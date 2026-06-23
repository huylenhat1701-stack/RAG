import requests, sys, json
sys.stdout.reconfigure(encoding='utf-8')
BASE = 'http://localhost:8000/api/v1'

print('=== TEST 1: Health Check ===')
r = requests.get(f'{BASE}/health')
print(f'Status: {r.status_code}')
print(json.dumps(r.json(), ensure_ascii=False, indent=2))

print()
print('=== TEST 2: Danh sach tai lieu ===')
r = requests.get(f'{BASE}/documents')
print(f'Status: {r.status_code}')
data = r.json()
print(f'So tai lieu: {data.get("total", 0)}')

print()
print('=== TEST 3: Lich su chat ===')
r = requests.get(f'{BASE}/chat/history?limit=3')
print(f'Status: {r.status_code}')
data = r.json()
print(f'So lich su: {data.get("total", 0)}')

print()
print('=== TEST 4: Chat Ask (khong co tai lieu) ===')
r = requests.post(f'{BASE}/chat/ask', json={'question': 'xin chao', 'top_k': 3, 'history': []})
print(f'Status: {r.status_code}')
data = r.json()
if r.status_code == 200:
    print(f'Answer: {data.get("answer", "")[:200]}')
else:
    print(f'Error: {data}')

print()
print('=== KET QUA TONG KET ===')
all_ok = True
