"""
Complete MySQL Startup and Verification Script
"""
import subprocess
import time
import socket

def is_port_open(host, port):
    """Check if a port is open"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    result = sock.connect_ex((host, port))
    sock.close()
    return result == 0

print("=" * 80)
print("MYSQL STARTUP SCRIPT")
print("=" * 80)

# Step 1: Check if MySQL is already running
print("\n[1/4] Checking if MySQL is already running...")
if is_port_open('127.0.0.1', 3306):
    print("✅ MySQL is already running on port 3306")
else:
    print("❌ MySQL is NOT running")
    
    # Step 2: Try to start MySQL
    print("\n[2/4] Attempting to start MySQL...")
    try:
        # Try using XAMPP's mysql_start.bat
        result = subprocess.run(
            ["C:\\xampp\\mysql_start.bat"],
            capture_output=True,
            text=True,
            timeout=10
        )
        print("Started MySQL via mysql_start.bat")
    except Exception as e:
        print(f"Could not start via batch file: {e}")
        print("Trying alternative method...")
        
        # Alternative: Start mysqld directly
        try:
            subprocess.Popen(
                ["C:\\xampp\\mysql\\bin\\mysqld.exe", "--defaults-file=C:\\xampp\\mysql\\bin\\my.ini"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print("Started mysqld.exe directly")
        except Exception as e2:
            print(f"Could not start mysqld: {e2}")
    
    # Step 3: Wait and verify
    print("\n[3/4] Waiting for MySQL to start...")
    for i in range(10):
        time.sleep(1)
        if is_port_open('127.0.0.1', 3306):
            print(f"✅ MySQL is now running! (took {i+1} seconds)")
            break
        print(f"   Waiting... ({i+1}/10)")
    else:
        print("❌ MySQL did not start within 10 seconds")
        print("\nMANUAL STEPS REQUIRED:")
        print("1. Open XAMPP Control Panel")
        print("2. Click 'Start' next to MySQL")
        print("3. Wait for it to turn green")
        exit(1)

# Step 4: Final verification
print("\n[4/4] Final verification...")
if is_port_open('127.0.0.1', 3306):
    print("✅ MySQL is running and accepting connections on port 3306")
    print("\n" + "=" * 80)
    print("SUCCESS! You can now start your Python server:")
    print("python run_server_windows.py")
    print("=" * 80)
else:
    print("❌ MySQL is still not accessible")
    print("\nPlease start MySQL manually via XAMPP Control Panel")
