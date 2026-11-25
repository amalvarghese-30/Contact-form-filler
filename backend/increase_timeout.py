import re

# Read the file
with open('form_filler.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the timeout value
content = re.sub(
    r'POST_SUBMIT_WAIT_MS = env_int\("POST_SUBMIT_WAIT_MS", 4000\)  # 4 seconds',
    'POST_SUBMIT_WAIT_MS = env_int("POST_SUBMIT_WAIT_MS", 10000)  # 10 seconds (increased for better response capture)',
    content
)

# Write back
with open('form_filler.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Increased POST_SUBMIT_WAIT_MS from 4000ms to 10000ms")
