import re

with open('app.py', encoding='utf-8', errors='replace') as f:
    content = f.read()
    lines = content.splitlines()

# Find all r'...' and r"..." patterns
pattern = re.compile(r'\br(["\'])((?:(?!\1).|\\.)*)\1')

for m in pattern.finditer(content):
    pat_str = m.group(2)
    lineno = content[:m.start()].count('\n') + 1
    try:
        re.compile(pat_str)
    except re.error as e:
        print(f"Line {lineno}: {pat_str!r}")
        print(f"  Error: {e}")
        print(f"  Context: {lines[lineno-1].strip()}")
        print()
