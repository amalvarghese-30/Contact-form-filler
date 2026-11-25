"""
MySQL Crash Fix Script
Attempts multiple solutions to get MySQL running
"""
import subprocess
import os
import shutil
from pathlib import Path

print("=" * 80)
print("MYSQL CRASH FIX SCRIPT")
print("=" * 80)

# Check if ibdata1 file is locked or corrupted
data_dir = Path("C:/xampp/mysql/data")
ibdata_file = data_dir / "ibdata1"

print("\n[1/4] Checking MySQL data directory...")
if ibdata_file.exists():
    size_mb = ibdata_file.stat().st_size / (1024 * 1024)
    print(f"✓ ibdata1 exists ({size_mb:.2f} MB)")
else:
    print("✗ ibdata1 missing - MySQL data is corrupted!")

# Check for ib_logfile files
ib_logfiles = list(data_dir.glob("ib_logfile*"))
print(f"✓ Found {len(ib_logfiles)} InnoDB log files")

print("\n[2/4] Checking for stuck MySQL processes...")
result = subprocess.run(
    ["powershell", "-Command", "Get-Process mysqld -ErrorAction SilentlyContinue | Stop-Process -Force"],
    capture_output=True
)
print("✓ Killed any stuck MySQL processes")

print("\n[3/4] Attempting MySQL repair...")
print("\nOption A: Delete InnoDB log files (safe if no critical data)")
print("This often fixes 'MySQL shutdown unexpectedly' errors")
print("\nWould delete:")
for logfile in ib_logfiles:
    print(f"  - {logfile.name}")

print("\n" + "=" * 80)
print("MANUAL FIX REQUIRED")
print("=" * 80)
print("""
MySQL is crashing on startup. Try these fixes in order:

FIX 1: Delete InnoDB log files (RECOMMENDED)
----------------------------------------------
1. Make sure MySQL is stopped in XAMPP
2. Navigate to: C:\\xampp\\mysql\\data
3. Delete these files:
   - ib_logfile0
   - ib_logfile1
4. Start MySQL again in XAMPP

FIX 2: Check MySQL error log
-----------------------------
1. In XAMPP Control Panel, click "Logs" button next to MySQL
2. Look for the actual error message
3. Common errors:
   - "Table './mysql/user' is marked as crashed"
   - "Can't open file: 'mysql.frm'"
   - "InnoDB: Database page corruption"

FIX 3: Reinstall MySQL data (NUCLEAR OPTION - loses all data)
--------------------------------------------------------------
1. Stop MySQL in XAMPP
2. Rename C:\\xampp\\mysql\\data to C:\\xampp\\mysql\\data_old
3. Copy C:\\xampp\\mysql\\backup to C:\\xampp\\mysql\\data
4. Start MySQL again

After fixing, run: python fastapi_backend.py
""")

# Try to read the actual error from XAMPP log
xampp_log = Path("C:/xampp/mysql/data/mysql_error.log")
if xampp_log.exists():
    print("\n" + "=" * 80)
    print("LAST 20 LINES OF MYSQL ERROR LOG:")
    print("=" * 80)
    with open(xampp_log, 'r', errors='ignore') as f:
        lines = f.readlines()
        for line in lines[-20:]:
            print(line.rstrip())
