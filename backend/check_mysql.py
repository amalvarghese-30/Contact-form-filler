"""
Quick Fix: Start MySQL Server

ERROR: Can't connect to MySQL server on '127.0.0.1:3306' (10061)

This means MySQL is not running!

SOLUTION:
1. Open XAMPP Control Panel
2. Click "Start" next to MySQL
3. Wait for it to show as running (green)
4. Then restart your Python server:
   python run_server_windows.py

OR use this command to check if MySQL is running:
"""

import subprocess
import sys

print("Checking if MySQL is running...")
print("=" * 80)

try:
    # Check if MySQL process is running
    result = subprocess.run(
        ["powershell", "-Command", "Get-Process mysqld -ErrorAction SilentlyContinue"],
        capture_output=True,
        text=True
    )
    
    if result.stdout.strip():
        print("✅ MySQL is RUNNING")
        print(result.stdout)
    else:
        print("❌ MySQL is NOT RUNNING")
        print("\nTo start MySQL:")
        print("1. Open XAMPP Control Panel")
        print("2. Click 'Start' next to MySQL")
        print("3. Wait for it to turn green")
        print("\nOR run this command:")
        print("   C:\\xampp\\mysql\\bin\\mysqld.exe")
        
except Exception as e:
    print(f"Error checking MySQL status: {e}")

print("\n" + "=" * 80)
print("After MySQL is running, restart your server:")
print("python run_server_windows.py")
