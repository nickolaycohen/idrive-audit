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


# --- AUTH ---
# log into idrive website; go to Developer Tools → Application → Cookies and copy the EVSID and JSESSIONID values into the COOKIE_STR below (format: "EVSID=...; JSESSIONID=...;")
# API call is made to browseFolder endpoint - look in Headers tab -> Request Headers → Cookie to find the correct string to use here.  This is a manual step since the cookie is periodically refreshed by the server and we want to avoid hardcoding credentials in the script.

COOKIE_STR = "EVSID=QF40648Y4E20GY7UCNB8FK17YPZJAJAFZ7P727OHSK3JGK0GFXRXHE58OT0I; JSESSIONID=8B61886C82C347041DD766F56EE1BD0B.tomcat8;"
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


def validate_cookie():
    """Make a quick request using current headers/cookie; exit if auth fails.

    The API returns JSON with a 'contents' key for a valid browseFolder call.
    When the cookie is missing/invalid the server typically returns HTML or
    an error message we can't parse.  In that case, we alert the user to
    fetch an updated cookie string manually via Chrome DevTools.
    """
    # echo the cookie so the user can verify what is being used
    print(f"Using COOKIE_STR: {COOKIE_STR}\n")
    test_dev = RAW_DEVICES[0]['device_id'] if RAW_DEVICES else None
    if not test_dev:
        return
    payload = {'p': '/', 'json': 'yes', 'device_id': test_dev}
    try:
        r = session.post(f"{BASE_URL}/browseFolder", data=payload, timeout=10)
        # try parse json
        data = r.json()
        if not isinstance(data, dict) or 'contents' not in data:
            raise ValueError("unexpected response")
    except Exception as e:
        sys.stdout.write("\nERROR: authentication appears to have failed.\n")
        sys.stdout.write("Please open Chrome, navigate to idrive.com, "
                         "copy the EVSID/JSESSIONID cookie from Developer "
                         "Tools and update COOKIE_STR in this script.\n")
        sys.exit(1)

# cookie validation will be triggered after device list is available
# (moved down to just after RAW_DEVICES declaration)

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
        tag TEXT DEFAULT ''
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
                tag TEXT DEFAULT ''
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
conn.commit()

def normalize_path(p):
    """Return a canonical path string used for DB keys (single leading slash).

    This ensures browseFolder and getProperties use the same path format.
    """
    if not p:
        return "/"
    # remove leading/trailing whitespace
    p = p.strip()
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

    # try to find an existing row for this device/endpoint/path and update it
    try:
        cur.execute(
            "SELECT id FROM api_calls WHERE device_id=? AND path=? AND endpoint=? ORDER BY timestamp DESC LIMIT 1",
            (device_id, norm_path, endpoint)
        )
        existing = cur.fetchone()
        if existing:
            cur.execute(
                "UPDATE api_calls SET timestamp=?, device_name=?, size=?, filecount=?, lmd=?, response_json=? WHERE id=?",
                (
                    datetime.utcnow().isoformat(),
                    device_name,
                    size_val,
                    filecount_val,
                    lmd_val,
                    resp_json,
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
        INSERT INTO api_calls (timestamp, device_id, device_name, endpoint, path, size, filecount, lmd, response_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            resp_json
        )
    )
    rowid = cur.lastrowid
    conn.commit()
    return rowid


# --- FULL DEVICE LIST ---
# RAW_DEVICES = [
#     {"device_id": "D01563744743000489825", "nick_name": "NickolaysiMac"},
# ]

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
    #{"device_id": "R01663474652000128789", "nick_name": "IDrive Photos"}, - this is special folder - files in it are most likely duplicates of other devices, so skipping for now
    {"device_id": "D01692572940000295373", "nick_name": "NickolaysMacmini"},
    {"device_id": "R01733266910000709467", "nick_name": "Milena’s iPad"},
    {"device_id": "D01740009573000135005", "nick_name": "NickolaysMacBookPro2"}
]


# validate cookie now that we know which test device to use
validate_cookie()

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

def crawl(device_id, device_name, current_path, depth, max_depth=MAX_DEPTH, ignore_skip=False):
    # canonical path for DB lookups/logging
    norm = normalize_path(current_path)
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
            # store using canonical path
            rowid = log_api_call(device_id, device_name, 'browseFolder', norm, res)
        except Exception:
            rowid = None
        items = res.get('contents', [])
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

        next_path = name if name.startswith("/") else f"{current_path.rstrip('/')}/{name}"
        
        details = get_details(device_id, device_name, next_path, ignore_skip=ignore_skip)
        size_bytes = int(details.get('size', 0))
        size_gb = size_bytes / (1024**3)

        if size_gb >= MIN_SIZE_GB:
            indent = "  " * depth
            print(f"{indent} > {name[:40]:<45} | {size_gb:>10.2f} GB | {details.get('filecount', 0):>8} files")
            crawl(device_id, device_name, next_path, depth + 1, max_depth, ignore_skip)
    # mark this folder as drilled (we processed its children)
    try:
        # Decide whether to flag this path as "drilled".
        #
        # * If the caller supplied --start-folder we always mark the root
        #   (depth==1) regardless of max_depth, since the intent was to
        #   explicitly drill that folder.
        # * For all other paths (including children during a targeted run),
        #   the value of max_depth determines whether their contents were
        #   explored; only when max_depth>1 (i.e. we went at least two levels
        #   beneath the starting point) do we mark them.
        do_mark = False
        if ignore_skip and depth == 1:
            do_mark = True
        elif max_depth is not None and int(max_depth) > 1:
            do_mark = True

        if do_mark:
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
    # try to find a getProperties record first
    cur.execute(
        "SELECT id FROM api_calls WHERE device_id=? AND path=? AND endpoint='getProperties' ORDER BY timestamp DESC LIMIT 1",
        (device_id, norm)
    )
    existing = cur.fetchone()
    if not existing:
        # fall back to any endpoint
        cur.execute(
            "SELECT id FROM api_calls WHERE device_id=? AND path=? ORDER BY timestamp DESC LIMIT 1",
            (device_id, norm)
        )
        existing = cur.fetchone()
    if existing:
        cur.execute("UPDATE api_calls SET tag=? WHERE id=?", (tag_value, existing['id']))
    else:
        # insert a new row with endpoint=getProperties so the record is included
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


def run_audit(start_folder=None, one_level=False, device_filter=None, max_depth=MAX_DEPTH):
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
        ignore = True if start_folder else False

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

    parser.add_argument("--max-depth", type=int, default=MAX_DEPTH,
                        help=f"Maximum recursion depth (default {MAX_DEPTH})")

    # tagging operations
    parser.add_argument("--tag", help="Mark a device/path as tagged (format path[=value], value optional)")
    parser.add_argument("--untag", help="Remove the tag from a device/path")
    parser.add_argument("--list-tags", action="store_true",
                        help="Print all tagged paths for matching device")

    args = parser.parse_args()
    print(f"Parsed parameters: {args}")

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

    run_audit(start_folder=args.start_folder, one_level=args.one_level, device_filter=args.device_filter, max_depth=args.max_depth)