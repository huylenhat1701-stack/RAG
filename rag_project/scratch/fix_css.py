import re

with open('frontend/app.py', encoding='utf-8') as f:
    content = f.read()

# The leftover old CSS block starts at the blank lines after the first </style>
# marker (line 192) and includes another full st.markdown CSS block ending with
# the second triple-quote close.  We locate the second occurrence of
# `st.markdown("""` inside the <style> context and remove it.

# Strategy: find the stretch between the first `</style>\n""", unsafe...` 
# and the second one, and collapse it.
marker = '</style>\n""", unsafe_allow_html=True)\n'
first_idx = content.index(marker) + len(marker)
second_idx = content.index(marker, first_idx) + len(marker)

# The junk is everything between first_idx and second_idx
junk = content[first_idx:second_idx]
print(f'Removing {len(junk)} chars of old CSS')

new_content = content[:first_idx] + '\n\n' + content[second_idx:]

with open('frontend/app.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print('Done. New file length:', len(new_content))
