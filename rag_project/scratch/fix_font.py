import sys, re
sys.stdout.reconfigure(encoding='utf-8')
path = r'c:\project\new\RAG\rag_project\frontend\app.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# The user messed up the file with the replacement tool. 
# Let's restore the lines that were deleted in the for loop block around line 1770.

# 1. First, find where `            else:\n` is, near `if not lp_items:`
idx_else = -1
for i, line in enumerate(lines):
    if line.strip() == 'else:' and 'lp_items' in lines[i-1]:
        idx_else = i
        break

if idx_else != -1:
    # 2. Check if the loop is missing
    next_line = lines[idx_else + 1].strip()
    if not next_line.startswith('for step_idx'):
        # It's missing the for loop. Let's insert the fixed block.
        fixed_block = """                import re
                for step_idx, item in enumerate(lp_items, 1):
                    topic      = _html.escape(str(item.get("topic", f"Chủ đề {step_idx}")))
                    
                    raw_snippet = str(item.get("content_snippet", ""))
                    # Remove unprintable/garbage characters (like 🗹 U+1F5F9, replacement chars, etc)
                    # We keep word characters (including unicode), whitespace, and common punctuation.
                    clean_snippet = re.sub(r'[^\\w\\s.,;:!?()\\[\\]{}"\\'+-*/=<>~@#$%^&|`]', '', raw_snippet)
                    snippet    = _html.escape(clean_snippet)
                    
                    advice     = _html.escape(str(item.get("advice", "")))
"""
        lines.insert(idx_else + 1, fixed_block)
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print("Restored and fixed snippet logic!")
    else:
        print("Loop already exists.")
else:
    print("Could not find else block.")
