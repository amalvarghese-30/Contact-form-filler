"""
Quick test to see if the server can start
"""
import sys
sys.path.insert(0, 'c:/xampp/htdocs/contact-form-filler/backend')

print("Testing imports...")
try:
    print("1. Importing form_filler...")
    from form_filler import CONCURRENT_BROWSERS
    print(f"   ✓ CONCURRENT_BROWSERS = {CONCURRENT_BROWSERS}")
    
    print("2. Importing fastapi_backend...")
    import fastapi_backend
    print("   ✓ fastapi_backend imported")
    
    print("\n✅ All imports successful!")
    print("Server should start normally.")
    
except Exception as e:
    print(f"\n❌ Import failed: {e}")
    import traceback
    traceback.print_exc()
