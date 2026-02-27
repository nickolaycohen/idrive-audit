import requests
import sys
import json
import argparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# python3 import-requests.py --start-folder /Volumes/Extreme\ Pro/Photos\ Library/All-Media.photoslibrary --device-filter D01692572940000295373

# --- AUTH ---
COOKIE_STR = "EVSID=JYR67VFA3VUQVD2CZ3HHMK4P3ZB9Z3JQ0U1RRFL00OCR34KJP85QNOXHD35X; JSESSIONID=8B61886C82C347041DD766F56EE1BD0B.tomcat8;"
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
        response_json TEXT
    )
    '''
)
# ensure columns exist for older databases
cur.execute("PRAGMA table_info(api_calls)")
cols = [row['name'] for row in cur.fetchall()]
if 'device_name' not in cols:
    cur.execute('ALTER TABLE api_calls ADD COLUMN device_name TEXT')
    conn.commit()
if 'lmd' not in cols:
    cur.execute('ALTER TABLE api_calls ADD COLUMN lmd TEXT')
    conn.commit()
conn.commit()

def log_api_call(device_id, device_name, endpoint, path, details):
    """Insert a record about an API call into the database.

    The API returns an optional 'lmd' field (last‑modification date).  If
    present, we store it alongside size/filecount.
    """
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
    cur.execute(
        '''
        INSERT INTO api_calls (timestamp, device_id, device_name, endpoint, path, size, filecount, lmd, response_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            datetime.utcnow().isoformat(),
            device_id,  # yes, device_id column exists and is being stored
            device_name,
            endpoint,
            path,
            int(details.get('size', 0)) if isinstance(details, dict) else None,
            int(details.get('filecount', 0)) if isinstance(details, dict) else None,
            lmd_val,
            json.dumps(details) if details is not None else None
        )
    )
    conn.commit()


# --- FULL DEVICE LIST ---
RAW_DEVICES = [
    {"device_id": "D01563711761000105006", "nick_name": "NickolaysMacBookPro"},
    {"device_id": "D01563744743000489825", "nick_name": "NickolaysiMac"},
    {"device_id": "R01563807439000950037", "nick_name": "iPhone (5)"},
    {"device_id": "R01563846082000493096", "nick_name": "Nickolay's iPad"},
    {"device_id": "D01567232251000246054", "nick_name": "ASUS"},
    {"device_id": "D01567473394000932522", "nick_name": "BENNY-ASUS-PC_1"},
    {"device_id": "D01567900303000721746", "nick_name": "BENNY-ASUS-PC_2"},
    {"device_id": "D01599278876000183928", "nick_name": "LAPTOP-BRBMTA5B"},
    {"device_id": "R01607197738000636951", "nick_name": "iPhone (3)"},
    {"device_id": "R01663474652000128789", "nick_name": "IDrive Photos"},
    {"device_id": "D01692572940000295373", "nick_name": "NickolaysMacmini"},
    {"device_id": "R01733266910000709467", "nick_name": "Milena’s iPad"},
    {"device_id": "D01740009573000135005", "nick_name": "NickolaysMacBookPro2"}
]

# --- SETTINGS ---
MAX_DEPTH = 4 # Increased depth to see deeper into /Users
MIN_SIZE_GB = 1.0 
OUTPUT_FILE = "idrive_audit_report.txt"

class Logger(object):
    """Helper to write to both console and file."""
    def __init__(self):
        self.terminal = sys.stdout
        self.log = open(OUTPUT_FILE, "w", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush() # Ensure it saves even if the script crashes

    def flush(self):
        pass

sys.stdout = Logger()

def get_details(device_id, device_name, path, ignore_skip=False):
    # skip detail call if this path was checked recently
    if not ignore_skip and should_skip(device_id, path, endpoint='getProperties'):
        print(f"  (skipping getProperties for {path} on {device_name} — recent entry)")
        return {"size": 0, "filecount": 0}
    for prefix in ["/", "//"]:
        clean_path = path if path.startswith("/") else prefix + path
        payload = {'p': clean_path, 'json': 'yes', 'device_id': device_id}
        try:
            r = session.post(f"{BASE_URL}/getProperties", data=payload, timeout=15)
            res = r.json()
            # log the call for auditing
            try:
                log_api_call(device_id, device_name, 'getProperties', clean_path, res)
            except Exception:
                pass  # logging should not interrupt the main flow
            if int(res.get('size', 0)) > 0:
                return res
        except Exception:
            continue
    # even if nothing found, log an empty result
    try:
        log_api_call(device_id, device_name, 'getProperties', path, {'size': 0, 'filecount': 0})
    except Exception:
        pass
    return {"size": 0, "filecount": 0}

def crawl(device_id, device_name, current_path, depth, max_depth=MAX_DEPTH, ignore_skip=False):
    # don't re-scan a folder if we've queried it within the last 24h
    if not ignore_skip and should_skip(device_id, current_path):
        print(f"  (skipping {current_path} for {device_name} — scanned <24h ago)")
        return
    if depth > max_depth:
        return

    payload = {'p': current_path, 'json': 'yes', 'device_id': device_id}
    try:
        r = session.post(f"{BASE_URL}/browseFolder", data=payload, timeout=15)
        res = r.json()
        # log the browse call
        try:
            log_api_call(device_id, device_name, 'browseFolder', current_path, res)
        except Exception:
            pass
        items = res.get('contents', [])
    except Exception:
        return

    for item in items:
        name = item.get('p') or item.get('name') or item.get('desc')
        if not name or name in [".", ".."]: continue

        next_path = name if name.startswith("/") else f"{current_path.rstrip('/')}/{name}"
        
        details = get_details(device_id, device_name, next_path, ignore_skip=ignore_skip)
        size_bytes = int(details.get('size', 0))
        size_gb = size_bytes / (1024**3)

        if size_gb >= MIN_SIZE_GB:
            indent = "  " * depth
            print(f"{indent} > {name[:40]:<45} | {size_gb:>10.2f} GB | {details.get('filecount', 0):>8} files")
            crawl(device_id, device_name, next_path, depth + 1, max_depth, ignore_skip)


# toggle verbose skip debugging
SKIP_DEBUG = True

def should_skip(device_id, path, endpoint='browseFolder', hours=24):
    """Return True if the given device/path/endpoint was logged within the last
    `hours` hours so we can avoid redundant API calls.

    When SKIP_DEBUG is True the result of the check is printed for visibility.
    """
    cur.execute(
        "SELECT timestamp FROM api_calls "
        "WHERE device_id=? AND path=? AND endpoint=? "
        "ORDER BY timestamp DESC LIMIT 1",
        (device_id, path, endpoint)
    )
    row = cur.fetchone()
    if not row:
        if SKIP_DEBUG:
            print(f"should_skip: no prior record for {endpoint} {path} ({device_id})")
        return False
    try:
        last = datetime.fromisoformat(row['timestamp'])
    except Exception:
        if SKIP_DEBUG:
            print(f"should_skip: bad timestamp '{row['timestamp']}'")
        return False
    delta = datetime.utcnow() - last
    result = delta < timedelta(hours=hours)
    if SKIP_DEBUG:
        print(f"should_skip: {endpoint} {path} ({device_id}) last={last.isoformat()} delta={delta} skip={result}")
    return result


def run_audit(start_folder=None, one_level=False, device_filter=None):
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
        # if a starting folder is provided we only go one level deep and
        # bypass the skip logic entirely
        if start_folder:
            limit = 2
            ignore = True
        else:
            limit = MAX_DEPTH
            ignore = False
        crawl(dev['device_id'], dev['nick_name'], root, 1, limit, ignore_skip=ignore)
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

    args = parser.parse_args()
    print(f"Parsed parameters: {args}")

    run_audit(start_folder=args.start_folder, one_level=args.one_level, device_filter=args.device_filter)