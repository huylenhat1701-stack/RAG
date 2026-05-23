#!/usr/bin/env python3
"""
Script kiểm tra xem token có được lưu đúng không
"""

import json
from pathlib import Path
import os

CODEX_HOME = Path.home() / ".codex"
AUTH_FILE = CODEX_HOME / "auth.json"

print("=" * 60)
print("Kiểm tra Token")
print("=" * 60)

print(f"\n📁 CODEX_HOME: {CODEX_HOME}")
print(f"   Tồn tại: {CODEX_HOME.exists()}")

print(f"\n📄 AUTH_FILE: {AUTH_FILE}")
print(f"   Tồn tại: {AUTH_FILE.exists()}")

if AUTH_FILE.exists():
    print("\n✅ File auth.json tìm thấy")
    
    try:
        with open(AUTH_FILE, 'r', encoding='utf-8') as f:
            auth_data = json.load(f)
        
        print(f"\n📋 Nội dung auth.json:")
        
        if "chatgpt" in auth_data:
            tokens = auth_data["chatgpt"]
            print(f"   ✓ Format: chatgpt")
        elif "tokens" in auth_data:
            tokens = auth_data["tokens"]
            print(f"   ✓ Format: tokens")
        else:
            tokens = auth_data
            print(f"   ✓ Format: root level")
        
        print(f"\n   access_token: {('✓ Có' if tokens.get('access_token') else '✗ Không')}")
        print(f"   refresh_token: {('✓ Có' if tokens.get('refresh_token') else '✗ Không')}")
        print(f"   id_token: {('✓ Có' if tokens.get('id_token') else '✗ Không')}")
        
        if tokens.get("access_token"):
            at = tokens.get("access_token")
            print(f"\n   access_token (preview): {at[:50]}...")
        
        print(f"\n   last_refresh: {auth_data.get('last_refresh', 'N/A')}")
        
        # Kiểm tra độ dài token
        at = tokens.get("access_token", "")
        rt = tokens.get("refresh_token", "")
        print(f"\n   Độ dài access_token: {len(at)} ký tự")
        print(f"   Độ dài refresh_token: {len(rt)} ký tự")
        
        if at and rt:
            print("\n✅ Token hợp lệ, sẵn sàng sử dụng")
        else:
            print("\n⚠️  Token không đầy đủ, cần đăng nhập lại")
            
    except json.JSONDecodeError as e:
        print(f"\n❌ Lỗi đọc file: {e}")
        print("   File auth.json không phải JSON hợp lệ")
    except Exception as e:
        print(f"\n❌ Lỗi: {e}")
else:
    print("\n❌ File auth.json không tìm thấy")
    print("   Chạy: python browser_login.py")

print("\n" + "=" * 60)
