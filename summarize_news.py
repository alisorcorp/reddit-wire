import os
from datetime import datetime
from google import genai
from dotenv import load_dotenv

def summarize():
    # Load environment variables
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    
    # Calculate today's date for the prompt
    today_str = datetime.now().strftime("%A, %B %d, %Y")

    if not api_key:
        print("Error: GOOGLE_API_KEY not found in .env. Get one at https://aistudio.google.com/")
        return

    # Initialize Gemini Client for Google AI Studio
    client = genai.Client(api_key=api_key)

    # Read data
    try:
        with open('reddit_today.json', 'r') as f:
            reddit_data = f.read()
        with open('podcast-persona.md', 'r') as f:
            persona = f.read()
    except FileNotFoundError as e:
        print(f"Error: Missing input file - {e}")
        return

    prompt = f"""
    TODAY'S DATE: {today_str}

    Read the following Reddit data and podcast persona. 
    Write a conversational 1200-1500 word podcast script in the style of Apple News Today. 
    Output ONLY raw script text. 

    IMPORTANT: 
    - This script is for a Text-to-Speech (TTS) engine. It will read EVERYTHING literally.
    - NEVER put pronunciation guides in parentheses (e.g., NO "LLM (L-L-M)").
    - If a term or username is hard to pronounce, use ONLY the phonetic version that sounds natural when spoken.
    - DO NOT include both the original spelling and the pronunciation. Choose one.
    - Use TODAY'S DATE ({today_str}) in your opening line. Do not use the example date from the persona.

    START IMMEDIATELY with the host's first line. 
    NO 'I will read...' statements.

    PERSONA:
    {persona}

    REDDIT DATA:
    {reddit_data}
    """

    print(f"Generating podcast script via Gemini API (Model: {model_name})...")
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        script_text = response.text

        # Basic cleaning
        lines = script_text.split('\n')
        cleaned_lines = [line for line in lines if not any(line.startswith(p) for p in ["I will read", "I'll read", "Reading"])]
        final_script = '\n'.join(cleaned_lines).strip()

        with open('podcast_script.txt', 'w') as f:
            f.write(final_script)
        
        print("Successfully generated podcast_script.txt")
    except Exception as e:
        print(f"Error during generation: {e}")

if __name__ == "__main__":
    summarize()
