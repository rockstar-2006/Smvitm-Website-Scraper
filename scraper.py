"""
Targeted scraper for SMVITM website.
Uses specific selectors discovered from DOM inspection.
"""
import requests
from bs4 import BeautifulSoup
import json
import os
import time
from urllib.parse import urljoin, urlparse

BASE = "https://sode-edu.in/smvitm/"

def make_session():
    s = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    s.headers.update(headers)
    try:
        s.get(BASE, timeout=20)
    except Exception as e:
        print(f"Homepage connection failed: {e}")
    return s

def extract_text(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    
    # Save links before decomposing
    links = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href and not href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
            full = urljoin(url, href).split('#')[0].rstrip('/')
            if 'sode-edu.in/smvitm' in full:
                links.add(full)

    # Clean up
    for tag in soup(["script", "style", "nav", "footer", "noscript", "iframe"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title else url

    # Targeted content extraction
    # SMVITM uses 'entry-content', 'wpb_wrapper', 'wpb_text_column'
    content_divs = soup.find_all("div", class_=["entry-content", "wpb_wrapper", "wpb_text_column"])
    
    lines = []
    # If it's a faculty page, capture labels and values
    if "/faculties/" in url:
        # Get the faculty name from h1
        name_h1 = soup.find("h1")
        if name_h1:
            lines.append(f"Faculty Name: {name_h1.get_text(strip=True)}")
        
        # Get all field labels and values
        for label in soup.find_all("label"):
            label_text = label.get_text(strip=True)
            parent = label.find_parent()
            value_text = parent.get_text(separator=" ", strip=True).replace(label_text, "").strip()
            if label_text and value_text:
                lines.append(f"{label_text}: {value_text}")

    # Also capture all standard text tags in priority order
    for el in soup.find_all(["h1","h2","h3","h4","p","li","td","th"]):
        # Skip if already captured in faculty logic (approximate check)
        txt = el.get_text(" ", strip=True)
        if len(txt) > 3:
            if el.name in ["h1", "h2"]:
                lines.append(f"\n## {txt}")
            elif el.name in ["h3", "h4"]:
                lines.append(f"\n# {txt}")
            elif el.name == "li":
                lines.append(f"- {txt}")
            else:
                lines.append(txt)

    # Deduplicate and format
    final_lines = []
    for l in lines:
        if not final_lines or l != final_lines[-1]:
            final_lines.append(l)
            
    content = "\n".join(final_lines)
    return title, content, links

def crawl():
    session = make_session()
    
    start_urls = [
        BASE,
        "https://sode-edu.in/smvitm/departments/computer-science-engineering/",
        "https://sode-edu.in/smvitm/sode-faculty/?dept_id=41", # CSE Faculty
        "https://sode-edu.in/smvitm/sode-faculty/?dept_id=23988", # AI&DS Faculty
        "https://sode-edu.in/smvitm/sode-faculty/?dept_id=23992", # AI&ML Faculty
        "https://sode-edu.in/smvitm/sode-faculty/?dept_id=43", # ECE Faculty
        "https://sode-edu.in/smvitm/sode-faculty/?dept_id=47", # ME Faculty
        "https://sode-edu.in/smvitm/sode-faculty/?dept_id=177", # CV Faculty
        "https://sode-edu.in/smvitm/faculties/sadananda-l/", # CSE HOD
        "https://sode-edu.in/smvitm/faculties/mr-ranjan-kumar-h-s/", # AI&DS HOD
    ]
    
    visited = set()
    queue = list(start_urls)
    scraped = []
    
    print(f"Starting crawl. Initial queue size: {len(queue)}")
    
    limit = 300
    while queue and len(scraped) < limit:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        
        print(f"[{len(scraped)+1}/{limit}] Fetching {url[:80]}...")
        try:
            r = session.get(url, timeout=15)
            if r.status_code != 200:
                print(f"  Fail {r.status_code}")
                continue
                
            title, content, links = extract_text(r.text, url)
            
            if len(content.strip()) > 100:
                scraped.append({"url": url, "title": title, "content": content})
                print(f"  ✓ Saved {len(content)} chars")
                
                # Add new links to queue
                for nl in links:
                    if nl not in visited and nl not in queue:
                        # Prioritize dept and faculty pages
                        if any(kw in nl for kw in ['/departments/', '/faculties/', '/sode-faculty/', '/about-us/', '/admission']):
                            queue.append(nl)
            else:
                print(f"  Short content ({len(content.strip())} chars)")
                
        except Exception as e:
            print(f"  Error: {e}")
        
        time.sleep(0.5) # Be gentle to the server
        
        # Save incrementally
        if len(scraped) % 5 == 0:
            os.makedirs("data", exist_ok=True)
            with open("data/scraped_data.json", "w", encoding="utf-8") as f:
                json.dump(scraped, f, indent=2, ensure_ascii=False)
    
    # Final Save
    os.makedirs("data", exist_ok=True)
    with open("data/scraped_data.json", "w", encoding="utf-8") as f:
        json.dump(scraped, f, indent=2, ensure_ascii=False)
    
    print(f"\nDone! Saved {len(scraped)} pages.")

if __name__ == "__main__":
    crawl()
