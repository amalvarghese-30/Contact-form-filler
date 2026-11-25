# FILE #7: backend/run_server.py
# Simple Server Startup Script - Copy this EXACTLY

#!/usr/bin/env python3
"""
Contact Form Auto Filler - Simple Server Launcher
Run this file to start the server
"""

import os
import sys
import subprocess

print("""
╔════════════════════════════════════════════════════╗
║  Contact Form Auto Filler - Server Launcher        ║
║  Starting FastAPI Server...                        ║
╚════════════════════════════════════════════════════╝
""")

# Check if running in the backend directory
if not os.path.exists('fastapi_backend.py'):
    print("ERROR: Run this script from the 'backend' folder!")
    print("Usage: python run_server.py")
    sys.exit(1)

# Import and run FastAPI
try:
    import uvicorn
    
    print("""
    ✅ Starting server on http://localhost:8000
    
    📊 Dashboard:     http://localhost:8000
    📚 API Docs:      http://localhost:8000/docs
    🏥 Health Check:  http://localhost:8000/health
    
    Press CTRL+C to stop the server
    """)
    
    uvicorn.run(
        "fastapi_backend:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )

except ImportError:
    print("ERROR: FastAPI is not installed!")
    print("Run: pip install -r requirements.txt")
    sys.exit(1)

except KeyboardInterrupt:
    print("\n\n🛑 Server stopped")
    sys.exit(0)

except Exception as e:
    print(f"ERROR: {str(e)}")
    sys.exit(1)
