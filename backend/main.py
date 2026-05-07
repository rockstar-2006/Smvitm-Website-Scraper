from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
import json
import os
import requests
import io
from dotenv import load_dotenv
import re
import time

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MURF_API_KEY = os.getenv("MURF_API_KEY")

groq_client = None
if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)
    print("Groq client initialized successfully.")
else:
    print("WARNING: GROQ_API_KEY not found. AI features are disabled.")


app = FastAPI()


# Helper guard for missing AI configuration
def ensure_ai_enabled():
    if groq_client is None:
        raise HTTPException(
            status_code=503,
            detail="AI is not configured. Set GROQ_API_KEY in .env to enable chat.",
        )


# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load scraped data
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "scraped_data.json")
indexed_chunks = []

try:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    # Pre-process chunks for faster retrieval
    for item in raw_data:
        content = str(item.get("content") or "")
        title = str(item.get("title") or "")
        url = str(item.get("url") or "")

        paragraphs = content.split("\n")
        current_chunk = ""
        for line in paragraphs:
            current_chunk += line + "\n"
            if len(current_chunk) > 1000 or line == "":
                p = current_chunk.strip()
                current_chunk = ""

                # HEURISTIC: Filter out navigation-heavy chunks (sidebars) but keep department listings
                dept_keywords = ["Computer Science", "Electronics", "Mechanical", "Civil", "Artificial Intelligence", "Data Science", "Machine Learning"]
                mention_count = sum(1 for d in dept_keywords if d in p)

                # Only skip if it's EXTREMELY link-heavy and very small (sidebar detection)
                if (mention_count > 10 and len(p) < 400) or (p.count("- ") > 30 and len(p) < 500):
                    continue

                if len(p) < 40:  # Only skip tiny chunks
                    continue

                indexed_chunks.append(
                    {
                        "content": p,
                        "title": title,
                        "url": url,
                        "source": url,
                        "title_lower": title.lower(),
                        "content_lower": p.lower(),
                    }
                )
    print(f"Successfully loaded {len(indexed_chunks)} chunks from knowledge base.")
except Exception as e:
    print(f"Error loading data: {e}")


class ChatRequest(BaseModel):
    message: str


def get_relevant_context(query: str, max_chunks: int = 20) -> list:
    """
    Keyword-based search for relevant chunks from the scraped knowledge base.
    """
    if not indexed_chunks:
        return []

    query_raw = query.lower()
    query_words = set(re.findall(r"\w+", query_raw))
    stop_words = {"the", "is", "of", "and", "a", "who", "what", "where", "tell", "me", "about", "for", "in", "at", "to", "how", "many", "are"}
    
    # Allow 2-letter words if they are department abbreviations or key terms
    academic_shorts = {"ai", "ds", "ml", "cs", "ec", "me", "be"}
    keywords = {w for w in query_words if (len(w) > 2 or w in academic_shorts) and w not in stop_words}

    # Special boosts for HOD/Faculty queries
    faculty_indicators = {"hod", "head", "faculty", "professor", "teacher", "principal", "dean", "name"}
    query_has_faculty_intent = any(w in query_words for w in faculty_indicators)

    keyword_scored_chunks = []
    for chunk in indexed_chunks:
        score = 0
        c_lower = chunk["content_lower"]
        t_lower = chunk["title_lower"]

        for word in keywords:
            if word in t_lower:
                score += 15  # High boost for title matches
            if word in c_lower:
                score += 3   # Normal boost for content matches

        # Extra boost for faculty-specific chunks if user is asking about faculty
        if query_has_faculty_intent:
            if any(term in c_lower for term in ["designation", "hod", "head of department", "professor"]):
                score += 10
            if "faculty name" in c_lower:
                score += 15

        for word in keywords:
            if word in chunk["url"].lower():
                score += 5

        if score > 0:
            keyword_scored_chunks.append((score, chunk))

    results = [c for s, c in sorted(keyword_scored_chunks, key=lambda x: x[0], reverse=True)[:max_chunks]]
    return results


@app.post("/chat")
async def chat(request: ChatRequest):
    user_query = request.message
    print(f"Received query: {user_query}")
    ensure_ai_enabled()

    # 1. Get context
    try:
        context_chunks = get_relevant_context(user_query)
        print(f"Found {len(context_chunks)} relevant chunks")
    except Exception as e:
        print(f"Error in context retrieval: {e}")
        raise HTTPException(status_code=500, detail=f"Context retrieval error: {str(e)}")

    if not context_chunks:
        context_str = "No specific information found on the website for this query."
    else:
        context_str = "\n\n".join(
            [
                f"--- Source: {c['title']} ({c['source']}) ---\n{c['content']}"
                for c in context_chunks
            ]
        )

    # 2. Build prompt and call Groq
    system_prompt = (
        "You are the \"SMVITM Virtual Assistant\", an expert academic advisor for Shri Madhwa Vadiraja Institute of Technology and Management.\n\n"
        "GOAL: Provide HIGHLY STRUCTURED, professional, and exhaustive information based on the provided context. Avoid 'walls of text'.\n\n"
        "CORE DIRECTIVES:\n"
        "1. STRUCTURAL HIERARCHY: Use Markdown headings (## and ###) to separate different topics. Each major part of your answer must have a heading.\n"
        "2. EXHAUSTIVE DETAIL: Provide all relevant information from the context. Do not be brief. If the user asks about a program, include overview, objectives, outcomes, and eligibility.\n"
        "3. FORMATTING FOR READABILITY:\n"
        "   - Use **bold labels** for key information (e.g., **Intake Capacity:** 120).\n"
        "   - Use bullet points for lists (PEOs, POs, Courses, etc.).\n"
        "   - Use horizontal rules (---) to separate major sections if the response is long.\n"
        "4. DATA INTEGRITY: Use exact names, titles, and numbers from the RELIABLE CONTEXT.\n"
        "5. FLEXIBILITY: Handle any query dynamically. Synthesize a unified, deep answer across multiple context chunks.\n"
        "6. PROFESSIONAL TONE: Maintain a helpful, academic, and professional persona."
    )


    user_message = f"### RELIABLE CONTEXT:\n{context_str}\n\n---\nUSER QUESTION: {user_query}\n\nYOUR DIRECT ANSWER:"

    try:
        print("Calling Groq API...")
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=1024,
        )
        answer = completion.choices[0].message.content
        print("Groq response received.")
        return {
            "response": answer,
            "sources": [c["source"] for c in context_chunks] if context_chunks else [],
        }
    except Exception as e:
        print(f"Error calling Groq: {e}")
        raise HTTPException(status_code=500, detail=f"Groq API error: {str(e)}")


@app.post("/chat/voice")
async def chat_voice(audio: UploadFile = File(...)):
    print("Received audio file")
    audio_data = await audio.read()
    ensure_ai_enabled()

    # 1. Transcribe the audio using Groq Whisper
    user_query = ""
    try:
        print("Calling Groq Whisper for transcription...")
        transcription = groq_client.audio.transcriptions.create(
            file=(audio.filename or "audio.webm", audio_data, audio.content_type or "audio/webm"),
            model="whisper-large-v3",
            response_format="text",
        )
        user_query = transcription.strip() if isinstance(transcription, str) else transcription.text.strip()
        print(f"Transcribed User Query: {user_query}")
    except Exception as e:
        print(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail=f"Could not transcribe audio: {str(e)}")

    # 2. Get context
    try:
        context_chunks = get_relevant_context(user_query)
        if not context_chunks:
            context_str = "No specific information found on the website for this query."
        else:
            context_str = "\n\n".join(
                [
                    f"--- Source: {c['title']} ({c['source']}) ---\n{c['content']}"
                    for c in context_chunks
                ]
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Context retrieval error: {str(e)}")

    # 3. Generate concise conversational voice response via Groq
    system_prompt = (
        "You are the \"SMVITM Virtual Assistant\". Answer directly and intelligently.\n\n"
        "RULES:\n"
        "1. Prioritize the provided context for SMVITM specific details.\n"
        "2. If the context is missing, use your general knowledge to answer the user's query.\n"
        "3. No Markdown. Speak in a natural, continuous conversational flow without bullet points, hashes, or asterisks.\n"
        "4. Tone: Polite, Natural Indian English."
    )


    user_message = f"### RELIABLE CONTEXT:\n{context_str}\n\n---\nUSER QUESTION: {user_query}\n\nVOICE ANSWER:"

    try:
        print("Calling Groq for text response...")
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=512,
        )
        text_response = completion.choices[0].message.content.replace("*", "").replace("#", "").strip()
        print(f"Generated Text: {text_response}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Groq API error: {str(e)}")

    # 4. Generate TTS via Murf.ai (Aarav voice)
    audio_url = ""
    try:
        murf_url = "https://api.murf.ai/v1/speech/stream"
        murf_headers = {
            "api-key": MURF_API_KEY,
            "Content-Type": "application/json",
        }
        murf_payload = {
            "text": text_response,
            "voiceId": "Aarav",
            "model": "FALCON",
            "style": "Conversational",
        }
        print(f"Calling Murf.ai Aarav voice for {len(text_response)} chars...")
        murf_resp = requests.post(murf_url, json=murf_payload, headers=murf_headers, timeout=15)
        if murf_resp.status_code == 200:
            timestamp = int(time.time())
            audio_filename = f"voice_response_{timestamp}.wav"
            audio_path = os.path.join(os.path.dirname(__file__), "..", "frontend", audio_filename)

            # Clean up old voice files
            try:
                frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
                for f in os.listdir(frontend_dir):
                    if f.startswith("voice_response_") and f.endswith(".wav"):
                        os.remove(os.path.join(frontend_dir, f))
            except Exception:
                pass

            with open(audio_path, "wb") as f:
                f.write(murf_resp.content)
            audio_url = f"/static/{audio_filename}?v={timestamp}"
            print(f"Murf TTS saved as {audio_filename}")
        else:
            print(f"Murf API failed: {murf_resp.status_code} - {murf_resp.text[:100]}")
    except Exception as e:
        print(f"Murf TTS Error: {e}")

    return {
        "user_query": user_query,
        "response": text_response,
        "audio_url": audio_url,
        "sources": [c["source"] for c in context_chunks] if context_chunks else [],
    }


from fastapi.staticfiles import StaticFiles

# Serve frontend static files
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=frontend_path), name="static")


@app.get("/")
async def root():
    return {"message": "SMVITM Chatbot API is running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
