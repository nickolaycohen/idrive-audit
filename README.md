# IDrive Account Storage Audit & Reconciliation Toolset

This repository provides tools for auditing and maintaining account storage by cataloging local attached storage volumes and reconciling them with remote IDrive EVS backups.

---

## Prerequisites

- **Python 3.8+**
- **Dependencies**: `requests`
  ```bash
  pip install requests
  ```

---

## Authentication Setup

Because the IDrive EVS API updates cookies periodically, you must manually capture a valid browser cookie to authenticate the remote audit script.

1. Log into your account on the [idrive.com](https://www.idrive.com) web console.
2. Open **Chrome Developer Tools** (F12) and go to the **Application** tab → **Cookies**.
3. Locate the `EVSID` and `JSESSIONID` cookies.
4. Copy their values and paste them into the `COOKIE_STR` variable at the top of [idrive-audit.py](file:///Users/nickolaycohen/dev/idrive-audit/idrive-audit.py):
   ```python
   COOKIE_STR = "EVSID=YOUR_EVSID_VALUE; JSESSIONID=YOUR_JSESSIONID_VALUE"
   ```

---

## 1. Remote IDrive Audit (`idrive-audit.py`)

This script audits backed-up directories on your IDrive account using remote EVS endpoints. The results, including folder sizes and file counts, are tracked in `idrive_audit.db`.

### Commands

* **Run Interactive Mode (Recommended)**:
  Launches an interactive console to display the top 10 largest folders, drill down into subdirectories, update tags, or recursively delete folders from your IDrive storage.
  ```bash
  python3 idrive-audit.py --interactive
  # or
  python3 idrive-audit.py -i
  ```

* **Standard Audit Run**:
  Crawls all registered IDrive devices and records their sizes in the database.
  ```bash
  python3 idrive-audit.py
  ```

* **Targeted Scanning**:
  Scan a specific starting folder on a targeted device up to a custom depth:
  ```bash
  python3 idrive-audit.py --start-folder "/Users/nickolaycohen/Pictures" --device-filter "D01563744743000489825" --max-depth 1
  ```

* **Force Rescan**:
  Bypass the default 24-hour skip caching logic to force a fresh scan:
  ```bash
  python3 idrive-audit.py --force
  ```

* **Command Line Tagging Operations**:
  Tag, untag, or list tags on a device:
  ```bash
  # Tag a path
  python3 idrive-audit.py --device-filter NickolaysMacbook --tag "/Users/nickolaycohen/Pictures=Photos-Backup"

  # Untag a path
  python3 idrive-audit.py --device-filter NickolaysMacbook --untag "/Users/nickolaycohen/Pictures"

  # List tags
  python3 idrive-audit.py --device-filter NickolaysMacbook --list-tags
  ```

---

## 2. Local Attached Storage Scan (`scan-local-drives.py`)

This script catalogs connected storage drives, external volumes, and local folders on macOS. It stores structural metadata in `device_registry.db` and compares sizes with `idrive_audit.db` to identify backup gaps.

### Commands

* **Scan Connected Drives**:
  Scans all attached storage volumes and directories larger than 1GB.
  ```bash
  python3 scan-local-drives.py --scan
  ```

* **Scan Specific Directory**:
  Scan only a targeted directory:
  ```bash
  python3 scan-local-drives.py --scan --path "/Volumes/Extreme Pro/Photos Library"
  ```

* **Generate Backup Gap Report**:
  Produces a detailed alignment report showing local paths, classes, priorities, Finder tags, and their current IDrive remote backup status.
  ```bash
  python3 scan-local-drives.py --report --output local_audit_report.txt
  ```

* **Manage Folder Classes & Priorities**:
  Organize folders to define what needs backing up vs what can be ignored.
  ```bash
  # Define a class linked to a priority
  python3 scan-local-drives.py --define-class "ApplePhotosTempExport=9-ApplePhotosTempExport"

  # Assign a class to a folder (propagates to all subdirectories)
  python3 scan-local-drives.py --assign-class "/Users/nickolaycohen/Pictures/Apple Photo Exports/=ApplePhotosTempExport"
  ```

* **Apply Tagging & Finder Tags**:
  ```bash
  # Apply tracking tags
  python3 scan-local-drives.py --tag "/Volumes/Extreme Pro/Photos=Memories"

  # Apply macOS Finder tags color-codes
  python3 scan-local-drives.py --finder-tag "/Volumes/Extreme Pro/Photos=Orange"
  ```
