from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZIPMiddleware
from pydantic import BaseModel
from langchain_ollama import OllamaLLM
from langchain_google_genai import ChatGoogleGenerativeAI
from sqlalchemy import Column, Integer, String, UniqueConstraint, Index, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
import os
import asyncio
import subprocess
import re
import json
import hashlib
import aiofiles

# Database Setup
DB_PATH = "/home/chris/wordhord/wordhord.db"
engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}")
AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
Base = declarative_base()

class CardModel(Base):
    __tablename__ = "cards"
    id = Column(Integer, primary_key=True, index=True)
    language = Column(String)
    term = Column(String)
    translation = Column(String)
    ipa = Column(String)
    gender = Column(String)
    plural = Column(String)
    part_of_speech = Column(String)
    tone = Column(String)
    prefix = Column(String)
    preposition = Column(String)
    case = Column(String)
    conjugations = Column(String)
    example = Column(String)
    example_translation = Column(String)
    passed = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    __table_args__ = (
        UniqueConstraint('language', 'term', name='_language_term_uc'),
        Index('idx_language', 'language'),
    )

app = FastAPI()
app.add_middleware(GZIPMiddleware, minimum_size=1000)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Configuration
API_KEY_FILE = "/home/chris/wordhord/wordhord_api.txt"
with open(API_KEY_FILE, "r") as f:
    GOOGLE_API_KEY = f.read().strip()

# Gemini 2.5 Flash (Latest Stable)
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=GOOGLE_API_KEY, temperature=0.1)
# Local Fallback
ollama_llm = OllamaLLM(model=os.getenv("OLLAMA_MODEL", "gemma2:9b"), temperature=0.1)

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PIPER_BIN = os.path.join(BASE_DIR, "bin", "piper")
PIPER_LIB = os.path.join(BASE_DIR, "bin")
VOICE_DIR = os.path.join(BASE_DIR, "voices")
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")
CACHE_DIR = "/tmp/panglossia_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

try:
    from google.cloud import texttospeech
    from google.cloud import speech
except ImportError:
    texttospeech = None
    speech = None

async def get_system_prompt(language: str) -> str:
    prompt_file = os.path.join(PROMPTS_DIR, f"{language}.txt")
    if os.path.exists(prompt_file):
        async with aiofiles.open(prompt_file, "r") as f:
            content = await f.read()
            return content.strip()
    return "You are a helpful language tutor."

class ChatRequest(BaseModel):
    message: str
    language: str
    history: list = []

class SpeakRequest(BaseModel):
    text: str
    language: str
    speed: float = 1.0

def extract_field(section, field_name):
    pattern = fr'{field_name}:\s*(.*?)(?:\n\s*-|\n\s*Example:|\n\s*##|$)'
    match = re.search(pattern, section, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""

async def parse_and_save_vocab(language, response_text):
    pattern = r'- \*\*([^*]+)\*\*\s*\(([^)]+)\)'
    matches = list(re.finditer(pattern, response_text))
    if not matches: return

    async with AsyncSessionLocal() as db:
        for i, match in enumerate(matches):
            term = match.group(1).strip()
            translation = match.group(2).strip()
            start_pos = match.end()
            end_pos = matches[i+1].start() if i + 1 < len(matches) else len(response_text)
            section = response_text[start_pos:end_pos]
            
            stmt = select(CardModel).filter(CardModel.language == language, CardModel.term == term)
            result = await db.execute(stmt)
            existing = result.scalars().first()
            
            if existing:
                existing.translation = translation
                existing.ipa = extract_field(section, 'IPA')
                existing.gender = extract_field(section, 'Gender')
                existing.plural = extract_field(section, 'Plural')
                existing.part_of_speech = extract_field(section, 'Part of Speech')
                existing.tone = extract_field(section, 'Tone')
                existing.prefix = extract_field(section, 'Prefix')
                existing.preposition = extract_field(section, 'Preposition')
                existing.case = extract_field(section, 'Case')
                existing.conjugations = extract_field(section, 'Conjugations')
                card = existing
            else:
                card = CardModel(
                    language=language, term=term, translation=translation,
                    ipa=extract_field(section, 'IPA'),
                    gender=extract_field(section, 'Gender'),
                    plural=extract_field(section, 'Plural'),
                    part_of_speech=extract_field(section, 'Part of Speech'),
                    tone=extract_field(section, 'Tone'),
                    prefix=extract_field(section, 'Prefix'),
                    preposition=extract_field(section, 'Preposition'),
                    case=extract_field(section, 'Case'),
                    conjugations=extract_field(section, 'Conjugations'),
                )
                db.add(card)
            
            ex_match = re.search(r'Example:\s*"([^"]+)"\s*\(([^)]+)\)', section)
            if ex_match:
                card.example = ex_match.group(1)
                card.example_translation = ex_match.group(2)
            
            try:
                await db.commit()
            except Exception as e:
                print(f"Error saving vocab {term}: {e}")
                await db.rollback()

@app.post("/chat")
async def chat(request: ChatRequest):
    system_prompt = await get_system_prompt(request.language)
    
    # Format messages for Gemini Chat
    messages = [("system", system_prompt)]
    for msg in request.history:
        role = "user" if msg["role"] == "user" else "assistant"
        messages.append((role, msg["content"]))
    
    extra = ""
    if request.language == "swedish": extra = " For Swedish vocabulary, always mention the tone (Accent 1 or 2)."
    elif request.language in ["german", "dutch", "swedish"]:
        extra = f" For {request.language.capitalize()} verbs with a prefix, always state if they are 'Separable' or 'Inseparable' in a 'Prefix:' field."
    
    noun_instr = " ALL nouns MUST include their grammatical gender and their plural form in a 'Plural:' field."
    verb_instr = " ALL verbs must include any associated prepositions in a 'Preposition:' field and the grammatical case they govern (e.g., Accusative, Dative) in a 'Case:' field."
    fmt = "\nVOCABULARY format:\n- **Word** (Translation)\n  - IPA: [ipa]\n  - Part of Speech: [pos]\n  - Gender: [nouns only]\n  - Plural: [nouns only]\n  - Tone: [Swedish only]\n  - Prefix: [German/Dutch/Swedish verbs only]\n  - Preposition: [verbs only]\n  - Case: [verbs only]\n  - Conjugations: [forms]\n  Example: \"Sentence\" (Translation)"

    target_lang = request.language.capitalize()
    if request.language == "finnish":
        reminder = f"\n\n(REMINDER: Follow the requested LAYOUT exactly: Finnish paragraph, Swedish paragraph, [English] response, HELPFUL ADVICE, and VOCABULARY & EXAMPLES section. All examples MUST be in BOTH Finnish and Swedish.{extra}{noun_instr}{verb_instr}{fmt})"
    else:
        reminder = f"\n\n(REMINDER: Follow the requested LAYOUT exactly: {target_lang} paragraph(s), [English] response, HELPFUL ADVICE, and VOCABULARY & EXAMPLES section. All examples MUST be in {target_lang}.{extra}{noun_instr}{verb_instr}{fmt})"
    
    messages.append(("user", f"{request.message}{reminder}"))
    
    try:
        # Use Gemini primarily
        response_msg = await llm.ainvoke(messages)
        response = response_msg.content
    except Exception as e:
        # Fallback to Ollama if Gemini fails
        print(f"Gemini error, falling back: {e}")
        prompt_fallback = f"SYSTEM: {system_prompt}\n" + "\n".join([f"{m[0].upper()}: {m[1]}" for m in messages[1:]])
        response = await ollama_llm.ainvoke(prompt_fallback)
    
    # Extract and save to SQL database
    match = re.search(r'(?i)(VOCABULARY|EXPRESSIONS)', response)
    if match:
        asyncio.create_task(parse_and_save_vocab(request.language, response[match.start():]))
            
    return {"response": response}

@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...), language: str = Form(...)):
    if not speech or not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        raise HTTPException(status_code=501, detail="Speech-to-Text not configured")
    try:
        content = await audio.read()
        client = speech.SpeechClient()
        lang_codes = {"swedish": "sv-SE", "german": "de-DE", "finnish": "fi-FI", "portuguese": "pt-BR", "spanish": "es-US", "dutch": "nl-NL"}
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
            sample_rate_hertz=48000,
            language_code=lang_codes.get(language, "en-US"),
            alternative_language_codes=["sv-FI", "sv-SE"] if language == "finnish" else [],
        )
        response = client.recognize(config=config, audio=speech.RecognitionAudio(content=content))
        return {"transcript": " ".join([r.alternatives[0].transcript for r in response.results]).strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/speak")
async def speak(request: SpeakRequest):
    text = re.sub(r"^\d+\.\s*", "", request.text.split("[English]")[0].split("HELPFUL ADVICE")[0].split("VOCABULARY")[0].strip())
    if not text: return {"status": "ok"}

    speed = request.speed
    text_hash = hashlib.md5(f"{text}_{request.language}".encode()).hexdigest()
    cache_path = os.path.join(CACHE_DIR, f"{text_hash}.wav")

    if not os.path.exists(cache_path):
        if texttospeech and os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            try:
                client = texttospeech.TextToSpeechClient()
                gtts_map = {
                    "swedish": ("sv-SE", "sv-SE-Chirp3-HD-Laomedeia"),
                    "german": ("de-DE", "de-DE-Chirp3-HD-Leda"),
                    "finnish": ("fi-FI", "fi-FI-Chirp3-HD-Despina"),
                    "portuguese": ("pt-BR", "pt-BR-Chirp3-HD-Dione"),
                    "spanish": ("es-US", "es-US-Chirp3-HD-Callirrhoe"),
                    "dutch": ("nl-NL", "nl-NL-Chirp3-HD-Despina")
                }
                l_code, v_name = gtts_map.get(request.language, ("en-US", "en-US-Journey-F"))
                resp = client.synthesize_speech(
                    input=texttospeech.SynthesisInput(text=text),
                    voice=texttospeech.VoiceSelectionParams(language_code=l_code, name=v_name),
                    audio_config=texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16, speaking_rate=1.0)
                )
                async with aiofiles.open(cache_path, "wb") as out:
                    await out.write(resp.audio_content)
            except Exception: pass

        if not os.path.exists(cache_path):
            voice_map = {"swedish": "sv_female.onnx", "finnish": "fi_female.onnx", "spanish": "es_mx_ximena.onnx"}
            if request.language in voice_map:
                v_path = os.path.join(VOICE_DIR, voice_map[request.language])
                if os.path.exists(v_path):
                    env = os.environ.copy()
                    env["LD_LIBRARY_PATH"] = f"{PIPER_LIB}:{env.get('LD_LIBRARY_PATH', '')}"
                    proc = await asyncio.create_subprocess_exec(
                        PIPER_BIN, "--model", v_path, "--output_file", cache_path,
                        stdin=asyncio.subprocess.PIPE, env=env
                    )
                    await proc.communicate(input=text.encode())

    if os.path.exists(cache_path):
        subprocess.Popen(["ffplay", "-nodisp", "-autoexit", "-af", f"atempo={speed}", "-loglevel", "quiet", cache_path])
        return {"status": "ok"}

    raise HTTPException(status_code=404, detail="No voice available")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
