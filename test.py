import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

url = "https://sode-edu.in/smvitm/"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}
response = requests.get(url, headers=headers, timeout=15)
print("Status:", response.status_code)
print("Content-Type:", response.headers.get('Content-Type'))

if response.status_code == 200:
    soup = BeautifulSoup(response.text, 'html.parser')
    links = [urljoin(url, a['href']) for a in soup.find_all('a', href=True)]
    print(f"Found {len(links)} links")
    for script in soup(["script", "style"]):
        script.decompose()
    text = soup.get_text(separator='\n')
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = '\n'.join(chunk for chunk in chunks if chunk)
    print("Content Length:", len(text))
    print("Content preview:", text[:100])
