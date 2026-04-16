# Hướng dẫn Debug Lỗi Token

## 1. Kiểm tra xem token có được lưu không
```
python check_token.py
```

## 2. Nếu token không tồn tại hoặc không hợp lệ

### Cách 1: Đăng nhập lại hoàn toàn (khuyến nghị)
```
python browser_login.py
```
- Sẽ mở trình duyệt tự động
- Đăng nhập với OpenAI account
- Token sẽ được lưu vào `~/.codex/auth.json`

### Cách 2: Làm mới token hiện có (nếu refresh token còn hiệu lực)
```
python browser_login.py --refresh
```

## 3. **QUAN TRỌNG**: Restart backend sau khi login
- Dừng backend (Ctrl+C)
- Khởi động lại backend:
  ```
  uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
  ```

## 4. Kiểm tra backend logs

Khi start backend, nên thấy:
```
🔍 Tìm file auth: /home/user/.codex/auth.json
   Tồn tại: True
✅ CodexOAuth đã kết nối: your_email@example.com
   Authentication status: True
```

Nếu không thấy như vậy, có vấn đề với token.

## 5. Thử hỏi câu hỏi lại

- Nếu vẫn lỗi 500 với "Token expired", hãy kiểm tra logs của backend xem error chi tiết là gì.
- Nếu lỗi 401 với "Không tìm thấy file auth", hãy chạy `python browser_login.py` lại.

## Ghi chú

- Token được lưu ở: `~/.codex/auth.json` (ví dụ: `C:\Users\HACOM\.codex\auth.json` trên Windows)
- Không chia sẻ file này với ai - nó chứa token truy cập
- Nếu token bị lộ, hãy đăng nhập lại sẽ tạo token mới
