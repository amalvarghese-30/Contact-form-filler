import re

# Read the file
with open('analytics.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the progress bar calculation
old_code = '''      const pct = total
        ? Math.min(100, Math.round((progress / total) * 100))
        : (status === "completed" ? 100 : 0);'''

new_code = '''      // Completed campaigns should always show 100% (full green bar)
      const pct = status === "completed"
        ? 100
        : total
          ? Math.min(100, Math.round((progress / total) * 100))
          : 0;'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open('analytics.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ Successfully updated progress bar logic!")
else:
    print("❌ Could not find the target code to replace")
    print("Searching for similar patterns...")
    # Try to find the line
    if "const pct = total" in content:
        print("Found 'const pct = total' in file")
    else:
        print("Could not find 'const pct = total'")
