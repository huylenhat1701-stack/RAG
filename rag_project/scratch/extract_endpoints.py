import re

def extract():
    with open('frontend/app.py', encoding='utf-8') as f:
        text = f.read()
    
    matches = re.findall(r'api_(?:get|post|delete)\(f?[\'"]([^\'"]+)[\'"]', text)
    for m in set(matches):
        print(m)

if __name__ == '__main__':
    extract()
