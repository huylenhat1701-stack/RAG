#!/usr/bin/env python3
"""
Reset Token Cache và Restart Backend
Giải pháp nhanh cho lỗi token
"""

import os
import sys
import json
import subprocess
import time
from pathlib import Path

print("=" * 60)
print("Reset Token & Reset Backend")
print("=" * 60)

# Bước 1: Kiểm tra xem token file có tồn tại không
CODEX_HOME = Path.home() / ".codex"
AUTH_FILE = CODEX_HOME / "auth.json"

print(f"\n📄 Token file: {AUTH_FILE}")

# Bước 2: Backup token cũ (tuỳ chọn)
if AUTH_FILE.exists():
    backup_file = AUTH_FILE.with_suffix('.json.backup')
    print(f"   Tạo backup: {backup_file}")
    import shutil
    shutil.copy(AUTH_FILE, backup_file)

# Bước 3: Yêu cầu user đăng nhập lại
print("\n🔄 Chuẩn bị đăng nhập lại...")
print("   Sẽ mở trình duyệt trong 3 giây...")
time.sleep(3)

# Chạy browser_login.py
try:
    result = subprocess.run(
        [sys.executable, "browser_login.py"],
        cwd=Path(__file__).parent,
        capture_output=False
    )
    if result.returncode != 0:
        print("\n❌ Đăng nhập thất bại")
        sys.exit(1)
except Exception as e:
    print(f"\n❌ Lỗi: {e}")
    sys.exit(1)

print("\n✅ Đăng nhập thành công")

# Bước 4: Kiểm tra token mới
print("\n🔍 Kiểm tra token mới...")
if AUTH_FILE.exists():
    with open(AUTH_FILE, 'r') as f:
        auth_data = json.load(f)
    
    if "chatgpt" in auth_data:
        tokens = auth_data["chatgpt"]
    else:
        tokens = auth_data
    
    if tokens.get("access_token"):
        print("✅ Token mới được lưu thành công")
    else:
        print("⚠️  Token không đầy đủ")
else:
    print("❌ File token không tìm thấy")

print("\n" + "=" * 60)
print("✅ Hoàn tất! Token đã được reset")
print("\n📌 Hãy RESTART backend:")
print("   1. Dừng backend hiện tại (Ctrl+C)")
print("   2. Chạy: uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000")
print("=" * 60)
