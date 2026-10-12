import requests
import sys
import json
import argparse
import os
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
# Attempts to load iDrive session cookies directly from your local browser cache (Chrome, Firefox, Safari, Edge, Brave).
# If auto-extraction fails or no browser cookies are found, it falls back to MANUAL_FALLBACK_COOKIE.

import concurrent.futures

def get_idrive_cookies(target_host="evsweb2652.idrive.com", timeout=5.0):
    """Attempt to dynamically read active iDrive session cookies from local browser cache.

    Groups cookies by domain so matching EVSID/JSESSIONID pairs from the target EVS host are used.
    """
    def _fetch():
        import browser_cookie3
        for loader_name in ['chrome', 'firefox', 'safari', 'brave', 'edge']:
            loader = getattr(browser_cookie3, loader_name, None)
            if not loader:
                continue
            try:
                cj = loader()
                
                by_domain = {}
                for c in cj:
                    dom = getattr(c, 'domain', '').lower().lstrip('.')
                    if 'idrive.com' in dom:
                        if dom not in by_domain:
                            by_domain[dom] = {}
                        if c.name in ('EVSID', 'JSESSIONID', 'WOPI_SESSION'):
                            by_domain[dom][c.name] = c.value

                if not by_domain:
                    continue

                # Search order: target host first, then subdomains by length descending
                search_order = []
                if target_host in by_domain:
                    search_order.append(target_host)
                search_order.extend(sorted([d for d in by_domain if d != target_host], key=len, reverse=True))

                for dom in search_order:
                    cmap = by_domain[dom]
                    if 'EVSID' in cmap or 'JSESSIONID' in cmap:
                        cookie_str = "; ".join([f"{k}={v}" for k, v in cmap.items()])
                        print(f"[*] Loaded active iDrive session cookies automatically from browser ({loader_name} -> {dom}).")
                        return cookie_str
            except Exception:
                continue
        return None

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_fetch)
            return future.result(timeout=timeout)
    except Exception:
        pass
    return None

MANUAL_FALLBACK_COOKIE = ""

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
COOKIE_CACHE_FILE = os.path.join(LOG_DIR, ".idrive_cookie")

def save_cookie_cache(cookie_str):
    try:
        with open(COOKIE_CACHE_FILE, "w", encoding="utf-8") as f:
            f.write(cookie_str.strip())
    except Exception:
        pass

def load_cookie_cache():
    try:
        if os.path.exists(COOKIE_CACHE_FILE):
            with open(COOKIE_CACHE_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return content
    except Exception:
        pass
    return None

COOKIE_STR = load_cookie_cache() or get_idrive_cookies() or MANUAL_FALLBACK_COOKIE
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
from datetime import datetime, timedelta, timezone

def get_now_iso():
    """Return ISO formatted current UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()

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

# --- DEVICE ONLINE/OFFLINE & ACTIVE/INACTIVE TABLE AND HELPERS ---
cur.execute(
    '''
    CREATE TABLE IF NOT EXISTS devices (
        device_id TEXT PRIMARY KEY,
        device_name TEXT,
        online INTEGER DEFAULT 1,
        active INTEGER DEFAULT 1
    )
    '''
)
conn.commit()

# Ensure active column exists in devices table for existing databases
cur.execute("PRAGMA table_info(devices)")
dev_cols = [row['name'] for row in cur.fetchall()]
if 'active' not in dev_cols:
    cur.execute("ALTER TABLE devices ADD COLUMN active INTEGER DEFAULT 1")
    conn.commit()
    cur.execute("UPDATE devices SET active = online WHERE online IS NOT NULL")
    conn.commit()

def sync_devices_table(raw_devices=None):
    """Ensure all known devices from RAW_DEVICES and api_calls exist in devices table.
    Preserves user-configured active/inactive status choices.
    """
    if raw_devices:
        for dev in raw_devices:
            dev_id = dev.get('device_id')
            dev_name = dev.get('nick_name')
            if dev_id:
                cur.execute("SELECT device_id FROM devices WHERE device_id = ?", (dev_id,))
                if not cur.fetchone():
                    cur.execute("INSERT INTO devices (device_id, device_name, online, active) VALUES (?, ?, 1, 1)", (dev_id, dev_name))
                else:
                    cur.execute("UPDATE devices SET device_name = ? WHERE device_id = ?", (dev_name, dev_id))
    
    # Also sync any unique device_ids from api_calls that might be historical
    cur.execute("SELECT DISTINCT device_id, device_name FROM api_calls WHERE device_id IS NOT NULL AND device_id != ''")
    api_devs = cur.fetchall()
    for row in api_devs:
        dev_id = row['device_id']
        dev_name = row['device_name'] or dev_id
        cur.execute("SELECT device_id FROM devices WHERE device_id = ?", (dev_id,))
        if not cur.fetchone():
            cur.execute("INSERT INTO devices (device_id, device_name, online, active) VALUES (?, ?, 1, 1)", (dev_id, dev_name))
    conn.commit()

def get_devices_status_map():
    sync_devices_table(RAW_DEVICES if 'RAW_DEVICES' in globals() else None)
    cur.execute("SELECT device_id, device_name, online, active FROM devices")
    rows = cur.fetchall()
    res = {}
    for r in rows:
        act = r['active'] if 'active' in r.keys() and r['active'] is not None else (r['online'] if 'online' in r.keys() and r['online'] is not None else 1)
        onl = r['online'] if 'online' in r.keys() and r['online'] is not None else act
        res[r['device_id']] = {
            'name': r['device_name'],
            'online': onl,
            'active': act,
            'status_str': 'Active' if act else 'Inactive'
        }
    return res

def set_device_status(device_identifier, is_active):
    """Update device active (and online) status by device_id or device_name."""
    sync_devices_table(RAW_DEVICES if 'RAW_DEVICES' in globals() else None)
    val = 1 if is_active else 0
    # Try exact match first
    cur.execute(
        "UPDATE devices SET active = ?, online = ? WHERE LOWER(device_id) = ? OR LOWER(device_name) = ?",
        (val, val, device_identifier.lower(), device_identifier.lower())
    )
    count = cur.rowcount
    if count == 0:
        # Fall back to substring match if no exact match
        cur.execute(
            "UPDATE devices SET active = ?, online = ? WHERE LOWER(device_id) LIKE ? OR LOWER(device_name) LIKE ?",
            (val, val, f"%{device_identifier.lower()}%", f"%{device_identifier.lower()}%")
        )
        count = cur.rowcount
    conn.commit()
    try:
        print_storage_summary()
    except Exception:
        pass
    return count


# Synchronize any legacy database records where size column is 0 or NULL but response_json has API size
try:
    cur.execute("SELECT id, response_json FROM api_calls WHERE endpoint = 'getProperties' AND (size = 0 OR size IS NULL) AND response_json IS NOT NULL")
    sync_rows = cur.fetchall()
    for srow in sync_rows:
        try:
            sdata = json.loads(srow['response_json'])
            rsize = int(sdata.get('size', 0)) if sdata.get('size') not in (None, '-') else 0
            rfc = int(sdata.get('filecount', 0)) if sdata.get('filecount') not in (None, '-') else 0
            if rsize > 0:
                cur.execute("UPDATE api_calls SET size = ?, filecount = ? WHERE id = ?", (rsize, rfc, srow['id']))
        except Exception:
            pass
    conn.commit()
except Exception:
    pass

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

    size_val = None
    if isinstance(details, dict) and 'size' in details and details['size'] not in (None, '-'):
        try:
            size_val = int(details['size'])
        except Exception:
            size_val = 0

    filecount_val = None
    if isinstance(details, dict) and 'filecount' in details and details['filecount'] not in (None, '-'):
        try:
            filecount_val = int(details['filecount'])
        except Exception:
            filecount_val = 0

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
            "SELECT id, size, filecount FROM api_calls WHERE device_id=? AND path=? AND endpoint=? ORDER BY timestamp DESC LIMIT 1",
            (device_id, norm_path, endpoint)
        )
        existing = cur.fetchone()
        if existing:
            # Preserve existing non-zero size if current size_val is 0 or None
            if (size_val is None or size_val == 0) and existing['size'] and existing['size'] > 0:
                size_val = existing['size']
                filecount_val = existing['filecount']
            cur.execute(
                "UPDATE api_calls SET timestamp=?, device_name=?, size=?, filecount=?, lmd=?, response_json=?, tag=? WHERE id=?",
                (
                    get_now_iso(),
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
            get_now_iso(),
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
    global COOKIE_STR, session
    
    for attempt in range(2):
        print(f"Using COOKIE_STR: {COOKIE_STR}\n")
        try:
            r = session.post(f"{BASE_URL}/listDevices", data={'json': 'yes'}, timeout=15)
            data = r.json()
            if isinstance(data, dict) and data.get('message') == 'SUCCESS' and 'contents' in data:
                devices = []
                for item in data['contents']:
                    dev_id = item.get('device_id')
                    nick = item.get('nick_name')
                    if dev_id and nick and nick != "IDrive Photos":
                        devices.append({"device_id": dev_id, "nick_name": nick})
                # Cache valid working cookie
                save_cookie_cache(COOKIE_STR)
                return devices
        except Exception:
            pass

        if attempt == 0:
            sys.stdout.write("\n[!] The current session cookie failed authentication (session expired).\n")
            fresh_cookie = get_idrive_cookies()
            if fresh_cookie and fresh_cookie != COOKIE_STR:
                sys.stdout.write("[*] Found fresh session cookie in browser cache. Retrying authentication...\n")
                COOKIE_STR = fresh_cookie
                session.headers.update({'Cookie': COOKIE_STR})
                continue

            sys.stdout.write("--> Please open Chrome / browser and log into https://www.idrive.com to refresh your session.\n")
            if sys.stdin.isatty():
                try:
                    user_cookie = input("--> Or paste fresh COOKIE_STR here (Press Enter to exit): ").strip()
                    if user_cookie:
                        COOKIE_STR = user_cookie
                        session.headers.update({'Cookie': COOKIE_STR})
                        continue
                except (EOFError, KeyboardInterrupt):
                    pass

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
OUTPUT_FILE = os.path.join(LOG_DIR, "idrive_audit_report.txt")

class Logger(object):
    """Helper to write to both console and file."""
    def __init__(self):
        self.terminal = sys.stdout
        self.log = open(OUTPUT_FILE, "w", encoding="utf-8")

    def write(self, message):
        try:
            self.terminal.write(message)
        except BrokenPipeError:
            pass
        # Filter out progress indicators (\r) and ANSI escape sequences to keep the file clean
        if not (message.startswith('\r') or '\033[' in message):
            self.log.write(message)
            self.log.flush()

    def flush(self):
        try:
            self.terminal.flush()
        except BrokenPipeError:
            pass
        try:
            self.log.flush()
        except Exception:
            pass

sys.stdout = Logger()

def get_details(device_id, device_name, path, ignore_skip=False):
    # skip detail call if this path was checked recently
    norm = normalize_path(path)
    if not ignore_skip and should_skip(device_id, norm, endpoint='getProperties'):
        print(f"  (skipping getProperties for {norm} on {device_name} — recent entry)")
        try:
            cur.execute(
                "SELECT size, filecount, lmd FROM api_calls WHERE device_id=? AND path=? AND endpoint='getProperties' AND size > 0 ORDER BY timestamp DESC LIMIT 1",
                (device_id, norm)
            )
            cached_rec = cur.fetchone()
            if cached_rec:
                return {"size": cached_rec['size'], "filecount": cached_rec['filecount'], "lmd": cached_rec['lmd']}
        except Exception:
            pass
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

    # Re-fetch properties for current_path at starting depth to update size, lmd, and timestamp
    if depth == 1:
        get_details(device_id, device_name, norm, ignore_skip=ignore_skip)

    # If starting a forced or targeted scan (depth 1), reset existing sizes for immediate children to 0.
    # This preserves data from deeper historical scans while ensuring deleted items at this level are correctly reflected.
    if depth == 1 and ignore_skip:
        child_pattern = norm.rstrip('/') + '/%'
        exclude_pattern = norm.rstrip('/') + '/%/%'
        cur.execute(
            "UPDATE api_calls SET size=0, filecount=0 WHERE device_id=? AND path LIKE ? AND path NOT LIKE ?",
            (device_id, child_pattern, exclude_pattern)
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
            now_iso = get_now_iso()
            cur.execute(
                'UPDATE api_calls SET drilled=1, timestamp=? WHERE device_id=? AND path=? AND (endpoint=? OR endpoint=?)',
                (now_iso, device_id, norm, 'browseFolder', 'getProperties')
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
            (get_now_iso(), device_id, device_name, norm, tag_value)
        )

    conn.commit()
    try:
        print_storage_summary()
    except Exception:
        pass


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
        if last.tzinfo is not None:
            last = last.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        if SKIP_DEBUG:
            print(f"should_skip: bad timestamp '{row['timestamp']}'")
        return False
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    delta = now_utc - last
    result = delta < timedelta(hours=hours)
    if SKIP_DEBUG:
        print(f"should_skip: {endpoint} {norm} ({device_id}) last={last.isoformat()} delta={delta} skip={result}")
    return result


def print_storage_summary(min_size=MIN_SIZE_GB, to_console=False, order_by='size', show_tree=False):
    """Summarize storage usage per device.
    
    order_by options:
      - 'size': Largest folders and devices first (default)
      - 'recent': Most recently updated/scanned folders and devices first
      - 'oldest': Oldest updated/scanned folders and devices first
    
    Writes:
      - One-line per device summary to logs/idrive_storage_summary.log
      - Full folder hierarchy to logs/idrive_storage_use_by_device.log
    """
    # Fetch all getProperties rows with non-zero size, ordered by timestamp ascending so latest scan overwrites
    cur.execute(
        """
        SELECT device_id, device_name, path, size, tag, timestamp, drilled, lmd
        FROM api_calls
        WHERE endpoint = 'getProperties' AND size IS NOT NULL AND size >= 0
        ORDER BY timestamp ASC
        """
    )
    rows = cur.fetchall()
    
    devices = {}
    for row in rows:
        dev_id = row['device_id']
        dev_name = row['device_name']
        if dev_id not in devices:
            devices[dev_id] = {'name': dev_name, 'folders': {}}
        devices[dev_id]['folders'][row['path']] = dict(row)
        
    if not devices:
        return
        
    order_labels = {
        'recent': 'Ordered by: Most Recent Updates',
        'oldest': 'Ordered by: Oldest Updates',
        'size': 'Ordered by: Size / Status'
    }
    order_label = order_labels.get(order_by, f"Ordered by: {order_by}")

    lines = []
    lines.append("\n" + "=" * 180)
    lines.append(f"{f'IDRIVE STORAGE USE BY DEVICE ({order_label})':^180}")
    lines.append("=" * 180)
    
    def is_drive_root(path):
        p = path.strip('/')
        return len(p) <= 1 or p.upper() in ('C', 'D', 'E', 'F', 'VOLUMES')

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    dev_summaries = []

    for dev_id, dev_info in sorted(devices.items(), key=lambda x: x[1]['name']):
        folders = dev_info['folders']
        folders_sorted = sorted(folders.values(), key=lambda x: len(x['path']))
        
        drilled_paths = {path for path, f in folders.items() if f.get('drilled') and f['drilled'] > 0}
        top_level_paths = set()
        display_folders = []
        
        for f in folders_sorted:
            if is_drive_root(f['path']) and len(folders_sorted) > 1:
                continue
            is_child_of_top = any(f['path'].startswith(tl + '/') for tl in top_level_paths)
            is_child_of_drilled = any(f['path'].startswith(dp + '/') for dp in drilled_paths)
            
            if not is_child_of_top:
                top_level_paths.add(f['path'])
                display_folders.append(f)
            elif (f.get('drilled') and f['drilled'] > 0) or (f.get('tag') and f['tag'] != '' and f['tag'] != '0') or is_child_of_drilled:
                display_folders.append(f)

        if not display_folders:
            continue

        def get_tree_sorted_folders(folders_list):
            folder_map = {f['path']: f for f in folders_list}
            children_map = {f['path']: [] for f in folders_list}
            roots = []

            for f in folders_list:
                ancestors = [p for p in folder_map if f['path'].startswith(p + '/')]
                if ancestors:
                    closest_parent = max(ancestors, key=len)
                    children_map[closest_parent].append(f)
                else:
                    roots.append(f)

            def folder_sort_key(x):
                ts = x.get('timestamp') or ''
                sz = x.get('size') if x.get('size') is not None else 0
                if order_by == 'recent':
                    return (ts, sz)
                elif order_by == 'oldest':
                    return (ts if ts else '0000-00-00', -sz)
                else:
                    return (sz, ts)

            rev = (order_by != 'oldest')
            roots.sort(key=folder_sort_key, reverse=rev)
            for p_path in children_map:
                children_map[p_path].sort(key=folder_sort_key, reverse=rev)

            res = []
            def traverse(f, ancestor_tags):
                f_tag = (f.get('tag') or '').strip().lower()
                is_same_tag_child = False
                for anc_tag in ancestor_tags:
                    if anc_tag and f_tag == anc_tag:
                        is_same_tag_child = True
                        break

                if not is_same_tag_child:
                    res.append(f)

                next_ancestor_tags = list(ancestor_tags)
                if f_tag and f_tag != '0':
                    next_ancestor_tags.append(f_tag)

                for child in children_map[f['path']]:
                    traverse(child, next_ancestor_tags)

            for root in roots:
                traverse(root, [])

            return res

        display_folders = get_tree_sorted_folders(display_folders)
        total_size = sum(f['size'] for f in display_folders if f['path'] in top_level_paths)
        
        dev_summaries.append({
            'id': dev_id,
            'name': dev_info['name'],
            'total_size': total_size,
            'display_folders': display_folders,
            'top_level_paths': top_level_paths,
            'drilled_paths': drilled_paths
        })
        
    dev_status_map = get_devices_status_map()
    dev_lmd_info = {}
    dev_scan_info = {}
    for dev_id in devices:
        cur.execute(
            "SELECT path, lmd FROM api_calls WHERE device_id = ? AND lmd IS NOT NULL AND lmd != '' ORDER BY lmd DESC LIMIT 1",
            (dev_id,)
        )
        lr = cur.fetchone()
        if lr and lr['lmd']:
            l_ts = lr['lmd'].replace('T', ' ')[:19]
            l_path = lr['path']
            dev_lmd_info[dev_id] = {'lmd': lr['lmd'], 'lmd_str': l_ts, 'path': l_path}
        else:
            dev_lmd_info[dev_id] = {'lmd': '', 'lmd_str': '[unknown]', 'path': ''}

        cur.execute(
            "SELECT MAX(timestamp) as max_ts, MIN(timestamp) as min_ts FROM api_calls WHERE device_id = ? AND timestamp IS NOT NULL AND timestamp != ''",
            (dev_id,)
        )
        ts_r = cur.fetchone()
        max_ts = ts_r['max_ts'] if ts_r and ts_r['max_ts'] else ''
        min_ts = ts_r['min_ts'] if ts_r and ts_r['min_ts'] else ''
        max_ts_str = max_ts.replace('T', ' ')[:16] if max_ts else '[never]'
        dev_scan_info[dev_id] = {
            'latest_scan': max_ts,
            'latest_scan_str': max_ts_str,
            'oldest_scan': min_ts
        }

    for ds in dev_summaries:
        dev_id = ds['id']
        ds['latest_scan'] = dev_scan_info.get(dev_id, {}).get('latest_scan', '')
        ds['latest_scan_str'] = dev_scan_info.get(dev_id, {}).get('latest_scan_str', '[never]')

    if order_by == 'recent':
        dev_summaries.sort(
            key=lambda x: (
                dev_status_map.get(x['id'], {}).get('active', 1),
                x.get('latest_scan') or '',
                x['total_size']
            ),
            reverse=True
        )
    elif order_by == 'oldest':
        dev_summaries.sort(
            key=lambda x: (
                -dev_status_map.get(x['id'], {}).get('active', 1),
                x.get('latest_scan') or '0000-00-00',
                -x['total_size']
            ),
            reverse=False
        )
    else:  # 'size' (default)
        dev_summaries.sort(
            key=lambda x: (
                dev_status_map.get(x['id'], {}).get('active', 1),
                dev_lmd_info.get(x['id'], {}).get('lmd', ''),
                x['total_size']
            ),
            reverse=True
        )
    
    for ds in dev_summaries:
        dev_id = ds['id']
        status_info = dev_status_map.get(dev_id, {'status_str': 'Active', 'active': 1})
        status_str = status_info['status_str']
        total_gb = ds['total_size'] / (1024**3)
        
        info = dev_lmd_info.get(dev_id, {'lmd_str': '[unknown]', 'path': ''})
        l_str = info['lmd_str']
        l_path = info['path']
        if l_path:
            if len(l_path) > 40:
                l_path = "..." + l_path[-37:]
            mod_display = f"{l_str} ({l_path})"
        else:
            mod_display = l_str

        last_scan_str = ds.get('latest_scan_str', '[never]')
        lines.append(
            f"Device: {ds['name']:<20} | Total Scanned Size: {total_gb:>8.2f} GB | Last Scanned: {last_scan_str:<16} | Status: {status_str:<8} | Last Mod: {mod_display}"
        )
        if ds['display_folders']:
            show_all_top = total_gb < min_size
            for f in ds['display_folders']:
                f_gb = f['size'] / (1024**3)
                is_drilled = bool(f.get('drilled') and f['drilled'] > 0)
                is_tagged = bool(f.get('tag') and f['tag'] != '' and f['tag'] != '0')
                is_top_level = f['path'] in ds.get('top_level_paths', set())
                is_child_of_drilled = any(f['path'].startswith(dp + '/') for dp in ds.get('drilled_paths', set()))
                if not (f_gb >= min_size or is_drilled or is_tagged or show_all_top or is_top_level or is_child_of_drilled):
                    continue

                if is_top_level:
                    prefix = "  - "
                    rel_depth = 0
                else:
                    parents = [tl for tl in ds.get('top_level_paths', set()) if f['path'].startswith(tl + '/')]
                    if parents:
                        parent_path = min(parents, key=len)
                        rel_depth = max(1, f['path'].count('/') - parent_path.count('/'))
                    else:
                        rel_depth = max(1, f['path'].count('/') - 1)
                    prefix = "  " + "  " * rel_depth + "└─ "
                path_str = f['path']
                if len(prefix + path_str) > 90:
                    path_str = "..." + path_str[-(87 - len(prefix)):]
                full_path_str = f"{prefix}{path_str}"

                ts_raw = f['timestamp'] if f['timestamp'] else ''
                ts_str = ts_raw.replace('T', ' ')[:16] if ts_raw else '[never]'

                stale_str = ''
                if ts_raw:
                    try:
                        dt = datetime.fromisoformat(ts_raw)
                        if dt.tzinfo is not None:
                            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                        if (now - dt) > timedelta(days=14):
                            stale_str = ' [Needs Refresh]'
                    except Exception:
                        pass

                drilled_str = f" | Drilled: {ts_str}{stale_str}" if (f.get('drilled') and f['drilled'] > 0) else f" | Audited: {ts_str}"
                tag_suffix = f" | Tag: {f['tag']}" if f['tag'] else ""
                size_indent = "  " * rel_depth
                lines.append(f"  {full_path_str:<90} | {size_indent}{f_gb:>10.2f} GB{drilled_str}{tag_suffix}")
        else:
            lines.append(f"  - (no folders >= {min_size:.2f} GB)")
    lines.append("=" * 180)
    tree_table_content = "\n".join(lines) + "\n"
    tree_log_file = os.path.join(LOG_DIR, "idrive_storage_use_by_device.log")
    with open(tree_log_file, "w", encoding="utf-8") as f:
        f.write(tree_table_content)

    # --- BUILD COMPACT ONE-LINE-PER-DEVICE SUMMARY TABLE ---
    summary_lines = []
    summary_lines.append("\n" + "=" * 155)
    summary_lines.append(f"{f'IDRIVE STORAGE SUMMARY ({order_label})':^155}")
    summary_lines.append("=" * 155)
    summary_lines.append(f"{'No.':<4} | {'Device Name':<22} | {'Scanned Size':>12} | {'Last Scanned':<16} | {'Status':<9} | {'Last Modified (Folder)':<50} | {'Device ID':<22}")
    summary_lines.append("-" * 155)

    total_acct_size = 0.0
    active_count = 0
    inactive_count = 0

    for idx, ds in enumerate(dev_summaries, 1):
        dev_id = ds['id']
        status_info = dev_status_map.get(dev_id, {'status_str': 'Active', 'active': 1})
        status_str = status_info['status_str']
        if status_info.get('active', 1):
            active_count += 1
        else:
            inactive_count += 1

        total_gb = ds['total_size'] / (1024**3)
        total_acct_size += total_gb

        info = dev_lmd_info.get(dev_id, {'lmd_str': '[unknown]', 'path': ''})
        l_str = info['lmd_str']
        l_path = info['path']
        if l_path:
            if len(l_path) > 30:
                l_path = "..." + l_path[-27:]
            mod_display = f"{l_str} ({l_path})"
        else:
            mod_display = l_str

        last_scan_str = ds.get('latest_scan_str', '[never]')
        summary_lines.append(
            f"{idx:<4} | {ds['name']:<22} | {total_gb:>9.2f} GB | {last_scan_str:<16} | {status_str:<9} | {mod_display:<50} | {dev_id:<22}"
        )

    summary_lines.append("-" * 155)
    summary_lines.append(
        f"TOTAL ACCOUNT STORAGE: {total_acct_size:.2f} GB Across {len(dev_summaries)} Devices (Active: {active_count}, Inactive: {inactive_count})"
    )
    summary_lines.append("=" * 155)
    summary_table_content = "\n".join(summary_lines) + "\n"

    summary_log_file = os.path.join(LOG_DIR, "idrive_storage_summary.log")
    with open(summary_log_file, "w", encoding="utf-8") as f:
        f.write(summary_table_content)

    if to_console:
        if show_tree:
            print(tree_table_content)
        else:
            print(summary_table_content)
    else:
        print(f"\n[*] IDRIVE STORAGE SUMMARY (One line per device) written to: {summary_log_file}")
        print(f"[*] Detailed hierarchy written to: {tree_log_file}")
    return tree_table_content if show_tree else summary_table_content


def run_interactive(min_size=MIN_SIZE_GB, order_by='size'):
    """Run interactive loop supporting Storage Management (default) and Device Management modes."""
    current_view = 'storage'
    current_order = order_by

    while True:
        if current_view == 'storage':
            print("\n" + "=" * 165)
            print(f"{'IDRIVE AUDIT INTERACTIVE DASHBOARD':^165}")
            print(f"{'[S] Storage Management (Active)   |   [D] Device Management':^165}")
            print("=" * 165)

            # Print storage usage by device
            print_storage_summary(min_size=min_size, order_by=current_order)

            status_map = get_devices_status_map()

            def row_sort_key(r):
                dev_id = r['device_id']
                online = status_map.get(dev_id, {}).get('online', 0)
                dev_name = (r['device_name'] or '').lower()
                path_val = (r['path'] or '').lower()
                ts = r['timestamp'] or ''
                sz = r['size'] if r['size'] is not None else 0
                if current_order == 'recent':
                    return (ts, sz, online, dev_name, path_val)
                elif current_order == 'oldest':
                    return (ts if ts else '0000-00-00', -sz, -online, dev_name, path_val)
                else:
                    return (-online, -sz, dev_name, path_val)

            # Fetch all drilled folders (which have drilled > 0 in database)
            cur.execute(
                """
                SELECT device_id, device_name, path, size, filecount, tag, active, lmd, timestamp
                FROM api_calls
                WHERE endpoint = 'getProperties' AND drilled > 0
                """
            )
            drilled_raw = cur.fetchall()
            drilled_rows = sorted(drilled_raw, key=row_sort_key, reverse=(current_order == 'recent'))

            # Fetch all tagged folders (excluding drilled folders)
            cur.execute(
                """
                SELECT device_id, device_name, path, size, filecount, tag, active, lmd, timestamp
                FROM api_calls
                WHERE endpoint = 'getProperties' AND tag IS NOT NULL AND tag != '' AND tag != '0' AND (drilled IS NULL OR drilled = 0)
                """
            )
            tagged_raw = cur.fetchall()
            tagged_rows = sorted(tagged_raw, key=row_sort_key, reverse=(current_order == 'recent'))

            # Fetch untagged folders (excluding drilled folders)
            cur.execute(
                """
                SELECT device_id, device_name, path, size, filecount, tag, active, lmd, timestamp
                FROM api_calls
                WHERE endpoint = 'getProperties' AND size IS NOT NULL AND size > 0 AND (tag IS NULL OR tag = '' OR tag = '0') AND (drilled IS NULL OR drilled = 0)
                """
            )
            untagged_raw = cur.fetchall()
            untagged_rows = sorted(untagged_raw, key=row_sort_key, reverse=(current_order == 'recent'))[:10]

            rows = list(drilled_rows) + list(tagged_rows) + list(untagged_rows)

            print("\n" + "=" * 165)
            order_desc = {'recent': 'Most Recent Updates', 'oldest': 'Oldest Updates', 'size': 'Size'}.get(current_order, current_order)
            print(f"{f'IDRIVE ACCOUNT STORAGE MANAGEMENT (Sorted by: {order_desc})':^165}")
            print("=" * 165)

            current_idx = 1
            header_str = f"{'No.':<4} | {'Device':<18} | {'Path':<45} | {'Size (GB)':>10} | {'Last Scanned':<16} | {'Last Modified':<19} | {'Tag':<16} | {'Device Status':<13}"

            if drilled_rows:
                print(f"\n--- DRILLED FOLDERS (Expanded into subfolders) ---")
                print(header_str)
                print("-" * 165)
                for row in drilled_rows:
                    size_val = row['size'] if row['size'] is not None else 0
                    size_gb = size_val / (1024**3)
                    tag_str = row['tag'] if row['tag'] else "[none]"
                    dev_id = row['device_id']
                    status_str = status_map.get(dev_id, {}).get('status_str', 'Offline')
                    dev_name = (row['device_name'] or '')[:18]
                    path_str = row['path']
                    if len(path_str) > 43:
                        path_str = "..." + path_str[-40:]
                    lmd_raw = row['lmd'] if 'lmd' in row.keys() and row['lmd'] else ''
                    lmd_str = lmd_raw.replace('T', ' ')[:19] if lmd_raw else "[unknown]"
                    ts_raw = row['timestamp'] if 'timestamp' in row.keys() and row['timestamp'] else ''
                    ts_str = ts_raw.replace('T', ' ')[:16] if ts_raw else "[never]"
                    print(f"{current_idx:<4} | {dev_name:<18} | {path_str:<45} | {size_gb:>10.2f} | {ts_str:<16} | {lmd_str:<19} | {tag_str:<16} | {status_str:<13}")
                    current_idx += 1
                print("-" * 165)

            if tagged_rows:
                print(f"\n--- TAGGED FOLDERS (Not drilled down) ---")
                print(header_str)
                print("-" * 165)
                for row in tagged_rows:
                    size_val = row['size'] if row['size'] is not None else 0
                    size_gb = size_val / (1024**3)
                    tag_str = row['tag']
                    dev_id = row['device_id']
                    status_str = status_map.get(dev_id, {}).get('status_str', 'Offline')
                    dev_name = (row['device_name'] or '')[:18]
                    path_str = row['path']
                    if len(path_str) > 43:
                        path_str = "..." + path_str[-40:]
                    lmd_raw = row['lmd'] if 'lmd' in row.keys() and row['lmd'] else ''
                    lmd_str = lmd_raw.replace('T', ' ')[:19] if lmd_raw else "[unknown]"
                    ts_raw = row['timestamp'] if 'timestamp' in row.keys() and row['timestamp'] else ''
                    ts_str = ts_raw.replace('T', ' ')[:16] if ts_raw else "[never]"
                    print(f"{current_idx:<4} | {dev_name:<18} | {path_str:<45} | {size_gb:>10.2f} | {ts_str:<16} | {lmd_str:<19} | {tag_str:<16} | {status_str:<13}")
                    current_idx += 1
                print("-" * 165)

            if untagged_rows:
                print(f"\n--- UNTAGGED FOLDERS (Not drilled down - Top 10 by sort order) ---")
                print(header_str)
                print("-" * 165)
                for row in untagged_rows:
                    size_val = row['size'] if row['size'] is not None else 0
                    size_gb = size_val / (1024**3)
                    tag_str = "[none]"
                    dev_id = row['device_id']
                    status_str = status_map.get(dev_id, {}).get('status_str', 'Offline')
                    dev_name = (row['device_name'] or '')[:18]
                    path_str = row['path']
                    if len(path_str) > 43:
                        path_str = "..." + path_str[-40:]
                    lmd_raw = row['lmd'] if 'lmd' in row.keys() and row['lmd'] else ''
                    lmd_str = lmd_raw.replace('T', ' ')[:19] if lmd_raw else "[unknown]"
                    ts_raw = row['timestamp'] if 'timestamp' in row.keys() and row['timestamp'] else ''
                    ts_str = ts_raw.replace('T', ' ')[:16] if ts_raw else "[never]"
                    print(f"{current_idx:<4} | {dev_name:<18} | {path_str:<45} | {size_gb:>10.2f} | {ts_str:<16} | {lmd_str:<19} | {tag_str:<16} | {status_str:<13}")
                    current_idx += 1
                print("-" * 165)

            print(f"Options: Select folder (1-{len(rows)}), enter path or keyword search (e.g. '/Pictures'), 'D' for Device Mgmt, 'O' to change sort order ({current_order}), 'V' to view summary, 'r' to refresh, 'q' to quit.")
            choice = input("Choice: ").strip()

            if not choice:
                continue

            c_lower = choice.lower()
            if c_lower == 'q':
                print("Exiting interactive session.")
                break
            elif c_lower == 'r':
                continue
            elif c_lower in ('d', 'dm', 'device'):
                current_view = 'device'
                continue
            elif c_lower in ('s', 'sm', 'storage'):
                current_view = 'storage'
                continue
            elif c_lower in ('o', 'order', 'sort'):
                print(f"\nSelect Table Sort Order:")
                print(f"  [1] Most Recent Updates (newest scans first)")
                print(f"  [2] Oldest Updates (oldest scans first)")
                print(f"  [3] Size (largest folders and devices first)")
                o_choice = input(f"Choice [1-3, current: {current_order}]: ").strip().lower()
                if o_choice in ('1', 'recent', 'r'):
                    current_order = 'recent'
                    print("Sort order updated to: Most Recent Updates")
                elif o_choice in ('2', 'oldest', 'o'):
                    current_order = 'oldest'
                    print("Sort order updated to: Oldest Updates")
                elif o_choice in ('3', 'size', 's'):
                    current_order = 'size'
                    print("Sort order updated to: Size")
                continue
            elif c_lower in ('v', 'view', 'summary'):
                print_storage_summary(min_size=min_size, to_console=True, order_by=current_order, show_tree=False)
                continue
            elif c_lower in ('t', 'tree'):
                print_storage_summary(min_size=min_size, to_console=True, order_by=current_order, show_tree=True)
                continue

            if choice.isdigit() and 1 <= int(choice) <= len(rows):
                selected_row = rows[int(choice) - 1]
                manage_folder_interactive(selected_row, min_size, order_by=current_order)
            else:
                # Search database for matching folder path
                cur.execute(
                    """
                    SELECT device_id, device_name, path, size, filecount, tag, active, lmd, drilled, timestamp
                    FROM api_calls
                    WHERE endpoint = 'getProperties' AND LOWER(path) LIKE ?
                    ORDER BY size DESC
                    """,
                    (f"%{c_lower}%",)
                )
                search_matches = cur.fetchall()
                if len(search_matches) == 1:
                    manage_folder_interactive(search_matches[0], min_size, order_by=current_order)
                elif len(search_matches) > 1:
                    print(f"\nFound {len(search_matches)} matching folders:")
                    print(f"{'No.':<4} | {'Device':<20} | {'Path':<55} | {'Size (GB)':>10} | {'Tag':<15}")
                    print("-" * 110)
                    for m_idx, m_row in enumerate(search_matches, 1):
                        m_sz = (m_row['size'] or 0) / (1024**3)
                        m_tag = m_row['tag'] if m_row['tag'] else "[none]"
                        m_path = m_row['path']
                        if len(m_path) > 53:
                            m_path = "..." + m_path[-50:]
                        print(f"{m_idx:<4} | {m_row['device_name'][:20]:<20} | {m_path:<55} | {m_sz:>10.2f} | {m_tag:<15}")
                    print("-" * 110)
                    sel_match = input(f"Select matching folder (1-{len(search_matches)}, or Enter to cancel): ").strip()
                    if sel_match.isdigit() and 1 <= int(sel_match) <= len(search_matches):
                        manage_folder_interactive(search_matches[int(sel_match) - 1], min_size, order_by=current_order)
                else:
                    print(f"No folder found matching '{choice}'. Enter a number 1-{len(rows)}, a path search, or 'D' for Device Management.")

        elif current_view == 'device':
            print("\n" + "=" * 155)
            print(f"{'IDRIVE AUDIT INTERACTIVE DASHBOARD':^155}")
            print(f"{'[S] Storage Management   |   [D] Device Management (Active)':^155}")
            print("=" * 155)

            status_map = get_devices_status_map()

            # Compute total scanned size per device from DB
            cur.execute(
                """
                SELECT device_id, SUM(size) as total_size
                FROM api_calls
                WHERE endpoint = 'getProperties' AND size IS NOT NULL AND size > 0
                GROUP BY device_id
                """
            )
            size_map = {r['device_id']: r['total_size'] for r in cur.fetchall()}

            dev_lmd_info = {}
            for d_id in status_map:
                cur.execute(
                    "SELECT path, lmd FROM api_calls WHERE device_id = ? AND lmd IS NOT NULL AND lmd != '' ORDER BY lmd DESC LIMIT 1",
                    (d_id,)
                )
                lr = cur.fetchone()
                if lr and lr['lmd']:
                    l_ts = lr['lmd'].replace('T', ' ')[:19]
                    l_path = lr['path']
                    dev_lmd_info[d_id] = {'lmd': lr['lmd'], 'lmd_str': l_ts, 'path': l_path}
                else:
                    dev_lmd_info[d_id] = {'lmd': '', 'lmd_str': '[unknown]', 'path': ''}

            dev_scan_map = {}
            for d_id in status_map:
                cur.execute(
                    "SELECT MAX(timestamp) as max_ts FROM api_calls WHERE device_id = ? AND timestamp IS NOT NULL AND timestamp != ''",
                    (d_id,)
                )
                ts_r = cur.fetchone()
                max_ts = ts_r['max_ts'] if ts_r and ts_r['max_ts'] else ''
                dev_scan_map[d_id] = max_ts.replace('T', ' ')[:16] if max_ts else '[never]'

            dev_list = sorted(
                status_map.items(),
                key=lambda x: (
                    x[1]['online'],
                    dev_lmd_info.get(x[0], {}).get('lmd', ''),
                    size_map.get(x[0], 0)
                ),
                reverse=True
            )

            print(f"\n--- DEVICE MANAGEMENT ---")
            print(f"{'No.':<4} | {'Device Name':<20} | {'Device ID':<22} | {'Status':<9} | {'Last Scanned':<17} | {'Last Modified (Folder)':<50} | {'Scanned Size':>12}")
            print("-" * 155)
            for idx, (d_id, d_info) in enumerate(dev_list, 1):
                sz_gb = size_map.get(d_id, 0) / (1024**3)
                info = dev_lmd_info.get(d_id, {'lmd_str': '[unknown]', 'path': ''})
                l_str = info['lmd_str']
                l_path = info['path']
                if l_path:
                    if len(l_path) > 30:
                        l_path = "..." + l_path[-27:]
                    mod_display = f"{l_str} ({l_path})"
                else:
                    mod_display = l_str
                s_ts = dev_scan_map.get(d_id, '[never]')
                print(f"{idx:<4} | {d_info['name']:<20} | {d_id:<22} | {d_info['status_str']:<9} | {s_ts:<17} | {mod_display:<50} | {sz_gb:>9.2f} GB")
            print("-" * 155)

            print(f"Options: Select device (1-{len(dev_list)}) to view options / drill down, 'S' for Storage Management, 'r' to refresh, 'q' to quit.")
            choice = input("Choice: ").strip().lower()

            if choice == 'q':
                print("Exiting interactive session.")
                break
            elif choice == 'r':
                continue
            elif choice in ('s', 'sm', 'storage'):
                current_view = 'storage'
                continue
            elif choice in ('d', 'dm', 'device'):
                current_view = 'device'
                continue

            if choice.isdigit() and 1 <= int(choice) <= len(dev_list):
                sel_id, sel_info = dev_list[int(choice) - 1]
                manage_device_interactive(sel_id, sel_info['name'], min_size)
            else:
                print(f"Invalid choice. Please enter a device number 1-{len(dev_list)}, or 'S' for Storage Management.")


def manage_device_interactive(device_id, device_name, min_size):
    """Sub-menu to manage a specific selected device (drill down / audit or toggle status)."""
    while True:
        status_map = get_devices_status_map()
        dev_info = status_map.get(device_id, {'name': device_name, 'online': 1, 'status_str': 'Online'})
        
        # Calculate total scanned size for this device from DB
        cur.execute(
            "SELECT SUM(size) as total_size FROM api_calls WHERE device_id = ? AND endpoint = 'getProperties' AND size IS NOT NULL AND size > 0",
            (device_id,)
        )
        s_row = cur.fetchone()
        dev_size_bytes = s_row['total_size'] if (s_row and s_row['total_size']) else 0
        dev_size_gb = dev_size_bytes / (1024**3)

        print("\n" + "-" * 80)
        print(f"Selected Device: {dev_info['name']} ({device_id})")
        print(f"  Status:       {dev_info['status_str']}")
        print(f"  Scanned Size: {dev_size_gb:.2f} GB")
        print("-" * 80)
        print("Actions:")
        print("  1. Drill Down / Audit Device (discover top-level folders & sizes)")
        print(f"  2. Toggle Active/Inactive status (Current: {dev_info['status_str']})")
        print("  3. Purge / Delete device audit records from database")
        print("  4. Go Back")
        
        act = input("Choose action (1-4): ").strip()
        if not act or act == '4':
            break
        elif act == '1':
            print(f"\nScanning / drilling top-level folders on {dev_info['name']}...")
            # Run crawl on root "/" with min_size_gb=0.0 so all folders (even small ones) are discovered
            crawl(device_id, dev_info['name'], "/", depth=1, max_depth=1, ignore_skip=True, min_size_gb=0.0)
            print(f"Completed scanning {dev_info['name']}.")
            try:
                print_storage_summary(min_size=min_size)
            except Exception:
                pass
            
            # Fetch all scanned folders for this device from DB
            cur.execute(
                """
                SELECT device_id, device_name, path, size, filecount, tag, active, lmd, drilled
                FROM api_calls
                WHERE device_id = ? AND endpoint = 'getProperties' AND size IS NOT NULL
                ORDER BY path
                """,
                (device_id,)
            )
            dev_folders = cur.fetchall()
            if dev_folders:
                print(f"\nFolders discovered on {dev_info['name']}:")
                print(f"{'No.':<4} | {'Path':<55} | {'Size (GB)':>10} | {'Drilled':<7} | {'Tag':<15}")
                print("-" * 100)
                for f_idx, f_row in enumerate(dev_folders, 1):
                    f_sz = (f_row['size'] or 0) / (1024**3)
                    f_drilled = "Yes" if f_row['drilled'] else "No"
                    f_tag = f_row['tag'] if f_row['tag'] else "[none]"
                    f_path = f_row['path']
                    if len(f_path) > 53:
                        f_path = "..." + f_path[-50:]
                    print(f"{f_idx:<4} | {f_path:<55} | {f_sz:>10.2f} | {f_drilled:<7} | {f_tag:<15}")
                print("-" * 100)
                f_choice = input(f"Select folder number (1-{len(dev_folders)}) to manage, or press Enter to return: ").strip()
                if f_choice.isdigit() and 1 <= int(f_choice) <= len(dev_folders):
                    selected_folder = dev_folders[int(f_choice) - 1]
                    manage_folder_interactive(selected_folder, min_size)
        elif act == '2':
            new_active = 0 if dev_info['active'] else 1
            new_status_str = "Active" if new_active else "Inactive"
            set_device_status(device_id, new_active)
            print(f"\n[+] Set device '{dev_info['name']}' status to: {new_status_str}")
        elif act == '3':
            confirm = input(f"Are you sure you want to purge all audit records for '{dev_info['name']}' from database? (y/N): ").strip().lower()
            if confirm == 'y':
                cur.execute("DELETE FROM api_calls WHERE device_id = ?", (device_id,))
                cur.execute("DELETE FROM devices WHERE device_id = ?", (device_id,))
                conn.commit()
                print(f"\n[+] Purged device '{dev_info['name']}' and its audit records from database.")
                try:
                    print_storage_summary(min_size=min_size)
                except Exception:
                    pass
                break



def manage_folder_interactive(row, min_size, order_by='size'):
    """Sub-menu to manage a specific selected folder."""
    device_id = row['device_id']
    device_name = row['device_name']
    path = row['path']
    
    while True:
        # Retrieve the latest details for this path from DB
        cur.execute(
            """
            SELECT size, filecount, tag, drilled, active, lmd
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
        lmd_raw = current['lmd'] if 'lmd' in current.keys() and current['lmd'] else ''
        lmd_str = lmd_raw.replace('T', ' ')[:19] if lmd_raw else "[unknown]"
        
        print("\n" + "-" * 80)
        print(f"Selected Folder Details:")
        print(f"  Device:   {device_name} ({device_id})")
        print(f"  Path:     {path}")
        print(f"  Size:     {size_gb:.2f} GB ({files} files)")
        print(f"  Last Mod: {lmd_str}")
        print(f"  Tag:      {tag}")
        print(f"  Drilled:  {'Yes' if is_drilled else 'No'}")
        print(f"  Active:   {'Yes' if is_active else 'No'}")
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
            try:
                print_storage_summary(min_size=min_size, order_by=order_by)
            except Exception:
                pass
        elif act == '2':
            new_tag = input("Enter tag value (press Enter to clear tag): ").strip()
            tag_folder(device_id, device_name, path, new_tag)
            print(f"Successfully updated tag to: {new_tag if new_tag else '[none]'}")
            try:
                print_storage_summary(min_size=min_size, order_by=order_by)
            except Exception:
                pass
        elif act == '3':
            new_active = 0 if is_active else 1
            cur.execute(
                "UPDATE api_calls SET active = ? WHERE device_id = ? AND path = ?",
                (new_active, device_id, path)
            )
            conn.commit()
            print(f"Successfully toggled active status to: {'Yes' if new_active else 'No'}")
            try:
                print_storage_summary(min_size=min_size, order_by=order_by)
            except Exception:
                pass



def manage_devices_interactive(standalone=False):
    """Interactive menu to view and toggle device Active/Inactive status."""
    while True:
        status_map = get_devices_status_map()
        dev_list = sorted(status_map.items(), key=lambda x: x[1]['name'])
        if not dev_list:
            print("\nNo devices found.")
            break
        
        print("\n" + "=" * 85)
        print(f"{'DEVICE STATUS MANAGEMENT':^85}")
        print("=" * 85)
        print(f"{'No.':<4} | {'Device Name':<30} | {'Device ID':<30} | {'Status':<10}")
        print("-" * 85)
        for idx, (d_id, d_info) in enumerate(dev_list, 1):
            print(f"{idx:<4} | {d_info['name']:<30} | {d_id:<30} | {d_info['status_str']:<10}")
        print("-" * 85)
        exit_hint = "press Enter to exit" if standalone else "press Enter / 'b' to go back"
        print(f"Enter 1-{len(dev_list)} to toggle device status (Active/Inactive), or {exit_hint}.")
        try:
            choice = input("Choice: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            break
        if not choice or choice in ('b', 'q'):
            break
        if choice.isdigit() and 1 <= int(choice) <= len(dev_list):
            sel_id, sel_info = dev_list[int(choice) - 1]
            new_active = 0 if sel_info['active'] else 1
            new_status_str = "Active" if new_active else "Inactive"
            set_device_status(sel_id, new_active)
            print(f"\n[+] Set device '{sel_info['name']}' status to: {new_status_str}")
        else:
            print(f"Invalid choice. Please enter a number between 1 and {len(dev_list)}.")


def run_audit(start_folder=None, one_level=False, device_filter=None, max_depth=MAX_DEPTH, force=False, min_size=MIN_SIZE_GB, order_by='size', include_inactive=False):
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
        order_by: sorting order for final summary table ('recent', 'oldest', or 'size').
        include_inactive: when True, inactive devices are also audited (default False).
    """
    print(f"\n{'IDRIVE RECURSIVE ACCOUNT AUDIT':^85}")
    print(f"{'Folder Hierarchy':<50} | {'Size':>13} | {'Files':>10}")
    print("-" * 85)
    
    status_map = get_devices_status_map()

    for dev in RAW_DEVICES:
        if device_filter:
            if device_filter.lower() not in dev['device_id'].lower() and \
               device_filter.lower() not in dev['nick_name'].lower():
                continue
        elif not include_inactive and not status_map.get(dev['device_id'], {}).get('active', 1):
            print(f"\nDEVICE: {dev['nick_name']} ({dev['device_id']}) - [INACTIVE: Skipped]")
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
    print_storage_summary(min_size=min_size, to_console=False, order_by=order_by)
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
    parser.add_argument("--order", "--sort", dest="order_by", choices=["recent", "oldest", "size"], default="size",
                        help="Sort order for IDRIVE STORAGE USE BY DEVICE table: 'recent' (most recent updates), 'oldest' (oldest updates), or 'size' (default)")
    parser.add_argument("--summary", action="store_true", help="Print the compact one-line per device storage summary table to console and exit")
    parser.add_argument("--tree", "--full-summary", action="store_true", help="Print the full folder hierarchy storage table to console and exit")

    # tagging operations
    parser.add_argument("--tag", help="Mark a device/path as tagged (format path[=value], value optional)")
    parser.add_argument("--untag", help="Remove the tag from a device/path")
    parser.add_argument("--list-tags", action="store_true",
                        help="Print all tagged paths for matching device")

    # device active / online status operations
    parser.add_argument("--edit-devices", "--manage-devices", action="store_true",
                        help="Interactive CLI prompt to view and edit device Active/Inactive status")
    parser.add_argument("--set-device-active", help="Set device to Active by ID or Name")
    parser.add_argument("--set-device-inactive", help="Set device to Inactive by ID or Name")
    parser.add_argument("--include-inactive", action="store_true", help="Include inactive devices in full audit (default skips inactive devices)")
    parser.add_argument("--set-device-online", help="Set device to Active/Online by ID or Name (alias for --set-device-active)")
    parser.add_argument("--set-device-offline", help="Set device to Inactive/Offline by ID or Name (alias for --set-device-inactive)")
    parser.add_argument("--list-devices", action="store_true", help="List all devices and prompt to edit their Active/Inactive status")

    args = parser.parse_args()
    print(f"Parsed parameters: {args}")

    # handle interactive device status editing request
    if args.edit_devices:
        manage_devices_interactive(standalone=True)
        conn.close()
        sys.exit(0)

    # handle device active / online status operations before interactive/crawl
    if args.set_device_active or args.set_device_inactive or args.set_device_online or args.set_device_offline or args.list_devices:
        if args.set_device_active:
            count = set_device_status(args.set_device_active, True)
            print(f"Updated {count} device(s) to Active.")
        if args.set_device_inactive:
            count = set_device_status(args.set_device_inactive, False)
            print(f"Updated {count} device(s) to Inactive.")
        if args.set_device_online:
            count = set_device_status(args.set_device_online, True)
            print(f"Updated {count} device(s) to Active (Online).")
        if args.set_device_offline:
            count = set_device_status(args.set_device_offline, False)
            print(f"Updated {count} device(s) to Inactive (Offline).")
        if args.list_devices:
            manage_devices_interactive(standalone=True)
        conn.close()
        sys.exit(0)

    # handle summary display request
    if args.summary or args.tree:
        print_storage_summary(min_size=args.min_size, to_console=True, order_by=args.order_by, show_tree=args.tree)
        conn.close()
        sys.exit(0)

    # handle interactive session request
    if args.interactive:
        run_interactive(min_size=args.min_size, order_by=args.order_by)
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
                cur.execute("SELECT DISTINCT path, tag FROM api_calls WHERE device_id=? AND tag IS NOT NULL AND tag <> '' AND tag <> '0' ORDER BY path", (dev['device_id'],))
                rows = cur.fetchall()
                top_level_rows = []
                for r in rows:
                    r_path = r['path']
                    r_tag = (r['tag'] or '').strip().lower()
                    has_ancestor = any(
                        r_path.startswith(p['path'].rstrip('/') + '/') and
                        (p['tag'] or '').strip().lower() == r_tag
                        for p in rows
                    )
                    if not has_ancestor:
                        top_level_rows.append(r)
                if top_level_rows:
                    print(f"\nTagged paths for {dev['nick_name']} ({dev['device_id']}):")
                    for r in top_level_rows:
                        sub_cnt = sum(1 for sub in rows if sub['path'].startswith(r['path'].rstrip('/') + '/') and sub['path'] != r['path'])
                        sub_info = f" (+{sub_cnt} subfolders)" if sub_cnt > 0 else ""
                        print(f"   {r['path']} -> {repr(r['tag'])}{sub_info}")
        conn.close()
        sys.exit(0)

    run_audit(
        start_folder=args.start_folder, 
        one_level=args.one_level, 
        device_filter=args.device_filter, 
        max_depth=args.max_depth,
        force=args.force,
        min_size=args.min_size,
        order_by=args.order_by,
        include_inactive=args.include_inactive
    )