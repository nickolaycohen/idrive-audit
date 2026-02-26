import requests
import sys

# --- AUTH ---
COOKIE_STR = "EVSID=7R0227F7RBY70IZWCRJ5NQWFUEZCO05DHERRCDMY3L663I6QYDE8SW5IYCA1; JSESSIONID=8B61886C82C347041DD766F56EE1BD0B.tomcat8;"
BASE_URL = "https://evsweb2652.idrive.com/evs"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
    'Cookie': COOKIE_STR,
    'Content-Type': 'application/x-www-form-urlencoded',
    'X-Requested-With': 'XMLHttpRequest'
}

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

def get_details(device_id, path):
    for prefix in ["/", "//"]:
        clean_path = path if path.startswith("/") else prefix + path
        payload = {'p': clean_path, 'json': 'yes', 'device_id': device_id}
        try:
            r = requests.post(f"{BASE_URL}/getProperties", data=payload, headers=HEADERS, timeout=15)
            res = r.json()
            if int(res.get('size', 0)) > 0:
                return res
        except:
            continue
    return {"size": 0, "filecount": 0}

def crawl(device_id, current_path, depth):
    if depth > MAX_DEPTH:
        return

    payload = {'p': current_path, 'json': 'yes', 'device_id': device_id}
    try:
        r = requests.post(f"{BASE_URL}/browseFolder", data=payload, headers=HEADERS, timeout=15)
        items = r.json().get('contents', [])
    except:
        return

    for item in items:
        name = item.get('p') or item.get('name') or item.get('desc')
        if not name or name in [".", ".."]: continue

        next_path = name if name.startswith("/") else f"{current_path.rstrip('/')}/{name}"
        
        details = get_details(device_id, next_path)
        size_bytes = int(details.get('size', 0))
        size_gb = size_bytes / (1024**3)

        if size_gb >= MIN_SIZE_GB:
            indent = "  " * depth
            print(f"{indent} > {name[:40]:<45} | {size_gb:>10.2f} GB | {details.get('filecount', 0):>8} files")
            crawl(device_id, next_path, depth + 1)

def run_audit():
    print(f"\n{'IDRIVE RECURSIVE ACCOUNT AUDIT':^85}")
    print(f"{'Folder Hierarchy':<50} | {'Size':>13} | {'Files':>10}")
    print("-" * 85)
    
    for dev in RAW_DEVICES:
        print(f"\nDEVICE: {dev['nick_name']} ({dev['device_id']})")
        crawl(dev['device_id'], "/", 1)
        print("-" * 85)
    
    print(f"\nAudit complete. Results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    run_audit()