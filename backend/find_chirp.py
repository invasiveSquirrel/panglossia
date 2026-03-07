import os
from google.cloud import texttospeech

def find_best_swedish_female():
    client = texttospeech.TextToSpeechClient()
    response = client.list_voices()
    
    # Filter for Swedish Chirp3 voices with Female gender
    # Note: Chirp voices often don't have gender metadata in the list_voices response, 
    # but we can try common female-coded names from the list.
    female_names = ["Aoede", "Autonoe", "Callirrhoe", "Despina", "Erinome", "Kore", "Leda", "Puck"]
    
    found = []
    for voice in response.voices:
        if "sv-SE-Chirp3" in voice.name:
            # Check if it's explicitly female or one of our suspected female names
            is_female = voice.ssml_gender == texttospeech.SsmlVoiceGender.FEMALE
            is_suspected = any(name in voice.name for name in female_names)
            
            if is_female or is_suspected:
                found.append(voice.name)
                
    print("
".join(found))

if __name__ == "__main__":
    find_best_swedish_female()
