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
            
            dept_keywords = ["Computer Science", "Electronics", "Mechanical", "Civil", "Artificial Intelligence", "Data Science", "Machine Learning"]
            mention_count = sum(1 for d in dept_keywords if d in p)
            if mention_count > 2 and len(p) < 1000: continue
            if p.count("- ") > 8 or (p.count("Department") > 5 and len(p) < 400): continue
            if len(p) < 40: continue
            
            indexed_chunks.append({"content": p, "title": title, "url": url, "title_lower": title.lower(), "content_lower": p.lower()})

def get_best_for(query):
    query_raw = query.lower()
    query_words = re.findall(r'\w+', query_raw)
    is_hod_query = any(w in query_raw for w in ["hod", "head", "principal", "dean"])
    keywords = [w for w in query_words if len(w) > 3 or w in ["cs", "is", "ec", "me"]]
    scored = []
    for chunk in indexed_chunks:
        score = 0
        p_l = chunk["content_lower"]
        t_l = chunk["title_lower"]
        u_l = chunk["url"].lower()
        for word in keywords:
            if word in p_l: score += 1
            if word in t_l: score += 3
        if is_hod_query:
            if "hod" in p_l or "head" in p_l: score += 30
            if "/faculties/" in u_l: score += 50
            # Aggressive Alignment
            if ("cse" in query_raw or "computer" in query_raw) and "computer science" in p_l: score += 100
            if "aids" in query_raw and ("data science" in p_l or "data science" in t_l): score += 100
            if ("ece" in query_raw or "electronics" in query_raw) and "electronics" in p_l: score += 100
        if "short term" in query_raw and ("short term" in p_l or "short term" in t_l): score += 50
        if score > 0:
            scored.append({"score": score, "title": chunk["title"], "content": chunk["content"][:200]})
    return sorted(scored, key=lambda x: x["score"], reverse=True)[:3]

test_cases = [
    "Who is the HOD of CSE?",
    "Tell me about AI&DS department",
    "What are the short term courses?",
    "Placement and training details",
    "sandeepa-prabhu faculty designation"
]

for q in test_cases:
    print(f"\n--- QUERY: {q} ---")
    results = get_best_for(q)
    for res in results:
        print(f"  Score {res['score']}: {res['title']} -> {res['content']}...")
