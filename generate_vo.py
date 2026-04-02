import os
import wave
import sys
import numpy as np
import soundfile as sf
from datetime import datetime
from kokoro_onnx import Kokoro
from dotenv import load_dotenv

load_dotenv()

def generate_local_audio(text, output_path, voice_name):
    print(f"Initializing Kokoro TTS engine (Voice: {voice_name})...")
    # Initialize Kokoro with local model files
    kokoro = Kokoro("kokoro-v0_19.onnx", "voices.bin")
    
    print(f"Synthesizing audio (local)...")
    samples, sample_rate = kokoro.create(
        text, 
        voice=voice_name, 
        speed=1.0, 
        lang="en-us"
    )
    
    # Save the synthesized audio
    sf.write(output_path, samples, sample_rate)
    print(f"Audio saved locally to {output_path}")

if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)
    
    # Get filename from CLI argument if provided
    if len(sys.argv) > 1:
        base_name = sys.argv[1]
    else:
        # Fallback to default date format if no arg provided
        base_name = f"Reddit Daily - {datetime.now().strftime('%B %d, %Y')}"
    
    output_file = f"output/{base_name}.mp3"
    
    # Get voice from .env, default to af_sky
    current_voice = os.getenv("KOKORO_VOICE", "af_sky")
    
    script_path = "podcast_script.txt"
    if os.path.exists(script_path):
        with open(script_path, "r") as f:
            full_text = f.read()
            
        generate_local_audio(full_text, output_file, current_voice)
        print(f"Local synthesis complete! Saved to {output_file}")
    else:
        print("No script found.")
