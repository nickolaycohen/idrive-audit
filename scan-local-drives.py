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

MIN_SIZE_GB = 1.0  # Only track folders larger than 1GB by default

# -------------------------
# Helpers
# -------------------------

class Logger(object):
    """Helper to write to both console and file."""
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "w", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        # Filter out progress indicators (\r) and ANSI escape sequences to keep the file clean
        if not (message.startswith('\r') or '\033[' in message):
            self.log.write(message)
            self.log.flush()

    def flush(self):
        self.terminal.flush()


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
    abs_path = os.path.abspath(path)
    # Check if the path itself is a mount point
    if os.path.ismount(abs_path):
        return abs_path
    
    # Traverse up the directory tree to find the mount point
    current_path = abs_path
    while True:
        parent_path = os.path.dirname(current_path)
        if parent_path == current_path: # Reached root and not a mount point
            return None
        if os.path.ismount(current_path):
            return current_path
        current_path = parent_path

def scan_folder(path, min_size_gb=1.0, depth=None):
    """
    Calculate the size of the folder and all sub-folders at the given path.
    If depth is None (default), it scans recursively for an accurate audit.
    Returns (total_bytes, found_folders_dict, None).
    found_folders_dict maps path -> {"size": bytes, "mtime": float}
    """
    folder_accum = {} # path -> {"size": size, "mtime": mtime}
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            # Feedback: Show the current directory being processed (truncated for terminal width)
            display_path = dirpath if len(dirpath) < 65 else f"...{dirpath[-62:]}"
            sys.stdout.write(f"\r      > Auditing: {display_path:<65}")
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

    # Ensure folders table schema is correct
    cursor = conn.execute("PRAGMA table_info(folders)")
    columns = [row[1] for row in cursor.fetchall()]

    # Check if table exists
    cursor2 = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='folders'")
    table_exists = cursor2.fetchone() is not None

    if table_exists:
        # Check for UNIQUE constraint on device_id and path
        cursor3 = conn.execute("PRAGMA index_list(folders)")
        indexes = cursor3.fetchall()
        has_unique = any('device_id' in idx[1] and 'path' in idx[1] and idx[2] == 1 for idx in indexes)

        # If UNIQUE constraint missing, migrate table
        if not has_unique:
            print("Migrating folders table to add UNIQUE(device_id, path)...")
            conn.execute("BEGIN TRANSACTION")
            conn.execute("""
                CREATE TABLE folders_new (
                    folder_id INTEGER PRIMARY KEY,
                    device_id INTEGER,
                    path TEXT,
                    size_bytes INTEGER,
                    last_modified REAL,
                    last_scanned DATETIME,
                    needs_backup BOOLEAN DEFAULT 1,
                    needs_tag BOOLEAN DEFAULT 0,
                    notes TEXT,
                    UNIQUE(device_id, path)
                )
            """)
            # Note: Migration from old schema without last_modified column
            conn.execute("""
                INSERT INTO folders_new (folder_id, device_id, path, size_bytes, last_scanned, needs_backup, needs_tag, notes)
                SELECT folder_id, device_id, path, size_bytes, last_scanned, needs_backup, needs_tag, notes
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
                needs_backup BOOLEAN DEFAULT 1,
                needs_tag BOOLEAN DEFAULT 0,
                notes TEXT,
                UNIQUE(device_id, path)
            )
        """)
        conn.commit()

    return conn

# -------------------------
# Main scan logic
# -------------------------

def tag_folder(conn, device_id, path, tag_name, needs_backup=1):
    conn.execute("""
        INSERT INTO folders (device_id, path, needs_tag, needs_backup, last_scanned)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(device_id, path) DO UPDATE SET needs_tag=excluded.needs_tag, needs_backup=excluded.needs_backup
    """, (device_id, path, tag_name, needs_backup, datetime.now(timezone.utc)))
    conn.commit()

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
    parser.add_argument("--report", action="store_true", help="Show local folders and their IDrive backup status")
    parser.add_argument("--path", help="Scan only a specific path")
    parser.add_argument("--tag", help="Tag a folder: --tag '/Users/name/Photos=Memories'")
    parser.add_argument("--output", help="Save the output to a specific file (e.g., report.txt)")
    parser.add_argument("--min-size", type=float, default=MIN_SIZE_GB, help="Minimum size in GB to record (default 1.0)")
    
    args = parser.parse_args()

    if args.output:
        sys.stdout = Logger(args.output)

    conn = init_db()
    hostname = socket.gethostname()

    if args.tag:
        if "=" in args.tag:
            t_path, t_val = args.tag.split("=", 1)
            print(f"Tagging {t_path} as {t_val}...")
            conn.execute("UPDATE folders SET notes = ? WHERE path = ?", (t_val, t_path))
            conn.commit()
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
            """, (name, device_type, uuid, capacity, datetime.now(timezone.utc)))

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
                """, (device_id, datetime.now(timezone.utc), total, used, free))
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
            """, (device_id, mount_point, used, os.path.getmtime(mount_point), datetime.now(timezone.utc)))
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
                        
                    # Check if folder was modified since last scan
                    current_mtime = os.path.getmtime(path_to_scan)
                    cursor_m = conn.execute("SELECT size_bytes, last_modified FROM folders WHERE device_id=? AND path=?", (device_id, path_to_scan))
                    existing_f = cursor_m.fetchone()
                    
                    if existing_f and existing_f[1] == current_mtime:
                        print(f"    [{i}/{len(entries_to_scan)}] Skipping: {path_to_scan} (Unchanged: {existing_f[0]/(1024**3):.2f} GB)")
                        continue

                    print(f"    [{i}/{len(entries_to_scan)}] Processing: {path_to_scan}", end="", flush=True)
                    size_bytes, found_folders, _ = scan_folder(path_to_scan, min_size_gb=args.min_size)
                    size_gb = size_bytes / (1024**3) if size_bytes else 0
                    print(f" -> {path_to_scan}: {size_gb:.2f} GB")

                    if found_folders:
                        for f_path, f_data in found_folders.items():
                            conn.execute("""
                                INSERT INTO folders (device_id, path, size_bytes, last_modified, last_scanned)
                                VALUES (?, ?, ?, ?, ?)
                                ON CONFLICT(device_id, path) DO UPDATE SET 
                                    size_bytes=excluded.size_bytes, 
                                    last_modified=excluded.last_modified,
                                    last_scanned=excluded.last_scanned
                            """, (device_id, f_path, f_data["size"], f_data["mtime"], datetime.now(timezone.utc)))
                        conn.commit()
            except Exception as e:
                print(f"  Error scanning folders: {e}")

    if args.report:
        print(f"\n{'LOCAL VS IDRIVE BACKUP REPORT':^95}")
        print(f"{'Local Path':<40} | {'Size (GB)':>10} | {'Modified':<20} | {'IDrive Status':<20} | {'Notes'}")
        print("-" * 125)
        
        cursor = conn.execute("SELECT f.path, f.size_bytes, f.last_modified, f.notes FROM folders f ORDER BY f.size_bytes DESC")
        for row in cursor:
            path = row['path']
            size_gb = row['size_bytes'] / (1024**3)
            mtime = row['last_modified']
            mtime_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M') if mtime else "Unknown"
            idrive_data = get_idrive_backup_info(path)
            
            idrive_size = (idrive_data['size'] or 0) if idrive_data else 0
            status = f"Backed Up ({idrive_size/(1024**3):.1f}GB)" if idrive_data else "MISSING"
            print(f"{path[:40]:<40} | {size_gb:>10.2f} | {mtime_str:<20} | {status:<20} | {row['notes'] or ''}")

    if not any([args.scan, args.report, args.tag]):
        parser.print_help()

    conn.commit()
    conn.close()
    print("Scan complete.")


if __name__ == "__main__":
    main()


# usage: 
# to scan all drives: python3 scan-local-drives.py --scan
# to tag a specific folder: python3 scan-local-drives.py --tag "/Volumes/Backup/Photos=Needs Backup"
# python3 scan-local-drives.py --scan --path "/Volumes/asd/projects"  (to scan just a specific folder)
# python3 scan-local-drives.py --report --output local_audit_report.txt (run report and save to file)

