from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_ollama import OllamaLLM
import os
import subprocess
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
    
    # Fallback to hardcoded prompts if file missing
    prompts = {
        "swedish": "You are Elina, a therapist from Stockholm...",
        "german": "You are Katja, a therapist from Berlin...",
        "finnish": "You are Aino, a bilingual therapist from Helsinki and Porvoo. You practice in both Finnish and Swedish. Practice both with the user, as they are both official languages of Finland.",
        "portuguese": "You are Luciana, a warm and energetic therapist from Rio de Janeiro, Brazil. You practice Brazilian Portuguese with the user.",
        "spanish": "You are Ximena, a therapist from Mexico City...",
        "dutch": "You are Anika, a therapist from Amsterdam..."
    }
    return prompts.get(language, "You are a helpful language tutor.")

class ChatRequest(BaseModel):
    message: str
    language: str
    history: list = []

class SpeakRequest(BaseModel):
    text: str
    language: str

@app.post("/chat")
async def chat(request: ChatRequest):
    system_prompt = get_system_prompt(request.language)
    
    # Gemma 2 works best with clear instruction boundaries
    prompt_text = f"INSTRUCTION: {system_prompt}\n\n"
    
    for msg in request.history:
        role = "USER" if msg["role"] == "user" else "ASSISTANT"
        prompt_text += f"{role}: {msg['content']}\n"
    
    # Add a strict layout reminder at the end of the user's current message
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
        # Request the model and explicitly set stop tokens if supported, 
        # otherwise we handle the truncation manually below.
        response = llm.invoke(prompt_text, stop=["USER:", "User:", "System:"])
        
        # Manual safety check: Truncate if the model hallucinates a User section anyway
        if "USER:" in response:
            response = response.split("USER:")[0].strip()
        if "User:" in response:
            response = response.split("User:")[0].strip()
            
        # Extract Vocabulary and Examples and save to a markdown file
        import re
        match = re.search(r'(?i)(VOCABULARY|EXPRESSIONS)', response)
        if match:
            vocab_section = response[match.start():].strip()
            vocab_file = os.path.join(os.path.dirname(BASE_DIR), f"{request.language}_vocab.md")
            with open(vocab_file, "a", encoding="utf-8") as vf:
                vf.write(f"\n\n---\n\n{vocab_section}\n")
            
        return {"response": response}
    except Exception as e:
        print(f"DEBUG: Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...), language: str = Form(...)):
    if not speech or not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        raise HTTPException(status_code=501, detail="Speech-to-Text not configured")

    try:
        content = await audio.read()
        client = speech.SpeechClient()
        
        lang_codes = {"swedish": "sv-SE", "german": "de-DE", "finnish": "fi-FI", "portuguese": "pt-BR", "spanish": "es-US", "dutch": "nl-NL"}
        target_lang = lang_codes.get(language, "en-US")
        
        # Support alternative languages for bilingual tutors (e.g., Finnish tutor also speaks Swedish)
        alt_langs = []
        if language == "finnish":
            alt_langs = ["sv-FI", "sv-SE"]

        audio_config = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
            sample_rate_hertz=48000,
            language_code=target_lang,
            alternative_language_codes=alt_langs,
        )

        response = client.recognize(config=config, audio=audio_config)
        
        transcript = ""
        for result in response.results:
            transcript += result.alternatives[0].transcript + " "
            
        return {"transcript": transcript.strip()}
    except Exception as e:
        print(f"DEBUG: Transcribe error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/speak")
async def speak(request: SpeakRequest):
    # Only speak text BEFORE any header section or the [English] marker
    # Also strip out list markers like "1. " at the beginning of the text
    import re
    text_to_speak = request.text.split("[English]")[0].split("HELPFUL ADVICE")[0].split("VOCABULARY")[0].strip()
    text_to_speak = re.sub(r"^\d+\.\s*", "", text_to_speak)
    
    if not text_to_speak:
        return {"status": "ok"}

    if texttospeech and os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        try:
            import json
            with open(os.environ["GOOGLE_APPLICATION_CREDENTIALS"], 'r') as f:
                creds = json.load(f)
                if "YOUR_PROJECT_ID" in str(creds.get("project_id", "")):
                    raise ValueError("Placeholder credentials detected")

            client = texttospeech.TextToSpeechClient()
            synthesis_input = texttospeech.SynthesisInput(text=text_to_speak)
            
            gtts_voice_map = {
                "swedish": texttospeech.VoiceSelectionParams(language_code="sv-SE", name="sv-SE-Chirp3-HD-Laomedeia"),
                "german": texttospeech.VoiceSelectionParams(language_code="de-DE", name="de-DE-Chirp3-HD-Leda"),
                "finnish": texttospeech.VoiceSelectionParams(language_code="fi-FI", name="fi-FI-Chirp3-HD-Despina"),
                "portuguese": texttospeech.VoiceSelectionParams(language_code="pt-BR", name="pt-BR-Chirp3-HD-Dione"),
                "spanish": texttospeech.VoiceSelectionParams(language_code="es-US", name="es-US-Chirp3-HD-Callirrhoe"),
                "dutch": texttospeech.VoiceSelectionParams(language_code="nl-NL", name="nl-NL-Chirp3-HD-Despina")
            }
            
            voice = gtts_voice_map.get(request.language, texttospeech.VoiceSelectionParams(language_code="en-US", name="en-US-Journey-F"))
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                pitch=0.0,
                speaking_rate=0.95
            )
            
            response = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
            
            gtts_wav = "/tmp/polyglossia_gtts.wav"
            with open(gtts_wav, "wb") as out:
                out.write(response.audio_content)
                
            subprocess.run(["aplay", gtts_wav], check=True)
            return {"status": "ok"}
        except Exception as e:
            print(f"DEBUG: Google TTS error: {e}, falling back to local TTS...")

    voice_map = {
        "swedish": os.path.join(VOICE_DIR, "sv_female.onnx"),
        "finnish": os.path.join(VOICE_DIR, "fi_female.onnx"),
        "spanish": os.path.join(VOICE_DIR, "es_mx_ximena.onnx")
    }
    
    if request.language in voice_map and os.path.exists(voice_map[request.language]):
        voice_path = voice_map[request.language]
        temp_wav = "/tmp/polyglossia_raw.wav"
        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = f"{PIPER_LIB}:{env.get('LD_LIBRARY_PATH', '')}"
        
        try:
            cmd = [PIPER_BIN, "--model", voice_path, "--output_file", temp_wav, "--length_scale", "1.1"]
            process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=BASE_DIR)
            process.communicate(input=text_to_speak)
            
            if process.returncode == 0:
                subprocess.run(["aplay", temp_wav], check=True)
                return {"status": "ok"}
        except Exception as e:
            print(f"DEBUG: Piper/SoX error: {e}")

    lang_codes = {"swedish": "sv-SE", "german": "de-DE", "finnish": "fi-FI", "spanish": "es-US", "dutch": "nl-NL"}
    raise HTTPException(status_code=404, detail="No high-quality backend voice available, fallback to browser.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
