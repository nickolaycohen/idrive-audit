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

def scan_folder(path, depth=1):
    """
    Calculate the size of the folder at the given path up to the specified depth.
    Returns total_bytes, used_bytes, free_bytes (used_bytes == total_bytes for folder).
    """
    total_size = 0
    try:
        if depth == 0:
            # No scanning, size 0
            return 0, 0, None
        elif depth == 1:
            # Sum sizes of immediate files and immediate subdirectories (non-recursive)
            with os.scandir(path) as it:
                for entry in it:
                    try:
                        if entry.is_file(follow_symlinks=False):
                            total_size += entry.stat(follow_symlinks=False).st_size
                        elif entry.is_dir(follow_symlinks=False):
                            # Sum sizes of immediate files inside this subdirectory only (one level down)
                            try:
                                with os.scandir(entry.path) as subit:
                                    for subentry in subit:
                                        if subentry.is_file(follow_symlinks=False):
                                            total_size += subentry.stat(follow_symlinks=False).st_size
                            except Exception as e:
                                print(f"Could not access {entry.path}: {e}")
                    except Exception as e:
                        print(f"Could not access {entry.path}: {e}")
        else:
            # For depth > 1, fallback to full recursive os.walk
            for dirpath, dirnames, filenames in os.walk(path):
                current_depth = dirpath[len(path):].count(os.sep)
                if current_depth >= depth:
                    # Don't descend further
                    dirnames[:] = []
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        if not os.path.islink(fp):
                            total_size += os.path.getsize(fp)
                    except Exception as e:
                        print(f"Could not access {fp}: {e}")
    except Exception as e:
        print(f"Error scanning folder {path}: {e}")
        return None, None, None

    free_bytes = None
    return total_size, total_size, free_bytes

# -------------------------
# Database setup
# -------------------------

def init_db():
    conn = sqlite3.connect(DB_PATH)
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
                    last_scanned DATETIME,
                    needs_backup BOOLEAN DEFAULT 1,
                    needs_tag BOOLEAN DEFAULT 0,
                    notes TEXT,
                    UNIQUE(device_id, path)
                )
            """)
            conn.execute("""
                INSERT INTO folders_new (folder_id, device_id, path, size_bytes, last_scanned, needs_backup, needs_tag, notes)
                SELECT
                    folder_id,
                    device_id,
                    path,
                    size_bytes,
                    last_scanned,
                    needs_backup,
                    needs_tag,
                    notes
                FROM (
                    SELECT *,
                           ROW_NUMBER() OVER (PARTITION BY device_id, path ORDER BY last_scanned DESC, folder_id DESC) as rn
                    FROM folders
                ) AS ranked_folders
                WHERE rn = 1;
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

def get_idrive_backup_info(path):
    """Check the idrive_audit.db to see if this path (or similar) is backed up."""
    if not os.path.exists(IDRIVE_DB_PATH):
        return None
    try:
        idrive_conn = sqlite3.connect(IDRIVE_DB_PATH)
        idrive_conn.row_factory = sqlite3.Row
        cur = idrive_conn.cursor()
        # Normalize path for comparison (IDrive paths are often absolute-ish)
        # We search for any record where the path matches or ends with our local path
        search_path = f"%{path.rstrip('/')}"
        cur.execute("SELECT size, filecount, timestamp, tag FROM api_calls WHERE path LIKE ? ORDER BY timestamp DESC LIMIT 1", (search_path,))
        row = cur.fetchone()
        idrive_conn.close()
        return row
    except Exception:
        return None

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
    parser.add_argument("--min-size", type=float, default=MIN_SIZE_GB, help="Minimum size in GB to record (default 1.0)")
    
    args = parser.parse_args()
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
        disks = subprocess.run(["diskutil", "list", "-plist"], capture_output=True, check=True)
        disks_info = plistlib.loads(disks.stdout)

        for disk in disks_info.get("AllDisksAndPartitions", []):
            for part in disk.get("Partitions", []):
                disk_id = part.get("DeviceIdentifier")
                info_proc = subprocess.run(["diskutil", "info", "-plist", disk_id], capture_output=True, check=True)
                info = plistlib.loads(info_proc.stdout)

                mount_point = info.get("MountPoint")
                if not mount_point:
                    continue

                abs_mount_point = os.path.abspath(mount_point)

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
                try:
                    for entry in os.scandir(mount_point):
                        if entry.is_dir() and not entry.name.startswith('.'):
                            size_bytes, _, _ = scan_folder(entry.path, depth=1)
                            if size_bytes and (size_bytes / (1024**3)) >= args.min_size:
                                conn.execute("""
                                    INSERT INTO folders (device_id, path, size_bytes, last_scanned)
                                    VALUES (?, ?, ?, ?)
                                    ON CONFLICT(device_id, path) DO UPDATE SET 
                                        size_bytes=excluded.size_bytes, 
                                        last_scanned=excluded.last_scanned
                                """, (device_id, entry.path, size_bytes, datetime.now(timezone.utc)))
                except Exception as e:
                    print(f"  Error scanning folders: {e}")

    if args.report:
        print(f"\n{'LOCAL VS IDRIVE BACKUP REPORT':^95}")
        print(f"{'Local Path':<45} | {'Size (GB)':>10} | {'IDrive Status':<25} | {'Notes'}")
        print("-" * 110)
        
        cursor = conn.execute("SELECT f.path, f.size_bytes, f.notes FROM folders f ORDER BY f.size_bytes DESC")
        for row in cursor:
            path = row['path']
            size_gb = row['size_bytes'] / (1024**3)
            idrive_data = get_idrive_backup_info(path)
            
            status = f"Backed Up ({idrive_data['size']/(1024**3):.1f}GB)" if idrive_data else "MISSING"
            print(f"{path[:45]:<45} | {size_gb:>10.2f} | {status:<25} | {row['notes'] or ''}")

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
