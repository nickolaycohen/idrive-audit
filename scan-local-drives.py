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

def get_mount_point_for_path(path):
    """
    Given a path, find its mount point.
    """
    # Shell expands ~ at the start. Avoid expanding literal ~ inside volume paths (common for scratch folders).
    if path.startswith('~'):
        path = os.path.expanduser(path)
    abs_path = os.path.abspath(path)

    if not os.path.exists(abs_path):
        return None

    curr = abs_path
    while not os.path.ismount(curr):
        parent = os.path.dirname(curr)
        if parent == curr:
            # Reached the ultimate root (e.g. '/')
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
                INSERT INTO folders_new (folder_id, device_id, path, size_bytes, last_modified, last_scanned, needs_tag, tag, drilled, class_id, notes)
                SELECT folder_id, device_id, path, size_bytes, last_modified, last_scanned, needs_tag, tag, drilled, """ + class_map_expr + """, notes
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
                drilled BOOLEAN DEFAULT 0,
                class_id INTEGER DEFAULT 1,
                notes TEXT,
                UNIQUE(device_id, path)
            )
        """)
        conn.commit()

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
    Propagates a given attribute (tag or class_id) to a base_path and all its subfolders
    across all devices (to handle Firmlink duplicates or re-mounted drives).
    """
    # Pattern to match all descendants in the directory tree (e.g., /path/to/dir/%)
    search_pattern = base_path.rstrip('/') + '/%'

    # Update the base_path itself and all its subfolders globally by path string
    cursor = conn.execute(f"UPDATE folders SET {attribute_name} = ? WHERE path = ? OR path LIKE ?",
                          (attribute_value, base_path, search_pattern))
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

def main():
    parser = argparse.ArgumentParser(description="Scan local drives and reconcile with IDrive backups.")
    parser.add_argument("--scan", action="store_true", help="Scan attached drives and top-level folders")
    parser.add_argument("--force", action="store_true", help="Force scan even if folder mtime matches")
    parser.add_argument("--report", action="store_true", help="Show local folders and their IDrive backup status")
    parser.add_argument("--path", help="Scan only a specific path")
    parser.add_argument("--tag", help="Tag a folder: --tag '/Users/name/Photos=Memories'")
    parser.add_argument("--output", help="Save the output to a specific file (e.g., report.txt)")
    parser.add_argument("--define-class", help="Define a folder class and priority: --define-class 'Media=1-PersonalData'")
    parser.add_argument("--assign-class", help="Assign a class to a folder: --assign-class '/path/to/dir=Media'")
    parser.add_argument("--update-class", help="Update an existing class by ID: --update-class '1=IDriveBackup=1-PersonalData'")
    parser.add_argument("--set-drilled", help="Set the drilled flag for a folder and subfolders: --set-drilled '/path/to/dir=1'")
    parser.add_argument("--min-size", type=float, default=MIN_SIZE_GB, help="Minimum size in GB to record (default 1.0)")
    
    args = parser.parse_args()

    conn = init_db()
    hostname = socket.gethostname()

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
            return

    if args.define_class:
        if "=" in args.define_class:
            name, pr_name = args.define_class.split("=", 1)
            # Lookup Priority ID
            pr_row = conn.execute("SELECT priority_id FROM folder_priorities WHERE priority_name = ?", (pr_name,)).fetchone()
            pr_id = pr_row['priority_id'] if pr_row else 1
            
            print(f"Defining class '{name}' linked to priority '{pr_name}' (ID: {pr_id})...")
            conn.execute("INSERT OR REPLACE INTO folder_classes (class_name, priority_id) VALUES (?, ?)", (name, pr_id))
            conn.commit()
            return

    if args.update_class:
        # Format: ID=NAME=PRIORITY
        parts = args.update_class.split("=")
        if len(parts) == 3:
            c_id, c_name, pr_name = parts
            # Lookup Priority ID
            pr_row = conn.execute("SELECT priority_id FROM folder_priorities WHERE priority_name = ?", (pr_name,)).fetchone()
            pr_id = pr_row['priority_id'] if pr_row else 1
            
            print(f"Updating folder class ID {c_id} to '{c_name}' with priority '{pr_name}'...")
            conn.execute("UPDATE folder_classes SET class_name = ?, priority_id = ? WHERE class_id = ?", (c_name, pr_id, c_id))
            conn.commit()
            print("Update complete.")
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
            return

    if args.assign_class:
        if "=" in args.assign_class:
            path, cls = args.assign_class.split("=", 1)
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
            return

    if args.scan:
        print(f"Scanning drives on host: {hostname}...\n")
        
        # UX: Check if this is the first time the script is being run
        db_check = conn.execute("SELECT COUNT(*) FROM devices").fetchone()
        if db_check and db_check[0] == 0:
            print(">>> [NOTICE] This appears to be an initial scan. Building the baseline")
            print(">>> may take several minutes. Progress is shown below.\n")
        
        target_disk_ids = []
        if args.path:
            try:
                # First, determine the mount point for the given path
                actual_mount_point = get_mount_point_for_path(args.path)
                if not actual_mount_point:
                    print(f"Error: Could not determine mount point for path {args.path}")
                    return

                # Resolve the device identifier for the mount point
                info_proc = subprocess.run(["diskutil", "info", "-plist", actual_mount_point], capture_output=True, check=True)
                info = plistlib.loads(info_proc.stdout)
                target_disk_ids = [info.get("DeviceIdentifier")]
            except Exception as e:
                print(f"Error: Could not resolve device for mount point {actual_mount_point} (derived from {args.path}): {e}")
                return
        else:
            disks = subprocess.run(["diskutil", "list", "-plist"], capture_output=True, check=True)
            disks_info = plistlib.loads(disks.stdout)
            target_disk_ids = disks_info.get("AllDisks", [])

        # Iterate over targeted disk identifiers
        for disk_id in target_disk_ids:
            info_proc = subprocess.run(["diskutil", "info", "-plist", disk_id], capture_output=True, check=True)
            info = plistlib.loads(info_proc.stdout)

            mount_point = info.get("MountPoint")
            if not mount_point:
                continue

            # Isolate primary internal drives (Macintosh HD) and user-mounted partitions.
            # This filters out system helper volumes like Recovery, Preboot, and VM.
            if info.get("Internal") and not args.path:
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

            # Upsert device
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

            # --- FIX: Prevent redundant usage records and keep only one entry per device ---
            cursor_usage = conn.execute("""
                SELECT usage_id, total_bytes, used_bytes, free_bytes 
                FROM device_usage 
                WHERE device_id = ? 
                ORDER BY recorded_at DESC
            """, (device_id,))
            usage_entries = cursor_usage.fetchall()
            
            last_entry = usage_entries[0] if usage_entries else None

            if last_entry is None or (last_entry[1] != total or last_entry[2] != used or last_entry[3] != free):
                # Usage changed or first time: Delete all old entries to maintain "one entry per device"
                conn.execute("DELETE FROM device_usage WHERE device_id = ?", (device_id,))
                conn.execute("""
                INSERT INTO device_usage (
                    device_id, recorded_at, total_bytes, used_bytes, free_bytes
                ) VALUES (?, ?, ?, ?, ?)
                    """, (device_id, datetime.now(timezone.utc).isoformat(), total, used, free))
                print(f"  Usage snapshot updated for {name}.")
            else:
                # Usage is the same. Prune any duplicate entries that might exist from previous runs.
                if len(usage_entries) > 1:
                    conn.execute("DELETE FROM device_usage WHERE device_id = ? AND usage_id != ?", (device_id, last_entry[0]))
                    print(f"  Cleaned up {len(usage_entries) - 1} duplicate records for {name}.")
                print(f"  Usage unchanged for {name}, skipping redundant snapshot.")

            print(f"{name} ({mount_point})")
            print(f"  Type: {device_type}")
            print(f"  Total: {total}")
            print(f"  Used:  {used}")
            print(f"  Free:  {free}\n")

            # --- Populate folders table ---
            print(f"  Scanning folders on {mount_point}...")
            
            # Always add the mount point itself as a tracked entry to check if the whole drive is backed up
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
                # If a path is provided, we only scan that specific folder.
                # Otherwise, we scan all top-level directories on the mount point.
                if args.path:
                    entries_to_scan = [args.path] if os.path.isdir(args.path) else []
                else:
                    entries_to_scan = [e.path for e in os.scandir(mount_point) if e.is_dir() and not e.name.startswith('.')]

                print(f"  Found {len(entries_to_scan)} top-level folders to audit on {name}.")
                for i, path_to_scan in enumerate(entries_to_scan, 1):
                    # Avoid system/virtual directories on the root drive to prevent Firmlink recursion (double-counting)
                    # /System/Volumes/Data/Volumes is a common path for duplicates.
                    if mount_point == "/" and os.path.basename(path_to_scan) in ("Volumes", "System", "dev", "Network"):
                        continue
                        
                    disp_path = format_display_path(path_to_scan)
                    # Check if folder was modified since last scan
                    current_mtime = os.path.getmtime(path_to_scan)
                    cursor_m = conn.execute("SELECT size_bytes, last_modified FROM folders WHERE device_id=? AND path=?", (device_id, path_to_scan))
                    existing_f = cursor_m.fetchone()
                    
                    if not args.force and existing_f and existing_f[1] == current_mtime:
                        print(f"    [{i}/{len(entries_to_scan)}] Skipping: {disp_path} (Unchanged: {existing_f[0]/(1024**3):.2f} GB)")
                        continue

                    print(f"    [{i}/{len(entries_to_scan)}] Processing: {disp_path}", end="", flush=True)
                    size_bytes, found_folders, _ = scan_folder(path_to_scan, min_size_gb=args.min_size)
                    size_gb = size_bytes / (1024**3) if size_bytes else 0
                    print(f" -> {disp_path}: {size_gb:.2f} GB")

                    # Ensure the target folder itself is always recorded, even if small or empty
                    if path_to_scan not in found_folders:
                        found_folders[path_to_scan] = {
                            "size": size_bytes,
                            "mtime": os.path.getmtime(path_to_scan)
                        }

                    for f_path, f_data in found_folders.items():
                        conn.execute("""
                            INSERT INTO folders (device_id, path, size_bytes, last_modified, last_scanned)
                            VALUES (?, ?, ?, ?, ?)
                            ON CONFLICT(device_id, path) DO UPDATE SET 
                                size_bytes=excluded.size_bytes, 
                                last_modified=excluded.last_modified,
                                last_scanned=excluded.last_scanned
                            """, (device_id, f_path, f_data["size"], f_data["mtime"], datetime.now(timezone.utc).isoformat()))
                        
                        # Mark the parent path as drilled now that children are recorded
                        conn.execute("UPDATE folders SET drilled=1 WHERE device_id=? AND path=?", (device_id, path_to_scan))
                    conn.commit()
            except Exception as e:
                print(f"  Error scanning folders: {e}")

    if args.report:
        print(f"\n{'LOCAL VS IDRIVE BACKUP REPORT':^190}")
        print(f"{'Local Path':<60} | {'Size (GB)':>10} | {'Modified':<18} | {'Class (Priority/Policy)':<50} | {'IDrive Status'}")
        print("-" * 190)
        
        cursor = conn.execute("""
            SELECT f.path, f.size_bytes, f.last_modified, f.tag, c.class_name, pr.priority_name, p.policy_name, f.notes 
            FROM folders f 
            LEFT JOIN folder_classes c ON f.class_id = c.class_id 
            LEFT JOIN folder_priorities pr ON c.priority_id = pr.priority_id
            LEFT JOIN backup_policies p ON pr.backup_policy_id = p.policy_id
            ORDER BY f.size_bytes DESC
        """)
        for row in cursor:
            raw_path = row['path']
            path = format_display_path(raw_path)
            size_gb = row['size_bytes'] / (1024**3)
            mtime = row['last_modified']
            mtime_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M') if mtime else "Unknown"
            folder_class = row['class_name'] or "Default"
            priority = row['priority_name'] or "Unknown"
            policy = row['policy_name'] or "IDriveBackup"
            
            if policy in ("IgnoreBackup", "SingleCopyNoBackup"):
                status = "IGNORED"
            else:
                idrive_data = get_idrive_backup_info(raw_path)
                idrive_size = (idrive_data['size'] or 0) if idrive_data else 0
                status = f"Backed Up ({idrive_size/(1024**3):.1f}GB)" if idrive_data else "MISSING"
                
            class_info = f"{folder_class} ({priority}/{policy})"
            print(f"{path[:60]:<60} | {size_gb:>10.2f} | {mtime_str:<18} | {class_info:<50} | {status}")

    if not any([args.scan, args.report, args.tag, args.define_class, args.assign_class, args.update_class, args.set_drilled]):
        parser.print_help()

    conn.commit()
    conn.close()
    print("Scan complete.")


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
