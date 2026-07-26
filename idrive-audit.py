import requests
import sys
import json
import argparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# default run:
# > python3 idrive-audit.py

# parameterized run example (to target a specific device and path):
# python3 idrive-audit.py --start-folder /Volumes --device-filter D01692572940000295373 --max-depth 1
# python3 idrive-audit.py --start-folder /Volumes/Extreme\ Pro --device-filter D01692572940000295373 --max-depth 1
# python3 idrive-audit.py --start-folder /Volumes/Extreme\ Pro/Photos\ Library --device-filter D01692572940000295373 --max-depth 1
# python3 idrive-audit.py --start-folder /C --device-filter D01567900303000721746 --max-depth 1
# python3 idrive-audit.py --start-folder /Archives --device-filter D01563744743000489825 --max-depth 1
# python3 idrive-audit.py --start-folder /Users --device-filter D01740009573000135005 --max-depth 1
# python3 idrive-audit.py --start-folder /Users/nickolaycohen --device-filter D01740009573000135005 --max-depth 1
# python3 idrive-audit.py --start-folder /Users/nickolaycohen/Pictures --device-filter D01740009573000135005 --max-depth 1
# python3 idrive-audit.py --start-folder /Pictures --device-filter D01563744743000489825 --max-depth 1
# python3 idrive-audit.py --start-folder /Volumes --device-filter D01563744743000489825 --max-depth 1
# python3 idrive-audit.py --start-folder /Volumes/OneTouch 4 --device-filter D01563744743000489825 --max-depth 1
# python3 idrive-audit.py --start-folder /C/iDrive-Backup-Restore-ASUS --device-filter D01567900303000721746 --max-depth 1
# python3 idrive-audit.py --start-folder /C/DELL1TB02 --device-filter D01567232251000246054 --max-depth 1
# python3 idrive-audit.py --start-folder /Users --device-filter D01692572940000295373 --max-depth 1
# python3 idrive-audit.py --start-folder /Users/nickolaycohen --device-filter D01692572940000295373 --max-depth 1
# python3 idrive-audit.py --start-folder /C/RAID2 --device-filter D01567232251000246054 --max-depth 1
# python3 idrive-audit.py --start-folder /C/RAID2/RAID1 --device-filter D01567232251000246054 --max-depth 1
# python3 idrive-audit.py --start-folder /Users/nickolaycohen/Pictures  --device-filter D01692572940000295373 --max-depth 1
# python3 idrive-audit.py --tag /Volumes/Extreme\ Pro/Photos\ Library/All-Media.photoslibrary  --device-filter D01692572940000295373 
# python3 idrive-audit.py --device-filter D01692572940000295373 --tag "/Volumes/Extreme\ Pro/Photos\ Library/All-Media.photoslibrary=PhotosLibrary-All-Media"
# python3 idrive-audit.py --device-filter D01692572940000295373 --tag "/Volumes/Extreme\ Pro/Photos\ Library/Samuil.photoslibrary=PhotosLibrary-Samuil"
# 3/13
# python3 idrive-audit.py --start-folder /C/iDrive-Backup-Restore-ASUS-2  --device-filter D01567900303000721746 --max-depth 1
# python3 idrive-audit.py --start-folder /Users/nickolaycohen/Pictures/Apple\ Photo\ Exports --device-filter D01740009573000135005 --max-depth 1
# python3 idrive-audit.py --start-folder /C/iDrive-Backup-Restore-ASUS-2/Niki\ and\ Benny\ Pictures  --device-filter D01567900303000721746 --max-depth 1
# python3 idrive-audit.py --start-folder /Users/nickolaycohen/Pictures/Apple\ Photo\ Exports/Benny\ iPhone\ 16\ Pro  --device-filter D01740009573000135005 --max-depth 1
# python3 idrive-audit.py --start-folder /C/Niki  --device-filter D01567232251000246054 --max-depth 1
# If we remove folder from iDrive - need to rerun the underlying folders:
# Ex.
# python3 idrive-audit.py --start-folder /C/iDrive-Backup-Restore-ASUS/C  --device-filter D01567900303000721746 --max-depth 1
# python3 idrive-audit.py --start-folder /Users  --device-filter D01563744743000489825 --max-depth 1
# python3 idrive-audit.py --start-folder /Users/nickolaycohen  --device-filter D01563744743000489825 --max-depth 1
# python3 idrive-audit.py --start-folder /Users/nickolaycohen/Pictures  --device-filter D01563744743000489825 --max-depth 1
# python3 idrive-audit.py --start-folder /Users/nickolaycohen/Pictures/Pipeline  --device-filter D01563744743000489825 --max-depth 1
# python3 idrive-audit.py --start-folder /Videos --device-filter R01563807439000950037 --max-depth 1
# python3 idrive-audit.py --device-filter R01563807439000950037 --tag "/Videos/Recently\ Added=RawAssets-Nickolay-iPhone5-iPhone13ProMax-Videos"
# python3 idrive-audit.py --start-folder /Videos --device-filter R01607197738000636951 --max-depth 1
# python3 idrive-audit.py --device-filter R01607197738000636951 --tag "/Videos/Recently\ Added=RawAssets-Benny-iPhone3-2017-2026-Videos"
# python3 idrive-audit.py --device-filter R01563807439000950037 --tag "/Videos/Recently\ Added=RawAssets-Nickolay-iPhone5-2017-2025-Videos"

# 4/11
# python3 idrive-audit.py --device-filter D01563711761000105006 --max-depth 
# python3 idrive-audit.py --start-folder /Users  --device-filter D01563711761000105006 --max-depth 1
# python3 idrive-audit.py --start-folder /Users --device-filter D01563711761000105006 --max-depth 1 --force --min-size 0
# python3 idrive-audit.py --start-folder /Users/nickolaycohen --device-filter D01563711761000105006 --max-depth 1 --force --min-size 0
# python3 idrive-audit.py --start-folder /Users/nickolaycohen/Pictures --device-filter D01563711761000105006 --max-depth 1 --force --min-size 0
# python3 idrive-audit.py --start-folder /Users/Shared --device-filter D01563711761000105006 --max-depth 1 --force --min-size 0
# python3 idrive-audit.py --start-folder /Users/nickolaycohen/Pictures/LightRoom\ Catalog\ and\ Data  --device-filter D01563744743000489825 --max-depth 1 --force --min-size 0
# python3 idrive-audit.py --start-folder /Users/nickolaycohen/Pictures/LightRoom\ Catalog\ and\ Data/LightRoom\ Imported\ Media  --device-filter D01563744743000489825 --max-depth 1 --force --min-size 0
# python3 idrive-audit.py --start-folder /Users/nickolaycohen/Pictures/Image\ Capture\ Import --device-filter D01563711761000105006 --max-depth 1 --force --min-size 0
# python3 idrive-audit.py --device-filter R01607197738000636951 --tag "/Videos/Recently\ Added=RawAssets-Benny-iPhone3-2017-2026-Videos"
# python3 idrive-audit.py --device-filter R01563807439000950037 --tag "/Photos=RawAssets-Nickolay-iPhone5-iPhone13ProMax-Photos"
# python3 idrive-audit.py --device-filter R01607197738000636951 --tag "/Photos=RawAssets-Benny-iPhone5-iPhone16-Photos"
# python3 idrive-audit.py --start-folder /Volumes/Extreme\ Pro/Photos\ Split --device-filter D01692572940000295373 --max-depth 1 --force --min-size 0
# python3 idrive-audit.py --start-folder /Volumes/Extreme\ Pro/ --device-filter D01692572940000295373 --max-depth 1 --force --min-size 0
# python3 idrive-audit.py --start-folder /Volumes/Extreme\ Pro/Photos\ Split --device-filter D01692572940000295373 --max-depth 1 --force --min-size 0
# python3 idrive-audit.py --start-folder /Volumes/Extreme\ Pro/Photos\ Library --device-filter D01692572940000295373 --max-depth 1 --force --min-size 0

# 4/18
# python3 idrive-audit.py --start-folder /Users/nickolaycohen/Pictures --device-filter D01563711761000105006 --max-depth 1 --force --min-size 0


# --- AUTH ---
# log into idrive website; go to Developer Tools → Application → Cookies and copy the EVSID and JSESSIONID values into the COOKIE_STR below (format: "EVSID=...; JSESSIONID=...;")
# API call is made to browseFolder endpoint - look in Headers tab -> Request Headers → Cookie to find the correct string to use here.  This is a manual step since the cookie is periodically refreshed by the server and we want to avoid hardcoding credentials in the script.

COOKIE_STR = "JSESSIONID=2344EDA0CB8B1DBC6903160904A881B2.tomcat8; EVSID=F9U66GWRW6F511WQMBY4394L4WUPP55011K0OTR4MWFAQ82JL8MTJ4QC1T7L; WOPI_SESSION=c9KXS213c6wZ"
BASE_URL = "https://evsweb2652.idrive.com/evs"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
    'Cookie': COOKIE_STR,
    'Content-Type': 'application/x-www-form-urlencoded',
    'X-Requested-With': 'XMLHttpRequest'
}

# --- SESSION SETUP ---
session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))
session.headers.update(HEADERS)


# cookie validation is now integrated into the dynamic device list retrieval

# --- DATABASE for logging API results (timestamped) ---
import sqlite3
from datetime import datetime, timedelta

DB_FILE = "idrive_audit.db"

# initialize database connection and table
conn = sqlite3.connect(DB_FILE)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute(
    '''
    CREATE TABLE IF NOT EXISTS api_calls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        device_id TEXT,
        device_name TEXT,
        endpoint TEXT,
        path TEXT,
        size INTEGER,
        filecount INTEGER,
        lmd TEXT,
        response_json TEXT,
        drilled INTEGER DEFAULT 0,
        tag TEXT DEFAULT '',
        active INTEGER DEFAULT 1
    )
    '''
)
# ensure columns exist for older databases
cur.execute("PRAGMA table_info(api_calls)")
rows = cur.fetchall()
cols = [row['name'] for row in rows]
# if tag column exists but is not TEXT, rebuild table with correct affinity
for row in rows:
    if row['name'] == 'tag' and row['type'].upper() != 'TEXT':
        print("migrating tag column to TEXT affinity")
        # rename existing table and recreate with new schema
        cur.execute("ALTER TABLE api_calls RENAME TO api_calls_old")
        cur.execute(
            '''
            CREATE TABLE api_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                device_id TEXT,
                device_name TEXT,
                endpoint TEXT,
                path TEXT,
                size INTEGER,
                filecount INTEGER,
                lmd TEXT,
                response_json TEXT,
                drilled INTEGER DEFAULT 0,
                tag TEXT DEFAULT '',
                active INTEGER DEFAULT 1
            )
            '''
        )
        # copy data over (tag value will be cast to text automatically)
        cur.execute(
            '''
            INSERT INTO api_calls (id,timestamp,device_id,device_name,endpoint,path,size,filecount,lmd,response_json,drilled,tag)
            SELECT id,timestamp,device_id,device_name,endpoint,path,size,filecount,lmd,response_json,drilled,tag
            FROM api_calls_old
            '''
        )
        cur.execute("DROP TABLE api_calls_old")
        conn.commit()
        # refresh rows/cols
        cur.execute("PRAGMA table_info(api_calls)")
        rows = cur.fetchall()
        cols = [r['name'] for r in rows]
        break

if 'device_name' not in cols:
    cur.execute('ALTER TABLE api_calls ADD COLUMN device_name TEXT')
    conn.commit()
if 'lmd' not in cols:
    cur.execute('ALTER TABLE api_calls ADD COLUMN lmd TEXT')
    conn.commit()
if 'drilled' not in cols:
    cur.execute('ALTER TABLE api_calls ADD COLUMN drilled INTEGER DEFAULT 0')
    conn.commit()
if 'tag' not in cols:
    # add TEXT column defaulting to empty string
    cur.execute("ALTER TABLE api_calls ADD COLUMN tag TEXT DEFAULT ''")
    conn.commit()
if 'active' not in cols:
    cur.execute('ALTER TABLE api_calls ADD COLUMN active INTEGER DEFAULT 1')
    conn.commit()
conn.commit()

def normalize_path(p):
    """Return a canonical path string used for DB keys (single leading slash).

    This ensures browseFolder and getProperties use the same path format.
    """
    if not p:
        return "/"
    # remove leading/trailing whitespace
    p = p.strip()
    # remove backslashes often introduced by shell auto-completion or escaping
    p = p.replace('\\', '')
    # ensure single leading slash
    p = '/' + p.lstrip('/').rstrip('/')
    return p

def log_api_call(device_id, device_name, endpoint, path, details):
    """Insert a record about an API call into the database.

    The API returns an optional 'lmd' field (last‑modification date).  If
    present, we store it alongside size/filecount.
    """
    # canonicalize path for DB key
    norm_path = normalize_path(path)

    # pull out last modified date; convert to ISO if possible
    lmd_val = None
    if isinstance(details, dict):
        raw_lmd = details.get('lmd')
        if raw_lmd:
            try:
                # original format appears to be YYYY/MM/DD HH:MM:SS
                dt = datetime.strptime(raw_lmd, "%Y/%m/%d %H:%M:%S")
                lmd_val = dt.isoformat()  # store in ISO 8601
            except Exception:
                lmd_val = raw_lmd  # fallback to whatever was provided

    size_val = int(details.get('size', 0)) if isinstance(details, dict) else None
    filecount_val = int(details.get('filecount', 0)) if isinstance(details, dict) else None
    # browseFolder responses may include a misleading size; we prefer to
    # trust getProperties results, so clear values for browseFolder
    if endpoint == 'browseFolder':
        size_val = None
        filecount_val = None
    resp_json = json.dumps(details) if details is not None else None

    # Carry over existing tags when updating or inserting new audit records
    cur.execute("SELECT tag FROM api_calls WHERE device_id=? AND path=? AND tag != '' LIMIT 1", (device_id, norm_path))
    tag_row = cur.fetchone()
    inherited_tag = tag_row['tag'] if tag_row else ''

    # try to find an existing row for this device/endpoint/path and update it
    try:
        cur.execute(
            "SELECT id FROM api_calls WHERE device_id=? AND path=? AND endpoint=? ORDER BY timestamp DESC LIMIT 1",
            (device_id, norm_path, endpoint)
        )
        existing = cur.fetchone()
        if existing:
            cur.execute(
                "UPDATE api_calls SET timestamp=?, device_name=?, size=?, filecount=?, lmd=?, response_json=?, tag=? WHERE id=?",
                (
                    datetime.utcnow().isoformat(),
                    device_name,
                    size_val,
                    filecount_val,
                    lmd_val,
                    resp_json,
                    inherited_tag,
                    existing['id']
                )
            )
            conn.commit()
            return existing['id']
    except Exception:
        # fall back to insert on any DB error
        pass

    cur.execute(
        '''
        INSERT INTO api_calls (timestamp, device_id, device_name, endpoint, path, size, filecount, lmd, response_json, tag)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            datetime.utcnow().isoformat(),
            device_id,
            device_name,
            endpoint,
            norm_path,
            size_val,
            filecount_val,
            lmd_val,
            resp_json,
            inherited_tag
        )
    )
    rowid = cur.lastrowid
    conn.commit()
    return rowid


def fetch_devices():
    """Fetch the list of devices dynamically from EVS API.

    Acts as cookie/authentication validation. Exits if authentication fails.
    Excludes the 'IDrive Photos' device.
    """
    print(f"Using COOKIE_STR: {COOKIE_STR}\n")
    try:
        r = session.post(f"{BASE_URL}/listDevices", data={'json': 'yes'}, timeout=15)
        data = r.json()
        if not isinstance(data, dict) or data.get('message') != 'SUCCESS' or 'contents' not in data:
            raise ValueError("unexpected API response format")

        devices = []
        for item in data['contents']:
            dev_id = item.get('device_id')
            nick = item.get('nick_name')
            if dev_id and nick:
                # Exclude the special IDrive Photos folder since it contains duplicates
                if nick == "IDrive Photos":
                    continue
                devices.append({"device_id": dev_id, "nick_name": nick})
        return devices
    except Exception as e:
        sys.stdout.write("\nERROR: authentication appears to have failed.\n")
        sys.stdout.write("Please open Chrome, navigate to idrive.com, "
                         "copy the EVSID/JSESSIONID cookie from Developer "
                         "Tools and update COOKIE_STR in this script.\n")
        sys.exit(1)


# Fetch device list dynamically
RAW_DEVICES = fetch_devices()

# --- SETTINGS ---
MAX_DEPTH = 1 # Increased depth to see deeper into /Users
MIN_SIZE_GB = 1.0 
OUTPUT_FILE = "idrive_audit_report.txt"

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

def get_details(device_id, device_name, path, ignore_skip=False):
    # skip detail call if this path was checked recently
    norm = normalize_path(path)
    # skip detail call if this path was checked recently
    if not ignore_skip and should_skip(device_id, norm, endpoint='getProperties'):
        print(f"  (skipping getProperties for {norm} on {device_name} — recent entry)")
        return {"size": 0, "filecount": 0}

    # try both prefix variants for compatibility, but always log using canonical path
    for prefix in ["/", "//"]:
        clean_path = path if path.startswith("/") else prefix + path
        payload = {'p': clean_path, 'json': 'yes', 'device_id': device_id}
        try:
            r = session.post(f"{BASE_URL}/getProperties", data=payload, timeout=15)
            res = r.json()
            # log the call for auditing using canonical path
            try:
                log_api_call(device_id, device_name, 'getProperties', norm, res)
            except Exception:
                pass  # logging should not interrupt the main flow
            if int(res.get('size', 0)) > 0:
                return res
        except Exception:
            continue

    # nothing useful found; do not insert a dummy zero-result row (avoids duplicate rows)
    return {"size": 0, "filecount": 0}

def crawl(device_id, device_name, current_path, depth, max_depth=MAX_DEPTH, ignore_skip=False, min_size_gb=MIN_SIZE_GB):
    # canonical path for DB lookups/logging
    norm = normalize_path(current_path)

    # If starting a forced or targeted scan (depth 1), reset existing sizes for this path 
    # and immediate children to 0. This preserves data from deeper historical scans 
    # while ensuring deleted items at this level are correctly reflected.
    if depth == 1 and ignore_skip:
        child_pattern = norm.rstrip('/') + '/%'
        exclude_pattern = norm.rstrip('/') + '/%/%'
        cur.execute(
            "UPDATE api_calls SET size=0, filecount=0 WHERE device_id=? AND (path=? OR (path LIKE ? AND path NOT LIKE ?))",
            (device_id, norm, child_pattern, exclude_pattern)
        )
        conn.commit()

    # don't re-scan a folder if we've queried it within the last 24h
    if not ignore_skip and should_skip(device_id, norm):
        print(f"  (skipping {norm} for {device_name} — scanned <24h ago)")
        return
    # Here `max_depth` is interpreted as the number of levels beneath the
    # starting folder to traverse. `depth` starts at 1 for the starting folder;
    # compute how many levels we've already descended as `depth - 1`.
    if (depth - 1) > max_depth:
        return

    payload = {'p': current_path, 'json': 'yes', 'device_id': device_id}
    try:
        r = session.post(f"{BASE_URL}/browseFolder", data=payload, timeout=15)
        res = r.json()
        # log the browse call and capture the row id so we can mark drilled later
        rowid = None
        try:
            rowid = log_api_call(device_id, device_name, 'browseFolder', norm, res)
        except Exception:
            rowid = None
        items = res.get('contents') or []
    except Exception:
        return

    # If we've reached the allowed depth (depth-1 >= max_depth) then we
    # should not iterate into children; still log the browse but skip
    # further detail calls and recursion.
    if (depth - 1) >= max_depth:
        items = []

    for item in items:
        name = item.get('p') or item.get('name') or item.get('desc')
        if not name or name in [".", ".."]: continue
        if SKIP_DEBUG: print(f"    [ITEM FOUND] {name}")

        next_path = name if name.startswith("/") else f"{current_path.rstrip('/')}/{name}"
        
        details = get_details(device_id, device_name, next_path, ignore_skip=ignore_skip)
        size_bytes = int(details.get('size', 0))
        size_gb = size_bytes / (1024**3)

        if size_gb >= min_size_gb:
            indent = "  " * depth
            print(f"{indent} > {name[:40]:<45} | {size_gb:>10.2f} GB | {details.get('filecount', 0):>8} files")
            crawl(device_id, device_name, next_path, depth + 1, max_depth, ignore_skip, min_size_gb)

    # Mark this folder as drilled only if we actually found and processed children.
    # This keeps leaf folders (only files or empty) as drilled=0 per your preference.
    try:
        do_mark = False
        if ignore_skip and depth == 1:
            do_mark = True
        elif max_depth is not None and (depth - 1) < max_depth:
            do_mark = True

        if do_mark and items:
            cur.execute(
                'UPDATE api_calls SET drilled=1 WHERE device_id=? AND path=? AND (endpoint=? OR endpoint=?)',
                (device_id, norm, 'browseFolder', 'getProperties')
            )
            affected = cur.rowcount
            conn.commit()
            print(f"  (marked drilled: {norm} on {device_name}) updated_rows={affected}")
        else:
            if SKIP_DEBUG:
                print(f"  (not marking drilled for {norm} on {device_name}) depth={depth} max_depth={max_depth} ignore_skip={ignore_skip}")
    except Exception as e:
        if SKIP_DEBUG:
            print(f"mark drilled failed for {norm}: {e}")


# toggle verbose skip debugging
SKIP_DEBUG = True

def tag_folder(device_id, device_name, path, tag_value):
    """Mark the given device/path as tagged with a text value.

    Prefer tagging an existing getProperties row (since that contains the
    authoritative size info); if none exists, fall back to any recent row.  If
    no record exists at all, insert a new row with endpoint set to
    "getProperties" so the tag can be associated with the real metadata.
    Empty string means untagged.
    """
    norm = normalize_path(path)
    
    # Update all existing rows for this path and device to ensure the tag is visible
    cur.execute("UPDATE api_calls SET tag=? WHERE device_id=? AND path=?", (tag_value, device_id, norm))
    
    # If no rows existed, insert a placeholder record
    if cur.rowcount == 0:
        cur.execute(
            "INSERT INTO api_calls (timestamp, device_id, device_name, endpoint, path, tag) VALUES (?, ?, ?, 'getProperties', ?, ?)",
            (datetime.utcnow().isoformat(), device_id, device_name, norm, tag_value)
        )

    conn.commit()


def should_skip(device_id, path, endpoint='browseFolder', hours=24):
    """Return True if the given device/path/endpoint should be skipped.

    Skipping occurs if the path is explicitly tagged or if a recent API call
    exists within the last ``hours`` hours.  ``SKIP_DEBUG`` prints the
    reasoning.
    """
    # normalize path for lookup
    norm = normalize_path(path)
    cur.execute(
        "SELECT timestamp, tag FROM api_calls "
        "WHERE device_id=? AND path=? AND endpoint=? "
        "ORDER BY timestamp DESC LIMIT 1",
        (device_id, norm, endpoint)
    )
    row = cur.fetchone()
    if not row:
        if SKIP_DEBUG:
            print(f"should_skip: no prior record for {endpoint} {norm} ({device_id})")
        return False
    if row['tag'] not in (None, "", "0"):
        if SKIP_DEBUG:
            print(f"should_skip: {norm} ({device_id}) is tagged ({row['tag']}), skipping")
        return True
    try:
        last = datetime.fromisoformat(row['timestamp'])
    except Exception:
        if SKIP_DEBUG:
            print(f"should_skip: bad timestamp '{row['timestamp']}'")
        return False
    delta = datetime.utcnow() - last
    result = delta < timedelta(hours=hours)
    if SKIP_DEBUG:
        print(f"should_skip: {endpoint} {norm} ({device_id}) last={last.isoformat()} delta={delta} skip={result}")
    return result


def print_storage_summary(min_size=MIN_SIZE_GB):
    """Print storage usage summarized by device and top-level folders."""
    # Fetch all getProperties rows with non-zero size
    cur.execute(
        """
        SELECT device_id, device_name, path, size, tag
        FROM api_calls
        WHERE endpoint = 'getProperties' AND size IS NOT NULL AND size > 0
        ORDER BY device_name, path
        """
    )
    rows = cur.fetchall()
    
    devices = {}
    for row in rows:
        dev_id = row['device_id']
        dev_name = row['device_name']
        path = row['path']
        size = row['size']
        tag = row['tag'] if row['tag'] else ''
        
        if dev_id not in devices:
            devices[dev_id] = {
                'name': dev_name,
                'folders': []
            }
        devices[dev_id]['folders'].append({'path': path, 'size': size, 'tag': tag})
        
    if not devices:
        return
        
    print("\n" + "=" * 95)
    print(f"{'IDRIVE STORAGE USE BY DEVICE':^95}")
    print("=" * 95)
    
    dev_summaries = []
    for dev_id, dev_info in devices.items():
        folders = dev_info['folders']
        # Sort folders by path length ascending so parents come before children
        folders_sorted = sorted(folders, key=lambda x: len(x['path']))
        
        top_level = []
        for f in folders_sorted:
            is_child = False
            for tl in top_level:
                tl_path = tl['path']
                if tl_path == '/':
                    is_child = True
                    break
                if f['path'].startswith(tl_path + '/'):
                    is_child = True
                    break
            if not is_child:
                top_level.append(f)
                
        total_size = sum(f['size'] for f in top_level)
        
        # Filter top-level folders by min_size
        filtered_top = [f for f in top_level if (f['size'] / (1024**3)) >= min_size]
        
        dev_summaries.append({
            'name': dev_info['name'],
            'total_size': total_size,
            'top_folders': sorted(filtered_top, key=lambda x: x['size'], reverse=True)
        })
        
    dev_summaries.sort(key=lambda x: x['total_size'], reverse=True)
    
    for ds in dev_summaries:
        total_gb = ds['total_size'] / (1024**3)
        print(f"Device: {ds['name']:<22} | Total Scanned Size: {total_gb:>8.2f} GB")
        if ds['top_folders']:
            for f in ds['top_folders']:
                f_gb = f['size'] / (1024**3)
                # truncate path if it is too long
                path_str = f['path']
                if len(path_str) > 50:
                    path_str = "..." + path_str[-47:]
                tag_suffix = f" | Tag: {f['tag']}" if f['tag'] else ""
                print(f"  - {path_str:<50} | {f_gb:>10.2f} GB{tag_suffix}")
        else:
            print(f"  - (no top-level folders >= {min_size:.2f} GB)")
    print("=" * 95)


def run_interactive(min_size=MIN_SIZE_GB):
    """Run an interactive console loop to manage top folders, showing tagged folders at the top."""
    while True:
        # Print storage usage by device
        print_storage_summary(min_size=min_size)

        # Fetch all drilled folders (which have drilled > 0 in database)
        cur.execute(
            """
            SELECT device_id, device_name, path, size, filecount, tag, active
            FROM api_calls
            WHERE endpoint = 'getProperties' AND drilled > 0
            ORDER BY device_name, path
            """
        )
        drilled_rows = cur.fetchall()

        # Fetch all tagged folders (excluding drilled folders)
        cur.execute(
            """
            SELECT device_id, device_name, path, size, filecount, tag, active
            FROM api_calls
            WHERE endpoint = 'getProperties' AND tag IS NOT NULL AND tag != '' AND tag != '0' AND (drilled IS NULL OR drilled = 0)
            ORDER BY device_name, size DESC
            """
        )
        tagged_rows = cur.fetchall()

        # Fetch the top 10 largest untagged folders (excluding drilled folders)
        cur.execute(
            """
            SELECT device_id, device_name, path, size, filecount, tag, active
            FROM api_calls
            WHERE endpoint = 'getProperties' AND size IS NOT NULL AND size > 0 AND (tag IS NULL OR tag = '' OR tag = '0') AND (drilled IS NULL OR drilled = 0)
            ORDER BY size DESC
            LIMIT 10
            """
        )
        untagged_rows = cur.fetchall()
        
        rows = list(drilled_rows) + list(tagged_rows) + list(untagged_rows)
        
        if not rows:
            print("\nNo folder size data found in the database. Please run a regular audit scan first to populate the database.")
            break
            
        print("\n" + "=" * 149)
        print(f"{'IDRIVE ACCOUNT STORAGE MANAGEMENT':^149}")
        print("=" * 149)
        
        current_idx = 1
        
        if drilled_rows:
            print(f"\n--- DRILLED FOLDERS ---")
            print(f"{'No.':<4} | {'Device':<22} | {'Path':<70} | {'Size (GB)':>10} | {'Tag':<20} | {'Active':<8}")
            print("-" * 149)
            for row in drilled_rows:
                size_val = row['size'] if row['size'] is not None else 0
                size_gb = size_val / (1024**3)
                tag_str = row['tag'] if row['tag'] else "[none]"
                active_str = "Yes" if row['active'] else "No"
                dev_name = row['device_name'][:22]
                path_str = row['path']
                if len(path_str) > 68:
                    path_str = "..." + path_str[-65:]
                print(f"{current_idx:<4} | {dev_name:<22} | {path_str:<70} | {size_gb:>10.2f} | {tag_str:<20} | {active_str:<8}")
                current_idx += 1
            print("-" * 149)
            
        if tagged_rows:
            print(f"\n--- TAGGED FOLDERS ---")
            print(f"{'No.':<4} | {'Device':<22} | {'Path':<70} | {'Size (GB)':>10} | {'Tag':<20} | {'Active':<8}")
            print("-" * 149)
            for row in tagged_rows:
                size_val = row['size'] if row['size'] is not None else 0
                size_gb = size_val / (1024**3)
                tag_str = row['tag']
                active_str = "Yes" if row['active'] else "No"
                dev_name = row['device_name'][:22]
                path_str = row['path']
                if len(path_str) > 68:
                    path_str = "..." + path_str[-65:]
                print(f"{current_idx:<4} | {dev_name:<22} | {path_str:<70} | {size_gb:>10.2f} | {tag_str:<20} | {active_str:<8}")
                current_idx += 1
            print("-" * 149)

        if untagged_rows:
            print(f"\n--- UNTAGGED FOLDERS (TOP 10 BY SIZE) ---")
            print(f"{'No.':<4} | {'Device':<22} | {'Path':<70} | {'Size (GB)':>10} | {'Tag':<20} | {'Active':<8}")
            print("-" * 149)
            for row in untagged_rows:
                size_val = row['size'] if row['size'] is not None else 0
                size_gb = size_val / (1024**3)
                tag_str = "[none]"
                active_str = "Yes" if row['active'] else "No"
                dev_name = row['device_name'][:22]
                path_str = row['path']
                if len(path_str) > 68:
                    path_str = "..." + path_str[-65:]
                print(f"{current_idx:<4} | {dev_name:<22} | {path_str:<70} | {size_gb:>10.2f} | {tag_str:<20} | {active_str:<8}")
                current_idx += 1
            print("-" * 149)
            
        print(f"Options: Enter 1-{len(rows)} to select a folder, 'r' to refresh, or 'q' to quit.")
        choice = input("Choice: ").strip().lower()
        
        if choice == 'q':
            print("Exiting interactive session.")
            break
        elif choice == 'r':
            continue
            
        if not choice.isdigit() or not (1 <= int(choice) <= len(rows)):
            print(f"Invalid choice. Please enter a number between 1 and {len(rows)}.")
            continue
            
        selected_row = rows[int(choice) - 1]
        manage_folder_interactive(selected_row, min_size)

def manage_folder_interactive(row, min_size):
    """Sub-menu to manage a specific selected folder."""
    device_id = row['device_id']
    device_name = row['device_name']
    path = row['path']
    
    while True:
        # Retrieve the latest details for this path from DB
        cur.execute(
            """
            SELECT size, filecount, tag, drilled, active
            FROM api_calls
            WHERE device_id = ? AND path = ? AND endpoint = 'getProperties'
            """,
            (device_id, path)
        )
        current = cur.fetchone()
        if not current:
            print(f"\nFolder {path} no longer found in the database.")
            break
            
        size_gb = current['size'] / (1024**3)
        files = current['filecount']
        tag = current['tag'] if current['tag'] else "[none]"
        is_drilled = current['drilled'] > 0
        is_active = current['active'] > 0
        
        print("\n" + "-" * 80)
        print(f"Selected Folder Details:")
        print(f"  Device: {device_name} ({device_id})")
        print(f"  Path:   {path}")
        print(f"  Size:   {size_gb:.2f} GB ({files} files)")
        print(f"  Tag:    {tag}")
        print(f"  Drilled: {'Yes' if is_drilled else 'No'}")
        print(f"  Active:  {'Yes' if is_active else 'No'}")
        print("-" * 80)
        print("Actions:")
        print("  1. Drill Down (browse subfolders and discover sizes)")
        print("  2. Tag/Rename Tag")
        print("  3. Toggle Active status")
        if is_drilled:
            print("  4. Undrill (delete subfolder records and reset status)")
            print("  5. Go Back")
            max_act = 5
        else:
            print("  4. Go Back")
            max_act = 4
        
        act = input(f"Choose action (1-{max_act}): ").strip()
        
        if not act:
            break
            
        if is_drilled:
            if act == '5':
                break
            elif act == '4':
                print(f"\nUndrilling {path} on {device_name}...")
                norm = normalize_path(path)
                child_pattern = norm.rstrip('/') + '/%'
                
                # Delete subfolder records
                cur.execute(
                    "DELETE FROM api_calls WHERE device_id = ? AND path LIKE ?",
                    (device_id, child_pattern)
                )
                # Reset drilled flag
                cur.execute(
                    "UPDATE api_calls SET drilled = 0 WHERE device_id = ? AND path = ?",
                    (device_id, norm)
                )
                conn.commit()
                print("Subfolder records deleted and folder marked as not drilled.")
                
                # Rescan top level folder
                print(f"Rescanning {path} size details...")
                get_details(device_id, device_name, path, ignore_skip=True)
                print("Rescan completed.")
                continue
        else:
            if act == '4':
                break
                
        if act == '1':
            print(f"\nDrilling down into {path} on {device_name}...")
            # Run crawl on the selected path with max_depth=1 (immediate children)
            # ignore_skip=True is used to bypass the 24h skip logic since this is user-triggered
            crawl(device_id, device_name, path, depth=1, max_depth=1, ignore_skip=True, min_size_gb=min_size)
            print("Drill down completed.")
        elif act == '2':
            new_tag = input("Enter tag value (press Enter to clear tag): ").strip()
            tag_folder(device_id, device_name, path, new_tag)
            print(f"Successfully updated tag to: {new_tag if new_tag else '[none]'}")
        elif act == '3':
            new_active = 0 if is_active else 1
            cur.execute(
                "UPDATE api_calls SET active = ? WHERE device_id = ? AND path = ?",
                (new_active, device_id, path)
            )
            conn.commit()
            print(f"Successfully toggled active status to: {'Yes' if new_active else 'No'}")


def run_audit(start_folder=None, one_level=False, device_filter=None, max_depth=MAX_DEPTH, force=False, min_size=MIN_SIZE_GB):
    """Perform the audit.

    If both ``device_filter`` and ``start_folder`` are provided the script will
    **only** scan that single device and will drill exactly one level below
    the given path, ignoring any skip logic. Any other devices/paths are
    skipped entirely.

    Parameters:
        start_folder: path to begin crawling (on targeted device).
        one_level: when true and no path is supplied, limit recursion to one
            level beneath the root.
        device_filter: device id or nickname to target; if ``None`` all devices
            are examined.
    """
    print(f"\n{'IDRIVE RECURSIVE ACCOUNT AUDIT':^85}")
    print(f"{'Folder Hierarchy':<50} | {'Size':>13} | {'Files':>10}")
    print("-" * 85)
    
    for dev in RAW_DEVICES:
        if device_filter:
            if device_filter.lower() not in dev['device_id'].lower() and \
               device_filter.lower() not in dev['nick_name'].lower():
                continue
        print(f"\nDEVICE: {dev['nick_name']} ({dev['device_id']})")
        root = start_folder or "/"
        # compute allowed recursion depth. We treat `max_depth` as the
        # number of levels beneath the root (so 0 = root only). Internally
        # `crawl` uses depth starting at 1 and compares (depth-1) to this
        # `max_depth` value. The `--one-level` flag forces one level beneath root.
        if one_level:
            effective_beneath = 1
        else:
            effective_beneath = (max_depth if max_depth is not None else 1)

        # pass the number of levels beneath root directly to `crawl`
        limit = max(0, int(effective_beneath))

        # when a starting folder is provided we bypass skip checks but still
        # respect the requested `max_depth` behavior
        ignore = True if (start_folder or force) else False

        crawl(dev['device_id'], dev['nick_name'], root, 1, limit, ignore_skip=ignore, min_size_gb=min_size)
        print("-" * 85)
    
    print(f"\nAudit complete. Results saved to {OUTPUT_FILE}")
    print(f"API call history is recorded in {DB_FILE}")
    # close database connection cleanly
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IDrive Recursive Account Audit")
    parser.add_argument("--start-folder", help="Path to begin crawling (on targeted device)")
    parser.add_argument("--one-level", action="store_true", help="Limit recursion to one level")
    parser.add_argument("--device-filter", help="Device ID or nickname to target")

    parser.add_argument("--max-depth", type=int, default=MAX_DEPTH,
                        help=f"Maximum recursion depth (default {MAX_DEPTH})")
    parser.add_argument("--force", action="store_true", help="Bypass 24h skip logic and re-scan everything")
    parser.add_argument("--min-size", type=float, default=MIN_SIZE_GB, help=f"Minimum size in GB to display (default {MIN_SIZE_GB})")
    parser.add_argument("--interactive", "-i", action="store_true", help="Run interactive session to view top folders, drill down, tag, or clean up")

    # tagging operations
    parser.add_argument("--tag", help="Mark a device/path as tagged (format path[=value], value optional)")
    parser.add_argument("--untag", help="Remove the tag from a device/path")
    parser.add_argument("--list-tags", action="store_true",
                        help="Print all tagged paths for matching device")

    args = parser.parse_args()
    print(f"Parsed parameters: {args}")

    # handle interactive session request
    if args.interactive:
        run_interactive(min_size=args.min_size)
        conn.close()
        sys.exit(0)

    # handle tag/untag/list requests and exit before crawling
    if args.tag or args.untag or args.list_tags:
        for dev in RAW_DEVICES:
            if args.device_filter:
                if args.device_filter.lower() not in dev['device_id'].lower() and \
                   args.device_filter.lower() not in dev['nick_name'].lower():
                    continue
            if args.tag:
                # --tag may include an '=' to separate path and tag value
                tag_arg = args.tag
                if '=' in tag_arg:
                    thepath, theval = tag_arg.split('=', 1)
                else:
                    thepath, theval = tag_arg, ''
                # remove shell-escaped spaces/backslashes before normalizing
                thepath = thepath.replace('\\', '')
                tag_folder(dev['device_id'], dev['nick_name'], thepath, theval)
                print(f"Tagged {thepath} (value='{theval}') on {dev['nick_name']} ({dev['device_id']})")
            if args.untag:
                norm = normalize_path(args.untag)
                cur.execute("UPDATE api_calls SET tag='' WHERE device_id=? AND path=?", (dev['device_id'], norm))
                conn.commit()
                print(f"Removed tag from {args.untag} on {dev['nick_name']} ({dev['device_id']})")
            if args.list_tags:
                cur.execute("SELECT path,tag FROM api_calls WHERE device_id=? AND tag<>''", (dev['device_id'],))
                rows = cur.fetchall()
                print(f"Tagged paths for {dev['nick_name']} ({dev['device_id']}):")
                for r in rows:
                    print("  ", r['path'], "->", repr(r['tag']))
        conn.close()
        sys.exit(0)

    run_audit(
        start_folder=args.start_folder, 
        one_level=args.one_level, 
        device_filter=args.device_filter, 
        max_depth=args.max_depth,
        force=args.force,
        min_size=args.min_size
    )