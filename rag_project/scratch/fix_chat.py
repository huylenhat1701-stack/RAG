with open('frontend/app.py', encoding='utf-8') as f:
    content = f.read()

# Remove the leftover duplicate old chat tab block
# It starts with the lone st.caption line (after our rerun()) up to "# TAB 5: Lịch sử"
marker_start = '\n    st.caption("Đặt câu hỏi về tài liệu — AI sẽ tìm kiếm và trả lời dựa trên nội dung.")'
marker_end = '\n\n# ============================================================\n# TAB 5: Lịch'

idx_start = content.index(marker_start)
idx_end = content.index(marker_end, idx_start)

junk = content[idx_start:idx_end]
print(f'Removing {len(junk)} chars')

new_content = content[:idx_start] + content[idx_end:]
with open('frontend/app.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
print('Done, lines:', new_content.count('\n'))
