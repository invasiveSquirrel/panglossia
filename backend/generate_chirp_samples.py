import os
from google.cloud import texttospeech

def generate_samples():
    client = texttospeech.TextToSpeechClient()
    
    languages = {
        "sv-SE": "Hej, jag heter Elina. Hur kan jag hjälpa dig idag?",
        "de-DE": "Hallo, ich bin Katja. Wie kann ich dir heute helfen?",
        "fi-FI": "Hei, olen Aino. Kuinka voin auttaa sinua tänään?",
        "es-US": "Hola, soy Ximena. ¿Cómo puedo ayudarte hoy?",
        "nl-NL": "Hallo, ik ben Anika. Hoe kan ik je vandaag helpen?"
    }
    
    # Selecting 3 likely female names from the Chirp3 list
    female_variants = ["Aoede", "Leda", "Despina"]
    
    for lang_code, text in languages.items():
        for variant in female_variants:
            voice_name = f"{lang_code}-Chirp3-HD-{variant}"
            print(f"Generating sample for {voice_name}...")
            
            synthesis_input = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(language_code=lang_code, name=voice_name)
            audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16)
            
            try:
                response = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
                filename = f"/home/chris/panglossia/test_voices/{voice_name}.wav"
                os.makedirs("/home/chris/panglossia/test_voices", exist_ok=True)
                with open(filename, "wb") as out:
                    out.write(response.audio_content)
            except Exception as e:
                print(f"Failed to generate {voice_name}: {e}")

if __name__ == "__main__":
    generate_samples()
