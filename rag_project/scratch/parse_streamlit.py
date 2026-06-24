import sys
import re

sys.stdout.reconfigure(encoding='utf-8')

with open('frontend/app.py', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    clean = line.strip()
    if clean.startswith('st.title') or clean.startswith('st.header') or clean.startswith('st.subheader'):
        print(f"L{i+1}: {clean}")
    elif 'st.radio' in clean or 'st.selectbox' in clean or 'st.tabs' in clean or 'option_menu' in clean:
        print(f"L{i+1}: {clean}")
    elif clean.startswith('if') and ('==' in clean) and ('"' in clean or "'" in clean):
        print(f"L{i+1}: {clean}")
    elif clean.startswith('elif') and ('==' in clean) and ('"' in clean or "'" in clean):
        print(f"L{i+1}: {clean}")
