"""
Fix MySQL Corrupted System Table
The proxies_priv table is corrupted, preventing MySQL from starting
"""
import shutil
from pathlib import Path

print("=" * 80)
print("FIXING CORRUPTED MYSQL SYSTEM TABLE")
print("=" * 80)

mysql_data = Path("C:/xampp/mysql/data/mysql")

# The corrupted files
files_to_backup = [
    "proxies_priv.frm",
    "proxies_priv.MYI",
    "proxies_priv.MYD"
]

print("\n[1/3] Backing up corrupted files...")
backup_dir = Path("C:/xampp/mysql/data/mysql_backup_corrupt")
backup_dir.mkdir(exist_ok=True)

for filename in files_to_backup:
    src = mysql_data / filename
    if src.exists():
        dst = backup_dir / filename
        shutil.copy2(src, dst)
        print(f"✓ Backed up {filename}")

print("\n[2/3] Deleting corrupted table files...")
for filename in files_to_backup:
    file_path = mysql_data / filename
    if file_path.exists():
        file_path.unlink()
        print(f"✓ Deleted {filename}")

print("\n[3/3] Copying fresh files from backup...")
backup_mysql = Path("C:/xampp/mysql/backup/mysql")

if backup_mysql.exists():
    for filename in files_to_backup:
        src = backup_mysql / filename
        if src.exists():
            dst = mysql_data / filename
            shutil.copy2(src, dst)
            print(f"✓ Restored {filename} from backup")
        else:
            print(f"⚠ {filename} not found in backup")
    
    print("\n" + "=" * 80)
    print("✅ FIXED! MySQL system table repaired")
    print("=" * 80)
    print("\nNow try starting MySQL in XAMPP Control Panel")
else:
    print("\n" + "=" * 80)
    print("❌ XAMPP backup directory not found!")
    print("=" * 80)
    print("\nAlternative fix:")
    print("1. Download fresh XAMPP")
    print("2. Extract just the mysql/backup folder")
    print("3. Copy files from there")
