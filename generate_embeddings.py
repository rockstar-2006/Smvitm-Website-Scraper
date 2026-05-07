import os
import json
import time
import numpy as np
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("Error: GOOGLE_API_KEY not found in .env file.")
    exit(1)

genai.configure(api_key=api_key)

DATA_PATH = os.path.join("data", "scraped_data.json")
EMB_PATH = os.path.join("data", "chunk_embeddings.npy")
PROGRESS_PATH = os.path.join("data", "partial_embeddings.npy")

if not os.path.exists(DATA_PATH):
    print(f"Error: {DATA_PATH} not found.")
    exit(1)

print(f"Loading data from {DATA_PATH}...")
with open(DATA_PATH, "r", encoding="utf-8") as f:
    raw_data = json.load(f)

print("Processing chunks...")
indexed_chunks = []
for item in raw_data:
    content = str(item.get("content") or "")
    title = str(item.get("title") or "")
    url = str(item.get("url") or "")

    paragraphs = content.split("\n")
    current_chunk = ""
    for line in paragraphs:
        current_chunk += line + "\n"
        if len(current_chunk) > 300 or line == "":
            p = current_chunk.strip()
            current_chunk = ""

            # Standard filtering logic from main.py
            dept_keywords = ["Computer Science", "Electronics", "Mechanical", "Civil", "Artificial Intelligence", "Data Science", "Machine Learning"]
            mention_count = sum(1 for d in dept_keywords if d in p)
            if mention_count > 2 and len(p) < 1000: continue
            if p.count("- ") > 8 or (p.count("Department") > 5 and len(p) < 400): continue
            if len(p) < 40: continue

            indexed_chunks.append(f"Title: {title}\nContent: {p}")

total_chunks = len(indexed_chunks)
print(f"Total chunks found: {total_chunks}")

# Resume logic
embeddings_list = []
start_idx = 0
if os.path.exists(PROGRESS_PATH):
    try:
        partial = np.load(PROGRESS_PATH)
        embeddings_list = partial.tolist()
        start_idx = len(embeddings_list)
        print(f"Resuming from index {start_idx} (loaded {start_idx} partial embeddings)...")
    except Exception as e:
        print(f"Could not load progress: {e}. Starting fresh.")
        embeddings_list = []
        start_idx = 0

batch_size = 1  # Testing batch size 1 to avoid TPM limits
print(f"Generating embeddings via Gemini... (Remaining: {total_chunks - start_idx} chunks)")

for i in range(start_idx, total_chunks, batch_size):
    batch = indexed_chunks[i : i + batch_size]
    # Only print every 50 to avoid clutter
    if i % 50 == 0:
        print(f"Embedding chunk {i}/{total_chunks}...")
    
    retries = 3
    success = False
    while retries > 0 and not success:
        try:
            resp = genai.embed_content(
                model="models/gemini-embedding-001",
                content=batch,
                task_type="retrieval_document",
            )
            embeddings_list.extend(resp["embedding"])
            success = True
            
            # Save progress every 50 chunks
            if i % 50 == 0:
                np.save(PROGRESS_PATH, np.array(embeddings_list, dtype="float32"))
                
        except Exception as e:
            print(f"Error at chunk {i}: {e}")
            retries -= 1
            if retries > 0:
                wait_time = 10
                print(f"Waiting {wait_time}s... ({retries} retries left)")
                time.sleep(wait_time)
            else:
                print("Failed. Progress saved.")
                np.save(PROGRESS_PATH, np.array(embeddings_list, dtype="float32"))
                exit(1)
    
    # Very small delay for batch size 1
    time.sleep(0.1)

print("All embeddings generated successfully!")
chunk_embeddings = np.array(embeddings_list, dtype="float32")

print(f"Saving final embeddings to {EMB_PATH}...")
np.save(EMB_PATH, chunk_embeddings)

# Cleanup
if os.path.exists(PROGRESS_PATH):
    os.remove(PROGRESS_PATH)

print("Done!")
