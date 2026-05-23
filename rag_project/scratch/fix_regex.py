import sys; sys.stdout.reconfigure(encoding='utf-8')
path = r'c:\project\new\RAG\rag_project\frontend\app.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Line 1777 (index 1776) has the bad regex - replace with a safe approach
old = lines[1776]

# Use a simpler approach with str.isprintable() instead of regex character class
new = (
    "                    # Giu lai ky tu co the hien thi (loai bo garbage chars tu PDF)\n"
    "                    clean_snippet = \"\".join(\n"
    "                        ch for ch in raw_snippet\n"
    "                        if ch.isprintable() and ord(ch) < 0x2000\n"
    "                    )\n"
)

lines[1776] = new

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print("Fixed!")
print("Old:", repr(old[:80]))
print("New:", repr(new[:80]))
