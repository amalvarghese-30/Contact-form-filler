"""
Minimal test to find what's hanging
"""
print("Step 1: Testing basic imports...")
import sys
import asyncio
print("  ✓ sys, asyncio")

print("Step 2: Testing FastAPI...")
from fastapi import FastAPI
print("  ✓ FastAPI")

print("Step 3: Testing form_filler import...")
sys.path.insert(0, 'c:/xampp/htdocs/contact-form-filler/backend')
from form_filler import fillallforms
print("  ✓ form_filler.fillallforms")

print("\n✅ All imports successful - server should work!")
