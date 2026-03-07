import os
import json
from google.cloud import texttospeech

def list_best_voices():
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        print("Error: GOOGLE_APPLICATION_CREDENTIALS not set.")
        return

    client = texttospeech.TextToSpeechClient()
    response = client.list_voices()
    
    target_langs = ["sv-SE", "de-DE", "fi-FI", "es-US", "nl-NL"]
    best_voices = {lang: None for lang in target_langs}
    
    # Priority: Journey > Neural2 > Wavenet > Standard
    def get_priority(name):
        if "Journey" in name: return 4
        if "Neural2" in name: return 3
        if "Wavenet" in name: return 2
        return 1

    for voice in response.voices:
        for lang_code in voice.language_codes:
            if lang_code in target_langs and voice.ssml_gender == texttospeech.SsmlVoiceGender.FEMALE:
                current_best = best_voices[lang_code]
                if not current_best or get_priority(voice.name) > get_priority(current_best.name):
                    best_voices[lang_code] = voice
                elif get_priority(voice.name) == get_priority(current_best.name):
                    # Prefer later alphabetical for variety if same tier
                    if voice.name > current_best.name:
                        best_voices[lang_code] = voice

    for lang, voice in best_voices.items():
        if voice:
            print(f"{lang}: {voice.name} ({voice.ssml_gender})")
        else:
            print(f"{lang}: No female voice found.")

if __name__ == "__main__":
    list_best_voices()
