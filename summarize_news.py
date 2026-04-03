import os
import json
from datetime import datetime
from google import genai
from dotenv import load_dotenv

MAX_POSTS = 30
MAX_COMMENT_CHARS = 300
MAX_CONTENT_CHARS = 1000
MAX_COMMENTS_PER_POST = 5

def trim_reddit_data(raw_json):
    """Trim reddit data to stay within reasonable token limits."""
    posts = json.loads(raw_json)
    trimmed = []
    for post in posts[:MAX_POSTS]:
        trimmed.append({
            "subreddit": post["subreddit"],
            "title": post["title"],
            "author": post["author"],
            "score": post["score"],
            "content": post.get("content", "")[:MAX_CONTENT_CHARS],
            "comments": [
                {"body": c["body"][:MAX_COMMENT_CHARS], "score": c["score"]}
                for c in post.get("comments", [])[:MAX_COMMENTS_PER_POST]
            ],
        })
    return json.dumps(trimmed, indent=2)

def check_data_freshness(filepath):
    """Warn if the data file wasn't modified today."""
    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
    if mtime.date() != datetime.now().date():
        print(f"Warning: {filepath} is from {mtime.strftime('%Y-%m-%d')}, not today. Data may be stale.")

def summarize():
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")

    def get_date_with_ordinal():
        d = datetime.now()
        day = d.day
        if 11 <= day <= 13:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
        return d.strftime(f"%A, %B {day}{suffix}, %Y")

    today_str = get_date_with_ordinal()

    if not api_key:
        print("Error: GOOGLE_API_KEY not found in .env. Get one at https://aistudio.google.com/")
        return

    client = genai.Client(api_key=api_key)

    try:
        with open('reddit_today.json', 'r') as f:
            raw_json = f.read()
        with open('podcast-persona.md', 'r') as f:
            persona = f.read()
    except FileNotFoundError as e:
        print(f"Error: Missing input file - {e}")
        return

    check_data_freshness('reddit_today.json')
    reddit_data = trim_reddit_data(raw_json)

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
    - Write "AI" naturally. Do not spell it out or use phonetic alternatives.

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

        lines = script_text.split('\n')
        cleaned_lines = [
            line for line in lines
            if not any(line.strip().startswith(p) for p in ["I will read", "I'll read", "Reading"])
        ]
        final_script = '\n'.join(cleaned_lines).strip()

        with open('podcast_script.txt', 'w') as f:
            f.write(final_script)

        print("Successfully generated podcast_script.txt")
    except Exception as e:
        print(f"Error during generation: {e}")

if __name__ == "__main__":
    summarize()
