#!/usr/bin/env python3

"""
Scan all local and attached drives on macOS, record disk utilization into SQLite database.
"""

import subprocess
import plistlib
import sqlite3
import socket
import argparse
from datetime import datetime, timezone
import os
import sys

DB_PATH = "device_registry.db"
IDRIVE_DB_PATH = "idrive_audit.db"
OUTPUT_FILE = "local_audit_report.txt"

MIN_SIZE_GB = 1.0  # Only track folders larger than 1GB by default

# -------------------------
# Helpers
# -------------------------

class Logger(object):
    """Helper to write to both console and file."""
    def __init__(self):
        self.terminal = sys.stdout
        self.log = open(OUTPUT_FILE, "w", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        # Filter out progress indicators (\r) and ANSI escape sequences to keep the file clean
        if not (message.startswith('\r') or '\033[' in message):
            self.log.write(message)
            self.log.flush()

    def flush(self):
        self.terminal.flush()

sys.stdout = Logger()

def format_display_path(path):
    """Trims /Volumes/ and replaces with // for cleaner output."""
    if path.startswith("/Volumes/"):
        return "//" + path[len("/Volumes/"):]
    return path

def get_macos_finder_tag(path):
    """
    Retrieves native macOS Finder Tags directly from OS extended attributes (xattr / mdls).
    Returns comma-separated tag names or None if not set.
    """
    if not path or not os.path.exists(path):
        return None
    try:
        proc = subprocess.run(["xattr", "-px", "com.apple.metadata:_kMDItemUserTags", path], capture_output=True, text=True)
        if proc.returncode == 0 and proc.stdout:
            hex_str = "".join(proc.stdout.split())
            data = bytes.fromhex(hex_str)
            tags = plistlib.loads(data)
            if tags and isinstance(tags, list):
                cleaned = [str(t).split("\n")[0].replace("FTag - ", "").strip() for t in tags if str(t).strip()]
                return ", ".join(cleaned) if cleaned else None
    except Exception:
        pass

    try:
        proc = subprocess.run(["mdls", "-raw", "-name", "kMDItemUserTags", path], capture_output=True, text=True)
        out = proc.stdout.strip()
        if out and out != "(null)":
            lines = [line.strip().strip('"').strip(",") for line in out.splitlines() if line.strip() not in ("(", ")")]
            cleaned = [l.replace("FTag - ", "").split("\n")[0].strip() for l in lines if l]
            return ", ".join(cleaned) if cleaned else None
    except Exception:
        pass
    return None

DEFAULT_FINDER_TAG_MAPPINGS = {
    "idrive - backup": {"internal_tag": "IDriveBackup", "class_name": "IDriveBackup"},
    "idrivebackup": {"internal_tag": "IDriveBackup", "class_name": "IDriveBackup"},
    "tmp": {"internal_tag": "tmp", "class_name": "ApplePhotosTempExport"},
    "sys": {"internal_tag": "sys", "class_name": "IgnoreBackup"},
    "ignore": {"internal_tag": "IgnoreBackup", "class_name": "IgnoreBackup"},
    "ignorebackup": {"internal_tag": "IgnoreBackup", "class_name": "IgnoreBackup"},
}

def resolve_internal_tag_from_finder_tag(conn, finder_tag):
    """
    Given a finder_tag string (e.g. 'iDrive - Backup' or 'tmp'),
    looks up finder_tag_mappings table or default mapping dictionary.
    Returns (internal_tag, class_id).
    """
    if not finder_tag:
        return None, None
    ft_clean = finder_tag.strip().lower()
    try:
        cur = conn.execute("SELECT internal_tag, class_id FROM finder_tag_mappings WHERE LOWER(finder_tag) = ?", (ft_clean,))
        row = cur.fetchone()
        if row:
            return row["internal_tag"], row["class_id"]
    except Exception:
        pass

    if ft_clean in DEFAULT_FINDER_TAG_MAPPINGS:
        m = DEFAULT_FINDER_TAG_MAPPINGS[ft_clean]
        cur_c = conn.execute("SELECT class_id FROM folder_classes WHERE class_name = ?", (m["class_name"],))
        c_row = cur_c.fetchone()
        cid = c_row["class_id"] if c_row else 1
        return m["internal_tag"], cid

    # Default fallback: any Finder tag maps to itself as internal tag
    return finder_tag.strip(), None

def sync_os_finder_tags(conn):
    """Scan registered local folders in SQLite and auto-populate finder_tag and mapped internal tags from macOS extended attributes."""
    print("Syncing native macOS Finder Tags from OS extended attributes...")
    cursor = conn.execute("SELECT folder_id, path, finder_tag, tag, class_id FROM folders")
    rows = cursor.fetchall()
    updated_count = 0
    for r in rows:
        p = r["path"]
        if os.path.exists(p):
            os_tag = get_macos_finder_tag(p)
            old_ftag = r["finder_tag"]
            if os_tag and os_tag != old_ftag:
                propagate_folder_attribute(conn, p, 'finder_tag', os_tag)
                updated_count += 1
    if updated_count > 0:
        conn.commit()
        print(f"Successfully synced {updated_count} macOS Finder tag(s) and mapped internal tags into database.")
    else:
        print("All macOS Finder tags are up to date.")
    return updated_count

def get_disk_usage_from_info(info):
    """
    Use diskutil values if available, but always fallback to shutil.disk_usage for mounted volumes.
    Ensures all drives, including ExFAT externals, are captured.
    """
    try:
        mount_point = info.get("MountPoint")
        total = info.get("VolumeTotalSpace") or info.get("TotalSize")
        free = info.get("VolumeFreeSpace") or info.get("FreeSpace")
        used = info.get("VolumeUsedSpace") or total - free if total and free else None

        if mount_point:
            import shutil
            try:
                usage = shutil.disk_usage(mount_point)
                if total is None:
                    total = usage.total
                if used is None:
                    used = usage.used
                if free is None:
                    free = usage.free
            except Exception as e:
                print(f"Fallback shutil failed for {mount_point}: {e}")

        if total is None or used is None or free is None:
            print(f"Unable to read usage for {mount_point}")
            return None, None, None

        print(f"DEBUG disk usage for {mount_point}: total={total}, used={used}, free={free}")
        return total, used, free

    except Exception as e:
        print(f"Error reading disk usage: {e}")
        return None, None, None


def detect_device_type(info):
    if info.get("Internal"):
        return "internal_drive"
    protocol = info.get("BusProtocol", "")
    if protocol in ("USB", "Thunderbolt"):
        return "external_drive"
    return "unknown"

SKIP_DIR_KEYWORDS = {
    "cloudstorage",
    "googledrive",
    "google drive",
    "onedrive",
    "dropbox",
    "mobile documents",
    "box-box",
}

def is_excluded_path(path):
    """
    Returns True if the path or any of its parent directory components match 
    known external cloud storage synchronization folders or system virtual directories.
    """
    if not path:
        return False
    norm = os.path.abspath(path)
    parts = norm.split(os.sep)
    
    for part in parts:
        part_lower = part.lower()
        if any(kw in part_lower for kw in SKIP_DIR_KEYWORDS):
            return True
            
    if "/Library/CloudStorage/" in norm or norm.endswith("/Library/CloudStorage"):
        return True
    if "/Library/Mobile Documents/" in norm or norm.endswith("/Library/Mobile Documents"):
        return True
        
    return False

def cleanup_excluded_folders(conn):
    """Deletes any previously recorded folders in SQLite that match cloud storage or excluded path patterns."""
    cursor = conn.execute("SELECT path FROM folders")
    paths_to_delete = [row[0] for row in cursor.fetchall() if is_excluded_path(row[0])]
    if paths_to_delete:
        print(f"Cleaning up {len(paths_to_delete)} cloud storage / excluded folder record(s) from database...")
        conn.executemany("DELETE FROM folders WHERE path = ?", [(p,) for p in paths_to_delete])
        conn.commit()

def get_mount_point_for_path(path):
    """
    Given a path, find its mount point.
    """
    if path.startswith('~'):
        path = os.path.expanduser(path)
    abs_path = os.path.abspath(path)

    if not os.path.exists(abs_path):
        return None

    curr = abs_path
    while not os.path.ismount(curr):
        parent = os.path.dirname(curr)
        if parent == curr:
            break
        curr = parent
    return curr

def scan_folder(path, min_size_gb=1.0, depth=None):
    """
    Calculate the size of the folder and all sub-folders at the given path.
    If depth is None (default), it scans recursively for an accurate audit.
    Returns (total_bytes, found_folders_dict, None).
    found_folders_dict maps path -> {"size": bytes, "mtime": float}
    """
    folder_accum = {} # path -> {"size": size, "mtime": mtime}
    try:
        def on_error(err):
            sys.stdout.write(f"\n      [WARN] Permission Denied: {err.filename}\n")

        for dirpath, dirnames, filenames in os.walk(path, onerror=on_error):
            # Prune excluded cloud storage directories so os.walk does not descend into them
            dirnames[:] = [d for d in dirnames if not is_excluded_path(os.path.join(dirpath, d))]
            if is_excluded_path(dirpath):
                continue

            # Feedback: Show the current directory being processed (truncated for terminal width)
            f_path = format_display_path(dirpath)
            display_path = f_path if len(f_path) < 65 else f"...{f_path[-62:]}"
            sys.stdout.write(f"\r      > Auditing: {display_path:<65}\033[K")
            sys.stdout.flush()

            if depth is not None:
                current_depth = dirpath[len(path):].count(os.sep)
                if current_depth >= depth:
                    # Don't descend further
                    dirnames[:] = []

            this_dir_mtime = os.path.getmtime(dirpath)
            this_dir_files = 0
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    if not os.path.islink(fp):
                        this_dir_files += os.path.getsize(fp)
                except Exception:
                    continue

            # Propagate this directory's file sizes up to the scan root
            curr = dirpath
            while True:
                if curr not in folder_accum:
                    folder_accum[curr] = {"size": 0, "mtime": 0}
                
                folder_accum[curr]["size"] += this_dir_files
                folder_accum[curr]["mtime"] = this_dir_mtime if curr == dirpath else folder_accum[curr]["mtime"]
                
                if curr == path:
                    break
                parent = os.path.dirname(curr)
                if parent == curr:
                    break
                curr = parent

    except Exception as e:
        print(f"Error scanning folder {path}: {e}")
        return 0, {}, None
    finally:
        # Clear the progress line after the walk finishes
        sys.stdout.write(f"\r\033[K")
        sys.stdout.flush()

    min_bytes = min_size_gb * (1024**3)
    # Filter results: only return folders large enough to track in the DB
    significant = {p: data for p, data in folder_accum.items() if data["size"] >= min_bytes}
    
    total_root_size = folder_accum.get(path, {}).get("size", 0)
    return total_root_size, significant, None

# -------------------------
# Database setup
# -------------------------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row # Enable accessing columns by name

    # --- backup_policies table creation ---
    conn.execute("""
    CREATE TABLE IF NOT EXISTS backup_policies (
        policy_id INTEGER PRIMARY KEY AUTOINCREMENT,
        policy_name TEXT UNIQUE
    )
    """)
    conn.execute("INSERT OR IGNORE INTO backup_policies (policy_id, policy_name) VALUES (1, 'IDriveBackup'), (2, 'IgnoreBackup'), (3, 'SingleCopyNoBackup')")
    conn.commit()

    # --- folder_priorities table creation ---
    conn.execute("""
    CREATE TABLE IF NOT EXISTS folder_priorities (
        priority_id INTEGER PRIMARY KEY,
        priority_name TEXT UNIQUE,
        backup_policy_id INTEGER,
        FOREIGN KEY(backup_policy_id) REFERENCES backup_policies(policy_id)
    )
    """)
    # Prepopulate based on request
    conn.execute("INSERT OR IGNORE INTO folder_priorities (priority_id, priority_name, backup_policy_id) VALUES (1, '1-PersonalData', 1)")
    conn.execute("INSERT OR IGNORE INTO folder_priorities (priority_id, priority_name, backup_policy_id) VALUES (9, '9-TemporaryWork', 3)")
    conn.commit()

    # --- folder_classes table migration and creation ---
    cursor_fc_check = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='folder_classes'")
    fc_row = cursor_fc_check.fetchone()
    if fc_row:
        sql = fc_row[0]
        # Trigger migration if class_id is missing, strict CHECK exists, or if missing priority_id
        if "class_id" not in sql or "priority_id" not in sql:
            print("Migrating folder_classes table to priority-based schema...")
            conn.execute("BEGIN TRANSACTION")
            conn.execute("ALTER TABLE folder_classes RENAME TO folder_classes_old")
            conn.execute("""
                CREATE TABLE folder_classes (
                    class_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    class_name TEXT UNIQUE,
                    priority_id INTEGER DEFAULT 1,
                    FOREIGN KEY(priority_id) REFERENCES folder_priorities(priority_id)
                )
            """)
            # Re-insert data: Map old backup_policy_id to reasonable priorities
            # Since we now use priorities, we'll map backup-heavy classes to priority 1
            if "backup_policy_id" in sql:
                conn.execute("""
                    INSERT OR IGNORE INTO folder_classes (class_name, priority_id) 
                    SELECT class_name, CASE WHEN backup_policy_id = 2 THEN 9 ELSE 1 END 
                    FROM folder_classes_old
                """)
            else:
                conn.execute("INSERT OR IGNORE INTO folder_classes (class_name, priority_id) SELECT class_name, 1 FROM folder_classes_old")
            
            conn.execute("DROP TABLE folder_classes_old")
            conn.execute("COMMIT")

    conn.execute("""
    CREATE TABLE IF NOT EXISTS folder_classes (
        class_id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_name TEXT UNIQUE,
        priority_id INTEGER DEFAULT 1,
        FOREIGN KEY(priority_id) REFERENCES folder_priorities(priority_id)
    )
    """)
    conn.commit()

    # Ensure default classes exist and link to appropriate priorities
    conn.execute("INSERT OR IGNORE INTO folder_classes (class_id, class_name, priority_id) VALUES (1, 'IDriveBackup', 1)")
    conn.execute("INSERT OR IGNORE INTO folder_classes (class_id, class_name, priority_id) VALUES (2, 'IgnoreBackup', 9)")
    # Rename existing legacy defaults to requested names if they are still named 'Default' or 'Ignore'
    conn.execute("UPDATE folder_classes SET class_name = 'IDriveBackup' WHERE class_id = 1 AND class_name = 'Default'")
    conn.execute("UPDATE folder_classes SET class_name = 'IgnoreBackup' WHERE class_id = 2 AND class_name = 'Ignore'")
    conn.commit()

    # --- finder_tag_mappings table creation ---
    conn.execute("""
    CREATE TABLE IF NOT EXISTS finder_tag_mappings (
        mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
        finder_tag TEXT UNIQUE,
        internal_tag TEXT,
        class_id INTEGER DEFAULT 1,
        FOREIGN KEY(class_id) REFERENCES folder_classes(class_id)
    )
    """)
    conn.execute("INSERT OR IGNORE INTO finder_tag_mappings (finder_tag, internal_tag, class_id) VALUES ('iDrive - Backup', 'IDriveBackup', 1)")
    conn.execute("INSERT OR IGNORE INTO finder_tag_mappings (finder_tag, internal_tag, class_id) VALUES ('IDriveBackup', 'IDriveBackup', 1)")
    conn.execute("INSERT OR IGNORE INTO finder_tag_mappings (finder_tag, internal_tag, class_id) VALUES ('tmp', 'tmp', 6)")
    conn.execute("INSERT OR IGNORE INTO finder_tag_mappings (finder_tag, internal_tag, class_id) VALUES ('sys', 'sys', 2)")
    conn.execute("INSERT OR IGNORE INTO finder_tag_mappings (finder_tag, internal_tag, class_id) VALUES ('IgnoreBackup', 'IgnoreBackup', 2)")
    conn.commit()

    # --- devices table creation ---
    conn.execute("""
    CREATE TABLE IF NOT EXISTS devices (
        device_id INTEGER PRIMARY KEY,
        device_name TEXT,
        device_type TEXT,
        filesystem_uuid TEXT UNIQUE,
        capacity_bytes INTEGER,
        last_seen DATETIME
    )
    """)
    conn.commit()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS device_usage (
        usage_id INTEGER PRIMARY KEY,
        device_id INTEGER,
        recorded_at DATETIME,
        total_bytes INTEGER,
        used_bytes INTEGER,
        free_bytes INTEGER
    )
    """)
    conn.commit()

    # Ensure folders table schema is correct
    cursor = conn.execute("PRAGMA table_info(folders)")
    columns = [row[1] for row in cursor.fetchall()]

    # Check if table exists
    cursor2 = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='folders'")
    table_exists = cursor2.fetchone() is not None

    if table_exists:
        # Ensure last_modified column exists before potentially migrating
        if "last_modified" not in columns:
            print("Adding last_modified column to folders table...")
            conn.execute("ALTER TABLE folders ADD COLUMN last_modified REAL")
            conn.commit()

        if "tag" not in columns:
            print("Adding tag column to folders table...")
            conn.execute("ALTER TABLE folders ADD COLUMN tag TEXT")
            conn.commit()

        if "finder_tag" not in columns:
            print("Adding finder_tag column to folders table...")
            conn.execute("ALTER TABLE folders ADD COLUMN finder_tag TEXT")
            conn.commit()

        if "drilled" not in columns:
            print("Adding drilled column to folders table...")
            conn.execute("ALTER TABLE folders ADD COLUMN drilled BOOLEAN DEFAULT 0")
            conn.commit()

        # Check for UNIQUE constraint on device_id and path
        cursor3 = conn.execute("PRAGMA index_list(folders)")
        indexes = cursor3.fetchall()
        has_unique = False
        for idx in indexes:
            if idx['unique'] == 1:
                cursor_idx = conn.execute(f"PRAGMA index_info('{idx['name']}')")
                idx_cols = [row['name'] for row in cursor_idx.fetchall()]
                if 'device_id' in idx_cols and 'path' in idx_cols:
                    has_unique = True
                    break

        has_class_id = "class_id" in columns
        has_needs_backup = "needs_backup" in columns

        # If UNIQUE constraint, class_id missing, or legacy needs_backup exists, migrate table
        if not has_unique or not has_class_id or has_needs_backup:
            print("Migrating folders table to align with latest schema...")
            conn.execute("BEGIN TRANSACTION")
            conn.execute("""
                CREATE TABLE folders_new (
                    folder_id INTEGER PRIMARY KEY,
                    device_id INTEGER,
                    path TEXT,
                    size_bytes INTEGER,
                    last_modified REAL,
                    last_scanned DATETIME,
                    needs_tag BOOLEAN DEFAULT 0, -- Legacy flag
                    tag TEXT,
                    finder_tag TEXT,
                    drilled BOOLEAN DEFAULT 0,
                    class_id INTEGER DEFAULT 1,
                    notes TEXT,
                    UNIQUE(device_id, path)
                )
            """)
            # Map old folder_class TEXT values to new class_id INTEGER if column exists
            if "class_id" in columns:
                class_map_expr = "class_id"
            elif "folder_class" in columns:
                class_map_expr = "COALESCE((SELECT class_id FROM folder_classes WHERE class_name = folder_class), 1)"
            else:
                class_map_expr = "1"

            conn.execute("""
                INSERT INTO folders_new (folder_id, device_id, path, size_bytes, last_modified, last_scanned, needs_tag, tag, finder_tag, drilled, class_id, notes)
                SELECT folder_id, device_id, path, size_bytes, last_modified, last_scanned, needs_tag, tag, finder_tag, drilled, """ + class_map_expr + """, notes
                FROM (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY device_id, path ORDER BY last_scanned DESC) as rn
                    FROM folders
                ) WHERE rn = 1
            """)
            conn.execute("DROP TABLE folders")
            conn.execute("ALTER TABLE folders_new RENAME TO folders")
            conn.execute("COMMIT")
    else:
        # Table does not exist, create fresh
        conn.execute("""
            CREATE TABLE IF NOT EXISTS folders (
                folder_id INTEGER PRIMARY KEY,
                device_id INTEGER,
                path TEXT,
                size_bytes INTEGER,
                last_modified REAL,
                last_scanned DATETIME,
                needs_tag BOOLEAN DEFAULT 0,
                tag TEXT,
                finder_tag TEXT,
                drilled BOOLEAN DEFAULT 0,
                class_id INTEGER DEFAULT 1,
                notes TEXT,
                UNIQUE(device_id, path)
            )
        """)
        conn.commit()

    cleanup_excluded_folders(conn)
    return conn

def get_device_id_for_path(conn, path):
    """
    Retrieves the device_id for a given path from the folders table.
    Assumes the path is unique enough or returns the first found.
    """
    cursor = conn.execute("SELECT device_id FROM folders WHERE path = ? LIMIT 1", (path,))
    row = cursor.fetchone()
    return row['device_id'] if row else None

def propagate_folder_attribute(conn, base_path, attribute_name, attribute_value):
    """
    Propagates a given attribute (tag, finder_tag, or class_id) to a base_path and all its subfolders
    across all devices (to handle Firmlink duplicates or re-mounted drives).
    Automatically maps Finder tags to internal tags and class definitions.
    """
    # Pattern to match all descendants in the directory tree (e.g., /path/to/dir/%)
    search_pattern = base_path.rstrip('/') + '/%'

    # Update the base_path itself and all its subfolders globally by path string
    cursor = conn.execute(f"UPDATE folders SET {attribute_name} = ? WHERE path = ? OR path LIKE ?",
                          (attribute_value, base_path, search_pattern))
    
    if attribute_name == 'finder_tag':
        mapped_tag, mapped_cid = resolve_internal_tag_from_finder_tag(conn, attribute_value)
        if mapped_tag:
            conn.execute("UPDATE folders SET tag = ? WHERE path = ? OR path LIKE ?",
                         (mapped_tag, base_path, search_pattern))
        if mapped_cid:
            conn.execute("UPDATE folders SET class_id = ? WHERE path = ? OR path LIKE ?",
                         (mapped_cid, base_path, search_pattern))

    return cursor.rowcount

# -------------------------
# Main scan logic
# -------------------------

def get_idrive_backup_info(path):
    """Check the idrive_audit.db to see if this path (or similar) is backed up."""
    if not os.path.exists(IDRIVE_DB_PATH):
        return None
    try:
        idrive_conn = sqlite3.connect(IDRIVE_DB_PATH)
        idrive_conn.row_factory = sqlite3.Row
        cur = idrive_conn.cursor()
        # Normalize path for comparison: search for records where the path matches
        search_path = f"%{path.rstrip('/')}"
        cur.execute("""
            SELECT size, filecount, timestamp, tag 
            FROM api_calls 
            WHERE path LIKE ? 
            ORDER BY timestamp DESC LIMIT 1
        """, (search_path,))
        row = cur.fetchone()
        idrive_conn.close()
        return row
    except Exception as e:
        print(f"Error querying IDrive DB: {e}")
        return None

def define_class_logic(conn, name, pr_name):
    pr_id = None
    first_part = pr_name.split('-')[0]
    if first_part.isdigit():
        check = conn.execute("SELECT priority_id FROM folder_priorities WHERE priority_id = ?", (first_part,)).fetchone()
        if check:
            pr_id = check['priority_id']
    
    if pr_id is None:
        pr_row = conn.execute("SELECT priority_id FROM folder_priorities WHERE priority_name = ?", (pr_name,)).fetchone()
        if pr_row:
            pr_id = pr_row['priority_id']

    if pr_id is not None:
        print(f"Defining class '{name}' linked to priority ID {pr_id}...")
        conn.execute("INSERT OR REPLACE INTO folder_classes (class_name, priority_id) VALUES (?, ?)", (name, pr_id))
        conn.commit()
        print("Class defined successfully.")
    else:
        print(f"Error: Could not resolve priority '{pr_name}' to a valid ID.")

def update_class_logic(conn, c_id, c_name, pr_name):
    pr_row = conn.execute("SELECT priority_id FROM folder_priorities WHERE priority_name = ?", (pr_name,)).fetchone()
    pr_id = pr_row['priority_id'] if pr_row else 1
    
    print(f"Updating folder class ID {c_id} to '{c_name}' with priority '{pr_name}'...")
    conn.execute("UPDATE folder_classes SET class_name = ?, priority_id = ? WHERE class_id = ?", (c_name, pr_id, c_id))
    conn.commit()
    print("Update complete.")

def assign_class_logic(conn, path, cls):
    if path.startswith('~'): path = os.path.expanduser(path)
    path = os.path.abspath(path).rstrip('/') or "/"
    
    cursor = conn.execute("SELECT class_id FROM folder_classes WHERE class_name = ?", (cls,))
    row = cursor.fetchone()
    if row:
        print(f"Assigning class '{cls}' to {path} and subfolders...")
        count = propagate_folder_attribute(conn, path, 'class_id', row['class_id'])
        conn.commit()
        if count == 0:
            print(f"Warning: Path '{path}' not found in registry. You may need to scan it first.")
        else:
            print(f"Updated {count} folders in the database.")
    else:
        print(f"Error: Folder class '{cls}' not found.")

def perform_scan(conn, hostname, path=None, force=False, min_size=MIN_SIZE_GB):
    print(f"Scanning drives on host: {hostname}...\n")
    
    db_check = conn.execute("SELECT COUNT(*) FROM devices").fetchone()
    if db_check and db_check[0] == 0:
        print(">>> [NOTICE] This appears to be an initial scan. Building the baseline")
        print(">>> may take several minutes. Progress is shown below.\n")
    
    target_disk_ids = []
    if path:
        try:
            actual_mount_point = get_mount_point_for_path(path)
            if not actual_mount_point:
                print(f"Error: Could not determine mount point for path {path}")
                return

            info_proc = subprocess.run(["diskutil", "info", "-plist", actual_mount_point], capture_output=True, check=True)
            info = plistlib.loads(info_proc.stdout)
            target_disk_ids = [info.get("DeviceIdentifier")]
        except Exception as e:
            print(f"Error: Could not resolve device for mount point {actual_mount_point} (derived from {path}): {e}")
            return
    else:
        disks = subprocess.run(["diskutil", "list", "-plist"], capture_output=True, check=True)
        disks_info = plistlib.loads(disks.stdout)
        target_disk_ids = disks_info.get("AllDisks", [])

    for disk_id in target_disk_ids:
        info_proc = subprocess.run(["diskutil", "info", "-plist", disk_id], capture_output=True, check=True)
        info = plistlib.loads(info_proc.stdout)

        mount_point = info.get("MountPoint")
        if not mount_point:
            continue

        if info.get("Internal") and not path:
            if mount_point != "/" and not mount_point.startswith("/Volumes/"):
                continue
            if info.get("APFSVolumeRole") in ("Recovery", "VM", "Preboot", "Update"):
                continue

        name = info.get("VolumeName") or disk_id
        uuid = info.get("VolumeUUID")
        capacity = info.get("TotalSize")
        device_type = detect_device_type(info)

        total, used, free = get_disk_usage_from_info(info)
        if total is None:
            continue

        cursor = conn.execute("SELECT device_id FROM devices WHERE filesystem_uuid=?", (uuid,))
        row = cursor.fetchone()
        
        if not row and device_type == "internal_drive":
            cursor = conn.execute("SELECT device_id FROM devices WHERE device_type='internal_drive' OR device_name=?", (name,))
            row = cursor.fetchone()
            if row:
                conn.execute("UPDATE devices SET filesystem_uuid=?, last_seen=? WHERE device_id=?", 
                             (uuid, datetime.now(timezone.utc).isoformat(), row[0]))
                conn.commit()

        if not row:
            conn.execute("""
            INSERT INTO devices (
                device_name, device_type, filesystem_uuid, capacity_bytes, last_seen
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(filesystem_uuid) DO UPDATE SET last_seen=excluded.last_seen
            """, (name, device_type, uuid, capacity, datetime.now(timezone.utc).isoformat()))
            cursor = conn.execute("SELECT device_id FROM devices WHERE filesystem_uuid=?", (uuid,))
            row = cursor.fetchone()

        if row is None:
            print(f"Could not find device_id for filesystem_uuid {uuid}, skipping folder scan")
            continue
        device_id = row[0]

        cursor_usage = conn.execute("""
            SELECT usage_id, total_bytes, used_bytes, free_bytes 
            FROM device_usage 
            WHERE device_id = ? 
            ORDER BY recorded_at DESC
        """, (device_id,))
        usage_entries = cursor_usage.fetchall()
        
        last_entry = usage_entries[0] if usage_entries else None

        if last_entry is None or (last_entry[1] != total or last_entry[2] != used or last_entry[3] != free):
            conn.execute("DELETE FROM device_usage WHERE device_id = ?", (device_id,))
            conn.execute("""
            INSERT INTO device_usage (
                device_id, recorded_at, total_bytes, used_bytes, free_bytes
            ) VALUES (?, ?, ?, ?, ?)
                """, (device_id, datetime.now(timezone.utc).isoformat(), total, used, free))
            print(f"  Usage snapshot updated for {name}.")
        else:
            if len(usage_entries) > 1:
                conn.execute("DELETE FROM device_usage WHERE device_id = ? AND usage_id != ?", (device_id, last_entry[0]))
                print(f"  Cleaned up {len(usage_entries) - 1} duplicate records for {name}.")
            print(f"  Usage unchanged for {name}, skipping redundant snapshot.")

        print(f"{name} ({mount_point})")
        print(f"  Type: {device_type}")
        print(f"  Total: {total}")
        print(f"  Used:  {used}")
        print(f"  Free:  {free}\n")

        print(f"  Scanning folders on {mount_point}...")
        
        conn.execute("""
            INSERT INTO folders (device_id, path, size_bytes, last_modified, last_scanned)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(device_id, path) DO UPDATE SET 
                size_bytes=excluded.size_bytes, 
                last_modified=excluded.last_modified,
                last_scanned=excluded.last_scanned
        """, (device_id, mount_point, used, os.path.getmtime(mount_point), datetime.now(timezone.utc).isoformat()))
        conn.commit()

        try:
            if path:
                entries_to_scan = [path] if os.path.isdir(path) and not is_excluded_path(path) else []
            else:
                entries_to_scan = [e.path for e in os.scandir(mount_point) 
                                   if e.is_dir() and not e.name.startswith('.') and not is_excluded_path(e.path)]

            print(f"  Found {len(entries_to_scan)} top-level folders to audit on {name}.")
            for i, path_to_scan in enumerate(entries_to_scan, 1):
                if mount_point == "/" and os.path.basename(path_to_scan) in ("Volumes", "System", "dev", "Network"):
                    continue
                    
                disp_path = format_display_path(path_to_scan)
                current_mtime = os.path.getmtime(path_to_scan)
                cursor_m = conn.execute("SELECT size_bytes, last_modified FROM folders WHERE device_id=? AND path=?", (device_id, path_to_scan))
                existing_f = cursor_m.fetchone()
                
                if not force and existing_f and existing_f[1] == current_mtime:
                    print(f"    [{i}/{len(entries_to_scan)}] Skipping: {disp_path} (Unchanged: {existing_f[0]/(1024**3):.2f} GB)")
                    continue

                print(f"    [{i}/{len(entries_to_scan)}] Processing: {disp_path}", end="", flush=True)

                if force:
                    search_pattern = path_to_scan.rstrip('/') + '/%'
                    conn.execute(
                        "UPDATE folders SET size_bytes=0 WHERE device_id=? AND (path=? OR path LIKE ?)",
                        (device_id, path_to_scan, search_pattern)
                    )

                size_bytes, found_folders, _ = scan_folder(path_to_scan, min_size_gb=min_size)
                size_gb = size_bytes / (1024**3) if size_bytes else 0
                print(f" -> {disp_path}: {size_gb:.2f} GB")

                if path_to_scan not in found_folders:
                    found_folders[path_to_scan] = {
                        "size": size_bytes,
                        "mtime": os.path.getmtime(path_to_scan)
                    }

                for f_path, f_data in found_folders.items():
                    os_ftag = get_macos_finder_tag(f_path)
                    conn.execute("""
                        INSERT INTO folders (device_id, path, size_bytes, last_modified, last_scanned, finder_tag)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(device_id, path) DO UPDATE SET 
                            size_bytes=excluded.size_bytes, 
                            last_modified=excluded.last_modified,
                            last_scanned=excluded.last_scanned,
                            finder_tag=COALESCE(excluded.finder_tag, folders.finder_tag)
                        """, (device_id, f_path, f_data["size"], f_data["mtime"], datetime.now(timezone.utc).isoformat(), os_ftag))
                    
                    conn.execute("UPDATE folders SET drilled=1 WHERE device_id=? AND path=?", (device_id, path_to_scan))
                conn.commit()
        except Exception as e:
            print(f"  Error scanning folders: {e}")

def build_hierarchical_rows(rows):
    """
    Groups folder rows by device, resolves parent-child hierarchy within each device,
    and sorts same-level siblings by size_bytes descending.
    Returns a list of tuples: (row, depth, display_path)
    """
    device_groups = {}
    for r in rows:
        dev_id = r['device_id'] if 'device_id' in r.keys() else 0
        device_groups.setdefault(dev_id, []).append(r)

    # Sort devices by max folder size in each device descending
    sorted_dev_ids = sorted(
        device_groups.keys(),
        key=lambda d: max((r['size_bytes'] for r in device_groups[d]), default=0),
        reverse=True
    )

    ordered_results = []

    for dev_id in sorted_dev_ids:
        dev_rows = device_groups[dev_id]
        
        path_map = {}
        for r in dev_rows:
            norm_p = r['path'].rstrip('/') if r['path'] != '/' else '/'
            path_map[norm_p] = r

        children_map = {p: [] for p in path_map}
        roots = []

        for norm_p in path_map:
            curr = os.path.dirname(norm_p)
            parent_found = None
            while curr and curr != norm_p:
                if curr in path_map:
                    parent_found = curr
                    break
                parent_dir = os.path.dirname(curr)
                if parent_dir == curr:
                    break
                curr = parent_dir

            if parent_found:
                children_map[parent_found].append(norm_p)
            else:
                roots.append(norm_p)

        def dfs(norm_p, depth, ancestor_tags):
            r = path_map[norm_p]
            raw_path = r['path']

            r_tag = (r['tag'] or '').strip().lower() if 'tag' in r.keys() and r['tag'] else ''
            r_ftag = (r['finder_tag'] or '').strip().lower() if 'finder_tag' in r.keys() and r['finder_tag'] else ''

            is_same_tag_child = False
            for anc_tag, anc_ftag in ancestor_tags:
                tag_match = bool(anc_tag and r_tag == anc_tag)
                ftag_match = bool(anc_ftag and r_ftag == anc_ftag)
                if tag_match or ftag_match:
                    is_same_tag_child = True
                    break

            if not is_same_tag_child:
                if depth == 0:
                    disp = format_display_path(raw_path)
                else:
                    base = os.path.basename(raw_path.rstrip('/'))
                    disp = ("." * depth) + "/" + base

                ordered_results.append((r, depth, disp))

            next_ancestor_tags = list(ancestor_tags)
            if r_tag or r_ftag:
                next_ancestor_tags.append((r_tag, r_ftag))

            kids = children_map[norm_p]
            kids.sort(key=lambda k: path_map[k]['size_bytes'], reverse=True)
            for k in kids:
                dfs(k, depth + 1, next_ancestor_tags)

        roots.sort(key=lambda p: path_map[p]['size_bytes'], reverse=True)
        for r_p in roots:
            dfs(r_p, 0, [])

    return ordered_results

def list_assigned_tags(conn):
    """Query and display all top-level assigned tags in the database."""
    cursor = conn.execute("""
        SELECT f.device_id, f.path, f.size_bytes, f.last_modified, f.tag, f.finder_tag, 
               c.class_name, pr.priority_name, p.policy_name
        FROM folders f
        LEFT JOIN folder_classes c ON f.class_id = c.class_id
        LEFT JOIN folder_priorities pr ON c.priority_id = pr.priority_id
        LEFT JOIN backup_policies p ON pr.backup_policy_id = p.policy_id
        WHERE (f.tag IS NOT NULL AND f.tag != '') OR (f.finder_tag IS NOT NULL AND f.finder_tag != '')
        ORDER BY f.size_bytes DESC
    """)
    rows = cursor.fetchall()

    if not rows:
        print("\nNo tagged folders found in the database.")
        return

    top_level_tagged = []
    for r in rows:
        r_path = r['path']
        r_tag = (r['tag'] or '').strip().lower()
        r_ftag = (r['finder_tag'] or '').strip().lower()

        has_ancestor = any(
            r_path.startswith(p['path'].rstrip('/') + '/') and
            (p['tag'] or '').strip().lower() == r_tag and
            (p['finder_tag'] or '').strip().lower() == r_ftag
            for p in rows
        )
        if not has_ancestor:
            top_level_tagged.append(r)

    print("\n" + "=" * 140)
    print(f"{'ASSIGNED TAGS SUMMARY':^140}")
    print("=" * 140)
    print(f"{'Path':<55} | {'Size (GB)':>9} | {'Internal Tag':<15} | {'Finder Tag':<15} | {'Class (Priority/Policy)'}")
    print("-" * 140)

    for r in top_level_tagged:
        r_path = r['path']
        disp_path = format_display_path(r_path)
        if len(disp_path) > 55:
            disp_path = "..." + disp_path[-52:]
        size_gb = (r['size_bytes'] or 0) / (1024**3)
        tag_str = r['tag'] or "[none]"
        ftag_str = r['finder_tag'] or "[none]"
        cls_name = r['class_name'] or "Default"
        prio_name = r['priority_name'] or "Unknown"
        pol_name = r['policy_name'] or "IDriveBackup"
        class_info = f"{cls_name} ({prio_name}/{pol_name})"

        sub_count = sum(
            1 for sub in rows 
            if sub['path'].startswith(r_path.rstrip('/') + '/') and sub['path'] != r_path
        )
        sub_str = f" (+{sub_count} subfolders)" if sub_count > 0 else ""

        print(f"{disp_path:<55} | {size_gb:>9.2f} | {tag_str:<15} | {ftag_str:<15} | {class_info}{sub_str}")

    print("-" * 140)
    print(f"Total Unique Tagged Top-Level Folders: {len(top_level_tagged)} (Total tagged records in DB: {len(rows)})")
    print("=" * 140)

def generate_report(conn, output_path=None):
    report_lines = []
    header = f"\n{'LOCAL VS IDRIVE BACKUP REPORT':^190}"
    cols = f"{'Local Path':<60} | {'Size (GB)':>10} | {'Modified':<18} | {'Class (Priority/Policy)':<50} | {'Finder Tag':<15} | {'IDrive Status'}"
    sep = "-" * 190
    
    print(header)
    print(cols)
    print(sep)
    
    if output_path:
        report_lines.extend([header, cols, sep])

    cursor = conn.execute("""
        SELECT f.device_id, f.path, f.size_bytes, f.last_modified, f.tag, f.finder_tag, c.class_name, pr.priority_name, p.policy_name, f.notes 
        FROM folders f 
        LEFT JOIN folder_classes c ON f.class_id = c.class_id
        LEFT JOIN folder_priorities pr ON c.priority_id = pr.priority_id
        LEFT JOIN backup_policies p ON pr.backup_policy_id = p.policy_id
        ORDER BY f.size_bytes DESC
    """)
    raw_rows = cursor.fetchall()
    hierarchical_entries = build_hierarchical_rows(raw_rows)

    for row, depth, path in hierarchical_entries:
        raw_path = row['path']
        size_gb = row['size_bytes'] / (1024**3)
        mtime = row['last_modified']
        mtime_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M') if mtime else "Unknown"
        folder_class = row['class_name'] or "Default"
        priority = row['priority_name'] or "Unknown"
        policy = row['policy_name'] or "IDriveBackup"
        finder_tag = row['finder_tag'] or ""
        
        if policy in ("IgnoreBackup", "SingleCopyNoBackup"):
            status = "IGNORED"
        else:
            idrive_data = get_idrive_backup_info(raw_path)
            idrive_size = (idrive_data['size'] or 0) if idrive_data else 0
            status = f"Backed Up ({idrive_size/(1024**3):.1f}GB)" if idrive_data else "MISSING"
            
        class_info = f"{folder_class} ({priority}/{policy})"
        line = f"{path[:60]:<60} | {size_gb:>10.2f} | {mtime_str:<18} | {class_info:<50} | {finder_tag:<15} | {status}"
        print(line)
        if output_path:
            report_lines.append(line)

    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(report_lines) + "\n")
            print(f"\nReport successfully saved to {output_path}")
        except Exception as e:
            print(f"\nError writing report to file {output_path}: {e}")

def manage_classes_interactive(conn):
    while True:
        print("\n" + "-" * 65)
        print("                 FOLDER CLASS MANAGEMENT")
        print("-" * 65)
        print("  1. List Existing Folder Classes")
        print("  2. Define / Create Class (--define-class)")
        print("  3. Assign Class to Folder (--assign-class)")
        print("  4. Update Class Definition (--update-class)")
        print("  b. Back to Main Menu")
        print("-" * 65)
        c = input("Select an option (1-4, b): ").strip().lower()
        if c in ('b', 'back', 'q'):
            break
        elif c == '1':
            cursor = conn.execute("""
                SELECT c.class_id, c.class_name, pr.priority_name, p.policy_name
                FROM folder_classes c
                LEFT JOIN folder_priorities pr ON c.priority_id = pr.priority_id
                LEFT JOIN backup_policies p ON pr.backup_policy_id = p.policy_id
                ORDER BY c.class_id
            """)
            rows = cursor.fetchall()
            print(f"\n{'ID':<5} | {'Class Name':<30} | {'Priority':<25} | {'Backup Policy'}")
            print("-" * 75)
            for r in rows:
                print(f"{r['class_id']:<5} | {r['class_name']:<30} | {(r['priority_name'] or ''):<25} | {r['policy_name'] or ''}")
        elif c == '2':
            name = input("Enter class name (e.g. Media): ").strip()
            pr_name = input("Enter priority name (e.g. 1-PersonalData or 9-ApplePhotosTempExport): ").strip()
            if name and pr_name:
                define_class_logic(conn, name, pr_name)
        elif c == '3':
            path = input("Enter folder path: ").strip()
            cls = input("Enter class name to assign: ").strip()
            if path and cls:
                assign_class_logic(conn, path, cls)
        elif c == '4':
            c_id = input("Enter Class ID: ").strip()
            c_name = input("Enter new Class Name: ").strip()
            pr_name = input("Enter Priority Name: ").strip()
            if c_id and c_name and pr_name:
                update_class_logic(conn, c_id, c_name, pr_name)

def manage_single_folder_interactive(conn, hostname, folder_row, min_size):
    raw_path = folder_row['path']
    disp_path = format_display_path(raw_path)
    size_gb = folder_row['size_bytes'] / (1024**3)
    
    while True:
        print("\n" + "-" * 70)
        print(f"Folder Detail: {disp_path}")
        print(f"Full Path:    {raw_path}")
        print(f"Size:         {size_gb:.2f} GB")
        print(f"Class:        {folder_row['class_name'] or 'Default'}")
        print(f"Tag:          {folder_row['tag'] or 'None'}")
        print(f"Finder Tag:   {folder_row['finder_tag'] or 'None'}")
        print(f"Drilled:      {'Yes' if folder_row['drilled'] else 'No'}")
        print("-" * 70)
        print("  1. 🔍 Scan / Drill Down into this directory")
        print("  2. 🏷️  Set Internal Tag")
        print("  3. 🎨 Set Finder Tag")
        print("  4. 🏷️  Assign Class")
        print("  5. 📌 Toggle Drilled Status")
        print("  b. Back to Folder List")
        print("-" * 70)
        
        act = input("Select an action (1-5, b): ").strip().lower()
        if act in ('b', 'back', 'q'):
            break
        elif act == '1':
            force_in = input("Force rescan unchanged subdirectories? (y/N): ").strip().lower()
            perform_scan(conn, hostname, path=raw_path, force=(force_in == 'y'), min_size=min_size)
            break
        elif act == '2':
            t_val = input("Enter Tag: ").strip()
            if t_val:
                propagate_folder_attribute(conn, raw_path, 'tag', t_val)
                conn.commit()
                print("Tag updated.")
        elif act == '3':
            t_val = input("Enter Finder Tag: ").strip()
            if t_val:
                propagate_folder_attribute(conn, raw_path, 'finder_tag', t_val)
                conn.commit()
                print("Finder Tag updated.")
        elif act == '4':
            cls_name = input("Enter Class Name to assign: ").strip()
            if cls_name:
                assign_class_logic(conn, raw_path, cls_name)
        elif act == '5':
            new_drilled = 0 if folder_row['drilled'] else 1
            conn.execute("UPDATE folders SET drilled = ? WHERE path = ?", (new_drilled, raw_path))
            conn.commit()
            print(f"Drilled status updated to {new_drilled}.")
            break

def browse_folders_interactive(conn, hostname, min_size):
    cursor = conn.execute("""
        SELECT f.device_id, f.path, f.size_bytes, f.last_modified, f.tag, f.finder_tag, f.drilled, c.class_name
        FROM folders f
        LEFT JOIN folder_classes c ON f.class_id = c.class_id
        ORDER BY f.size_bytes DESC
    """)
    raw_rows = cursor.fetchall()
    if not raw_rows:
        print("No folders registered in the database yet. Run a scan first!")
        return

    hierarchical_entries = build_hierarchical_rows(raw_rows)[:40]

    while True:
        print("\n" + "=" * 115)
        print(f"Top {len(hierarchical_entries)} Registered Local Folders (Hierarchical Tree by Size)")
        print("=" * 115)
        print(f"{'#':<3} | {'Local Path':<55} | {'Size (GB)':>9} | {'Class':<15} | {'Drilled':<7} | {'IDrive Status'}")
        print("-" * 115)
        
        for idx, (row, depth, disp_path) in enumerate(hierarchical_entries, 1):
            raw_path = row['path']
            if len(disp_path) > 55:
                disp_path = "..." + disp_path[-52:]
            size_gb = row['size_bytes'] / (1024**3)
            cls_name = row['class_name'] or "Default"
            drilled_str = "Yes" if row['drilled'] else "No"
            
            idrive_data = get_idrive_backup_info(raw_path)
            idrive_size = (idrive_data['size'] or 0) if idrive_data else 0
            status = f"Backed Up ({idrive_size/(1024**3):.1f}GB)" if idrive_data else "MISSING"
            
            print(f"{idx:<3} | {disp_path:<55} | {size_gb:>9.2f} | {cls_name:<15} | {drilled_str:<7} | {status}")
            
        print("-" * 115)
        sel = input("Select a folder number to drill down / manage (or 'b' for back): ").strip()
        if sel.lower() in ('b', 'back', 'q'):
            break
        if sel.isdigit() and 1 <= int(sel) <= len(hierarchical_entries):
            target_row = hierarchical_entries[int(sel) - 1][0]
            manage_single_folder_interactive(conn, hostname, target_row, min_size)
            cursor = conn.execute("""
                SELECT f.device_id, f.path, f.size_bytes, f.last_modified, f.tag, f.finder_tag, f.drilled, c.class_name
                FROM folders f
                LEFT JOIN folder_classes c ON f.class_id = c.class_id
                ORDER BY f.size_bytes DESC
            """)
            raw_rows = cursor.fetchall()
            hierarchical_entries = build_hierarchical_rows(raw_rows)[:40]

def run_interactive(conn, hostname, min_size=MIN_SIZE_GB):
    while True:
        print("\n" + "=" * 80)
        print(f"       LOCAL DRIVES & IDRIVE AUDIT - INTERACTIVE CONSOLE ({hostname})")
        print("=" * 80)
        print("  1. 🔍 Scan All Attached Storage Drives")
        print("  2. 📂 Scan Specific Directory Path")
        print("  3. 📊 Generate Local vs IDrive Backup Audit Report")
        print("  4. 🏷️  Apply Internal Tag (--tag)")
        print("  5. 🎨 Apply macOS Finder Tag (--finder-tag)")
        print("  6. 📋 Display All Assigned Tags (--list-tags)")
        print("  7. 🏷️  Manage Folder Classes (--define-class / --assign-class / --update-class)")
        print("  8. 📌 Set Drilled Status (--set-drilled)")
        print("  9. 📁 Browse Registered Local Folders & Drill Down")
        print("  q. Exit Interactive Console")
        print("=" * 80)
        
        choice = input("Select an option (1-9, q): ").strip().lower()
        if choice in ('q', 'exit', 'quit'):
            print("Exiting interactive session.")
            break
        elif choice == '1':
            force_in = input("Force rescan unchanged directories? (y/N): ").strip().lower()
            force = force_in == 'y'
            perform_scan(conn, hostname, path=None, force=force, min_size=min_size)
        elif choice == '2':
            p_in = input("Enter directory path to scan: ").strip()
            if p_in:
                if p_in.startswith('~'): p_in = os.path.expanduser(p_in)
                p_in = os.path.abspath(p_in)
                force_in = input("Force rescan unchanged directories? (y/N): ").strip().lower()
                force = force_in == 'y'
                perform_scan(conn, hostname, path=p_in, force=force, min_size=min_size)
            else:
                print("No path entered.")
        elif choice == '3':
            out_file = input(f"Save report to file? (press Enter for default '{OUTPUT_FILE}', or enter filename): ").strip()
            out_path = out_file if out_file else OUTPUT_FILE
            generate_report(conn, output_path=out_path)
        elif choice == '4':
            p_in = input("Enter target folder path: ").strip()
            if p_in:
                if p_in.startswith('~'): p_in = os.path.expanduser(p_in)
                p_in = os.path.abspath(p_in).rstrip('/') or "/"
                
                # Check if folder is already tagged in Finder
                cur_f = conn.execute("SELECT finder_tag, tag FROM folders WHERE path = ?", (p_in,))
                f_row = cur_f.fetchone()
                if f_row and f_row['finder_tag']:
                    mapped_tag, _ = resolve_internal_tag_from_finder_tag(conn, f_row['finder_tag'])
                    print(f"\n[NOTICE] Path '{p_in}' is already tagged in Finder as '{f_row['finder_tag']}' (auto-mapped to internal tag '{mapped_tag}').")
                    print("No need to re-apply internal tag.")
                    override = input("Press Enter to keep auto-mapped tag, or enter custom tag override: ").strip()
                    t_val = override if override else mapped_tag
                else:
                    t_val = input("Enter tag string (e.g. Memories): ").strip()
                
                if t_val:
                    print(f"Tagging {p_in} and subfolders as '{t_val}'...")
                    count = propagate_folder_attribute(conn, p_in, 'tag', t_val)
                    conn.commit()
                    print(f"Updated {count} folders in the database.")
        elif choice == '5':
            p_in = input("Enter target folder path: ").strip()
            t_val = input("Enter Finder Tag color/string (e.g. Orange): ").strip()
            if p_in and t_val:
                if p_in.startswith('~'): p_in = os.path.expanduser(p_in)
                p_in = os.path.abspath(p_in).rstrip('/') or "/"
                print(f"Setting Finder Tag for {p_in} and subfolders as '{t_val}'...")
                count = propagate_folder_attribute(conn, p_in, 'finder_tag', t_val)
                conn.commit()
                print(f"Updated {count} folders in the database.")
        elif choice == '6':
            list_assigned_tags(conn)
        elif choice == '7':
            manage_classes_interactive(conn)
        elif choice == '8':
            p_in = input("Enter target folder path: ").strip()
            val_in = input("Enter drilled status (1 = drilled, 0 = not drilled): ").strip()
            if p_in and val_in in ('0', '1'):
                if p_in.startswith('~'): p_in = os.path.expanduser(p_in)
                p_in = os.path.abspath(p_in).rstrip('/') or "/"
                drilled_val = int(val_in)
                cursor = conn.execute("UPDATE folders SET drilled = ? WHERE path = ?", (drilled_val, p_in))
                conn.commit()
                print(f"Updated {cursor.rowcount} record(s).")
        elif choice == '9':
            browse_folders_interactive(conn, hostname, min_size)

def main():
    parser = argparse.ArgumentParser(description="Scan local drives and reconcile with IDrive backups.")
    parser.add_argument("--interactive", "-i", action="store_true", help="Launch interactive console session")
    parser.add_argument("--scan", action="store_true", help="Scan attached drives and top-level folders")
    parser.add_argument("--force", action="store_true", help="Force scan even if folder mtime matches")
    parser.add_argument("--report", action="store_true", help="Show local folders and their IDrive backup status")
    parser.add_argument("--path", help="Scan only a specific path")
    parser.add_argument("--tag", help="Tag a folder: --tag '/Users/name/Photos=Memories'")
    parser.add_argument("--finder-tag", help="Set Finder Tag for a folder: --finder-tag '/path/to/dir=Red'")
    parser.add_argument("--list-tags", action="store_true", help="Display all assigned tags in the database")
    parser.add_argument("--sync-finder-tags", action="store_true", help="Sync native macOS Finder Tags from OS into database")
    parser.add_argument("--output", help="Save the output to a specific file (e.g., report.txt)")
    parser.add_argument("--define-class", help="Define a folder class and priority: --define-class 'Media=1-PersonalData'")
    parser.add_argument("--assign-class", help="Assign a class to a folder: --assign-class '/path/to/dir=Media'")
    parser.add_argument("--update-class", help="Update an existing class by ID: --update-class '1=IDriveBackup=1-PersonalData'")
    parser.add_argument("--set-drilled", help="Set the drilled flag for a folder and subfolders: --set-drilled '/path/to/dir=1'")
    parser.add_argument("--min-size", type=float, default=MIN_SIZE_GB, help="Minimum size in GB to record (default 1.0)")
    
    args = parser.parse_args()

    conn = init_db()
    hostname = socket.gethostname()

    if args.interactive or len(sys.argv) == 1:
        run_interactive(conn, hostname, min_size=args.min_size)
        conn.close()
        return

    if args.tag:
        if "=" in args.tag:
            t_path, t_val = args.tag.split("=", 1)
            if t_path.startswith('~'): t_path = os.path.expanduser(t_path)
            t_path = os.path.abspath(t_path).rstrip('/') or "/"
            
            print(f"Tagging {t_path} and subfolders as '{t_val}'...")
            count = propagate_folder_attribute(conn, t_path, 'tag', t_val)
            conn.commit()
            if count == 0:
                print(f"Warning: Path '{t_path}' not found in registry. You may need to scan it first.")
            else:
                print(f"Updated {count} folders in the database.")
            conn.close()
            return

    if args.finder_tag:
        if "=" in args.finder_tag:
            t_path, t_val = args.finder_tag.split("=", 1)
            if t_path.startswith('~'): t_path = os.path.expanduser(t_path)
            t_path = os.path.abspath(t_path).rstrip('/') or "/"
            
            print(f"Setting Finder Tag for {t_path} and subfolders as '{t_val}'...")
            count = propagate_folder_attribute(conn, t_path, 'finder_tag', t_val)
            conn.commit()
            if count == 0:
                print(f"Warning: Path '{t_path}' not found in registry. You may need to scan it first.")
            else:
                print(f"Updated {count} folders in the database.")
    if args.list_tags:
        list_assigned_tags(conn)
        conn.close()
        return

    if args.sync_finder_tags:
        sync_os_finder_tags(conn)
        conn.close()
        return

    if args.define_class:
        if "=" in args.define_class:
            name, pr_name = args.define_class.split("=", 1)
            define_class_logic(conn, name, pr_name)
        conn.close()
        return

    if args.update_class:
        parts = args.update_class.split("=")
        if len(parts) == 3:
            c_id, c_name, pr_name = parts
            update_class_logic(conn, c_id, c_name, pr_name)
        conn.close()
        return

    if args.set_drilled:
        if "=" in args.set_drilled:
            path, val = args.set_drilled.split("=", 1)
            if path.startswith('~'): path = os.path.expanduser(path)
            path = os.path.abspath(path).rstrip('/') or "/"
            try:
                drilled_val = int(val)
                print(f"Setting drilled={drilled_val} for {path}...")
                cursor = conn.execute("UPDATE folders SET drilled = ? WHERE path = ?", (drilled_val, path))
                conn.commit()
                count = cursor.rowcount
                if count == 0:
                    print(f"Warning: Path '{path}' not found in registry. You may need to scan it first.")
                else:
                    print(f"Updated {count} record(s) in the database.")
            except ValueError:
                print("Error: Drilled value must be an integer (0 or 1).")
        conn.close()
        return

    if args.assign_class:
        if "=" in args.assign_class:
            path, cls = args.assign_class.split("=", 1)
            assign_class_logic(conn, path, cls)
        conn.close()
        return

    if args.scan:
        perform_scan(conn, hostname, path=args.path, force=args.force, min_size=args.min_size)

    if args.report:
        generate_report(conn, output_path=args.output)

    conn.commit()
    conn.close()
    print("Operation complete.")


if __name__ == "__main__":
    main()


# usage: 
# =====

# to scan all drives: python3 scan-local-drives.py --scan
# to tag a specific folder: python3 scan-local-drives.py --tag "/Volumes/Backup/Photos=Needs Backup"
# python3 scan-local-drives.py --scan --path "/Volumes/asd/projects"  (to scan just a specific folder)
# python3 scan-local-drives.py --report --output local_audit_report.txt (run report and save to file)
# python3 scan-local-drives.py --tag "/Volumes/Extreme Pro/Photos Library/All-Media.photoslibrary=CentralPhotosLibrary"
# python3 scan-local-drives.py --scan --force --path "/Volumes/asd/~ToDelete" (force scan even if mtime matches, useful for folders that are tagged but need rescanning)
# python3 scan-local-drives.py --scan --force --path "/Volumes/Extreme Pro/iDrive Restore MacBookPro/NickolaysMacmini" (force scan even if mtime matches, useful for folders that are tagged but need rescanning)
# python3 scan-local-drives.py --scan --force --path "/Users/nickolaycohen/.Trash/Smart Album - iPhone 16 Pro Photos"
# python3 scan-local-drives.py --finder-tag "/Volumes/Extreme Pro/Photos=Orange"
# python3 scan-local-drives.py --scan --force --path "/Volumes/asd/copy of folder from MBP - check import to Apple Photos All Media Library and Delete"
# python3 scan-local-drives.py --define-class 'Media=9-ApplePhotosTempExport'
# python3 scan-local-drives.py --assign-class '/Users/nickolaycohen/Pictures/Apple Photo Exports/=ApplePhotosTempExport'

# python3 scan-local-drives.py --define-class "ApplePhotosTempExport=9-ApplePhotosTempExport"
# python3 scan-local-drives.py --scan --force --path "/Volumes/LaCie"
# python3 scan-local-drives.py --tag "/Volumes/Extreme Pro/Photos Library/All-Media.photoslibrary=CentralPhotosLibrary"

# MBP
# python3 scan-local-drives.py --finder-tag "/Users/nickolaycohen/Pictures/Apple Photo Exports=tmp"
# python3 scan-local-drives.py --tag "/Users/nickolaycohen/Library=sys"
# python3 scan-local-drives.py --assign-class '/Users/nickolaycohen/Pictures/Benny iPhone 16 Pro.photoslibrary=IDriveBackup'
# python3 scan-local-drives.py --finder-tag "/Users/nickolaycohen/Pictures/Benny iPhone 16 Pro.photoslibrary=IDriveBackup"
# python3 scan-local-drives.py --finder-tag "/Users/nickolaycohen/Samouil USB Stick=IDriveBackup"


