import json
import re
import os

# Load the indexed chunks (simulate the backend logic)
DATA_PATH = "data/scraped_data.json"
with open(DATA_PATH, "r", encoding="utf-8") as f:
    raw_data = json.load(f)

indexed_chunks = []
for item in raw_data:
    content = item.get("content", "")
    title = item.get("title", "")
    url = item.get("url", "")
    paragraphs = content.split("\n")
    current_chunk = ""
    for line in paragraphs:
        current_chunk += line + "\n"
        if len(current_chunk) > 300 or line == "":
            p = current_chunk.strip()
            current_chunk = ""
            if p.count("- ") > 8 or (p.count("Department") > 5 and len(p) < 400): continue
            if len(p) < 40: continue
            indexed_chunks.append({"content": p, "title": title, "url": url, "source": url, "title_lower": title.lower(), "content_lower": p.lower()})

def get_best_for(query):
    query_raw = query.lower()
    query_words = re.findall(r'\w+', query_raw)
    is_hod_query = any(w in query_raw for w in ["hod", "head", "principal", "dean"])
    keywords = [w for w in query_words if len(w) > 3 or w in ["cs", "is", "ec", "me"]]
    scored_chunks = []
    for chunk in indexed_chunks:
        score = 0
        p_lower = chunk["content_lower"]
        t_lower = chunk["title_lower"]
        url_lower = chunk["source"].lower()
        for word in keywords:
            if word in p_lower: score += 1
            if word in t_lower: score += 3
        if is_hod_query:
            if "hod" in p_lower or "head" in p_lower: score += 30
            if "/faculties/" in url_lower: score += 50
            if "cse" in query_raw and "computer science" in p_lower: score += 100
        if "faculty" in query_raw or "count" in query_raw:
            if "/sode-faculty/" in url_lower: score += 80
        if score > 0:
            scored_chunks.append({"score": score, "title": chunk["title"], "source": chunk["source"], "content": chunk["content"][:150]})
    
    sorted_chunks = sorted(scored_chunks, key=lambda x: x["score"], reverse=True)
    return sorted_chunks[:10]

print("TEST: How many faculty in CSE")
for res in get_best_for("How many faculty in CSE"):
    print(f"Score {res['score']}: {res['title']} ({res['source']}) -> {res['content']}...")
