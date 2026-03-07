from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_ollama import OllamaLLM
from sqlalchemy import create_engine, Column, Integer, String, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
import os
import subprocess
import re
import json

# Database Setup (Sharing Wordhord's DB)
DB_PATH = "/home/chris/wordhord.db"
engine = create_engine(f"sqlite:///{DB_PATH}")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class CardModel(Base):
    __tablename__ = "cards"
    id = Column(Integer, primary_key=True, index=True)
    language = Column(String)
    term = Column(String)
    translation = Column(String)
    ipa = Column(String)
    gender = Column(String)
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
    __table_args__ = (UniqueConstraint('language', 'term', name='_language_term_uc'),)

Base.metadata.create_all(bind=engine)

try:
    from google.cloud import texttospeech
    from google.cloud import speech
except ImportError:
    texttospeech = None
    speech = None

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
MODEL_NAME = os.getenv("OLLAMA_MODEL", "gemma2:9b")
llm = OllamaLLM(model=MODEL_NAME, temperature=0.1)

# Paths for Piper TTS and Prompts
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PIPER_BIN = os.path.join(BASE_DIR, "bin", "piper")
PIPER_LIB = os.path.join(BASE_DIR, "bin")
VOICE_DIR = os.path.join(BASE_DIR, "voices")
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")

def get_system_prompt(language: str) -> str:
    prompt_file = os.path.join(PROMPTS_DIR, f"{language}.txt")
    if os.path.exists(prompt_file):
        with open(prompt_file, "r") as f:
            return f.read().strip()
    return "You are a helpful language tutor."

class ChatRequest(BaseModel):
    message: str
    language: str
    history: list = []

class SpeakRequest(BaseModel):
    text: str
    language: str

def extract_field(section, field_name):
    pattern = fr'{field_name}:\s*(.*?)(?:\n\s*-|\n\s*Example:|\n\s*##|$)'
    match = re.search(pattern, section, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""

def parse_and_save_vocab(language, response_text):
    # Regex to find cards: - **term** (translation)
    pattern = r'- \*\*([^*]+)\*\*\s*\(([^)]+)\)'
    matches = list(re.finditer(pattern, response_text))
    
    if not matches:
        return

    db = SessionLocal()
    for i, match in enumerate(matches):
        term = match.group(1).strip()
        translation = match.group(2).strip()
        
        start_pos = match.end()
        end_pos = matches[i+1].start() if i + 1 < len(matches) else len(response_text)
        section = response_text[start_pos:end_pos]
        
        card = CardModel(
            language=language,
            term=term,
            translation=translation,
            ipa=extract_field(section, 'IPA'),
            gender=extract_field(section, 'Gender'),
            part_of_speech=extract_field(section, 'Part of Speech'),
            tone=extract_field(section, 'Tone'),
            prefix=extract_field(section, 'Prefix'),
            preposition=extract_field(section, 'Preposition'),
            case=extract_field(section, 'Case'),
            conjugations=extract_field(section, 'Conjugations'),
        )
        
        ex_match = re.search(r'Example:\s*"([^"]+)"\s*\(([^)]+)\)', section)
        if ex_match:
            card.example = ex_match.group(1)
            card.example_translation = ex_match.group(2)
        
        try:
            db.merge(card)
            db.commit()
        except Exception as e:
            print(f"Error saving vocab {term}: {e}")
            db.rollback()
    db.close()

@app.post("/chat")
async def chat(request: ChatRequest):
    system_prompt = get_system_prompt(request.language)
    prompt_text = f"INSTRUCTION: {system_prompt}\n\n"
    
    for msg in request.history:
        role = "USER" if msg["role"] == "user" else "ASSISTANT"
        prompt_text += f"{role}: {msg['content']}\n"
    
    extra_instructions = ""
    if request.language == "swedish":
        extra_instructions = " For Swedish vocabulary, always mention the tone (Accent 1 or 2)."
    elif request.language == "german":
        extra_instructions = " For German verbs with a prefix, always state if they are 'Separable' or 'Inseparable' in a 'Prefix:' field."
    
    verb_instructions = " ALL verbs must include any associated prepositions in a 'Preposition:' field and the grammatical case they govern in a 'Case:' field."
    format_instruction = "\nVOCABULARY format:\n- **Word** (Translation)\n  - IPA: [ipa]\n  - Part of Speech: [pos]\n  - Gender: [if applicable]\n  - Tone: [Swedish only]\n  - Prefix: [German verbs only]\n  - Preposition: [verbs only]\n  - Case: [verbs only]\n  - Conjugations: [forms]\n  Example: \"Sentence\" (Translation)"

    if request.language == "finnish":
        layout_reminder = f"\n\n(REMINDER: Follow the requested LAYOUT exactly: Finnish paragraph, Swedish paragraph, [English] response, HELPFUL ADVICE, and VOCABULARY & EXAMPLES section. All examples MUST be in BOTH Finnish and Swedish.{extra_instructions}{verb_instructions}{format_instruction})"
    else:
        target_lang = request.language.capitalize()
        layout_reminder = f"\n\n(REMINDER: Follow the requested LAYOUT exactly: {target_lang} paragraph(s), [English] response, HELPFUL ADVICE, and VOCABULARY & EXAMPLES section. All examples MUST be in {target_lang}.{extra_instructions}{verb_instructions}{format_instruction})"
    
    prompt_text += f"USER: {request.message}{layout_reminder}\nASSISTANT:"
    
    try:
        response = llm.invoke(prompt_text, stop=["USER:", "User:", "System:"])
        
        if "USER:" in response: response = response.split("USER:")[0].strip()
        if "User:" in response: response = response.split("User:")[0].strip()
            
        # Extract and save to SQL database
        match = re.search(r'(?i)(VOCABULARY|EXPRESSIONS)', response)
        if match:
            parse_and_save_vocab(request.language, response[match.start():])
            
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
    text_to_speak = re.sub(r"^\d+\.\s*", "", request.text.split("[English]")[0].split("HELPFUL ADVICE")[0].split("VOCABULARY")[0].strip())
    if not text_to_speak: return {"status": "ok"}

    if texttospeech and os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        try:
            client = texttospeech.TextToSpeechClient()
            gtts_voice_map = {
                "swedish": ("sv-SE", "sv-SE-Chirp3-HD-Laomedeia"),
                "german": ("de-DE", "de-DE-Chirp3-HD-Leda"),
                "finnish": ("fi-FI", "fi-FI-Chirp3-HD-Despina"),
                "portuguese": ("pt-BR", "pt-BR-Chirp3-HD-Dione"),
                "spanish": ("es-US", "es-US-Chirp3-HD-Callirrhoe"),
                "dutch": ("nl-NL", "nl-NL-Chirp3-HD-Despina"),
                "scottish_gaelic": ("en-GB", "en-GB-Wavenet-B")
            }
            l_code, v_name = gtts_voice_map.get(request.language, ("en-US", "en-US-Journey-F"))
            response = client.synthesize_speech(
                input=texttospeech.SynthesisInput(text=text_to_speak),
                voice=texttospeech.VoiceSelectionParams(language_code=l_code, name=v_name),
                audio_config=texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16, speaking_rate=0.95)
            )
            with open("/tmp/polyglossia_gtts.wav", "wb") as out: out.write(response.audio_content)
            subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "/tmp/polyglossia_gtts.wav"], check=False)
            return {"status": "ok"}
        except Exception: pass

    voice_map = {"swedish": "sv_female.onnx", "finnish": "fi_female.onnx", "spanish": "es_mx_ximena.onnx"}
    if request.language in voice_map:
        v_path = os.path.join(VOICE_DIR, voice_map[request.language])
        if os.path.exists(v_path):
            temp_wav = "/tmp/polyglossia_local.wav"
            env = os.environ.copy()
            env["LD_LIBRARY_PATH"] = f"{PIPER_LIB}:{env.get('LD_LIBRARY_PATH', '')}"
            cmd = [PIPER_BIN, "--model", v_path, "--output_file", temp_wav]
            subprocess.run(cmd, input=text_to_speak, text=True, env=env, check=False)
            subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", temp_wav], check=False)
            return {"status": "ok"}

    raise HTTPException(status_code=404, detail="No voice available")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
