import os
import json
from datetime import datetime
from pathlib import Path
from google import genai
from dotenv import load_dotenv

MAX_POSTS = 30
MAX_COMMENT_CHARS = 300
MAX_CONTENT_CHARS = 1000
MAX_COMMENTS_PER_POST = 5
# How many recent closings to load as "don't repeat these" context.
# Too few = weak variety pressure; too many = wasted tokens.
RECENT_CLOSINGS_WINDOW = 7

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


def load_recent_closings(output_dir: Path, limit: int) -> list[str]:
    """Return the most recent N episode closings, newest first.

    Used to give Gemini explicit 'don't repeat any of these' context so the
    daily closing genuinely varies instead of relying on Gemini's non-existent
    memory of yesterday's output.
    """
    if not output_dir.exists():
        return []
    closing_files = sorted(
        output_dir.glob("Reddit *.closing.txt"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    closings: list[str] = []
    for p in closing_files[:limit]:
        try:
            text = p.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if text:
            closings.append(text)
    return closings

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

    def get_time_of_day():
        """Return (hour_24, label) for the current local time.

        Labels are used to steer the intro greeting — Gemini picks the
        specific wording ('Good morning', 'Good evening', etc.) based on
        the label, so manual runs at off-hours don't open with a stale
        'Good morning' at 10pm.
        """
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return hour, "morning"
        if 12 <= hour < 17:
            return hour, "afternoon"
        if 17 <= hour < 21:
            return hour, "evening"
        return hour, "late night"

    today_str = get_date_with_ordinal()
    current_hour, time_of_day = get_time_of_day()

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

    # Load the last N closings so Gemini can actually vary the sign-off
    # instead of being asked to "not repeat yesterday" without any memory of it.
    recent_closings = load_recent_closings(Path("output"), RECENT_CLOSINGS_WINDOW)
    if recent_closings:
        recent_closings_block = (
            "\n\n    RECENT CLOSINGS YOU'VE ALREADY USED (each one is from a previous episode — "
            "do NOT repeat any of their ideas, framings, callbacks, metaphors, structures, or rhetorical moves; "
            "the new closing must feel genuinely different from all of them):\n\n"
            + "\n\n---\n\n".join(recent_closings)
            + "\n\n---\n"
        )
    else:
        recent_closings_block = ""

    prompt = f"""
    TODAY'S DATE: {today_str}
    CURRENT LOCAL TIME: {current_hour:02d}:00 ({time_of_day})

    Read the following Reddit data and podcast persona.
    Write a conversational 1200-1500 word podcast script in the style of Apple News Today,
    followed by a short episode description for the podcast app and a clean copy of the
    closing for archival.

    OUTPUT FORMAT (exactly):
    1. The podcast script (1200-1500 words, TTS-optimized per rules below). The script must
       end with the creative closing described in the persona.
    2. On its own line, exactly this marker: ~~~EPISODE_DESCRIPTION~~~
    3. A 2-3 sentence episode description (plain prose, max ~400 characters) highlighting
       the top stories covered. The description is plain text for a podcast app UI — it is
       NOT read by TTS, so it does not need phonetic spellings or contractions.
    4. On its own line, exactly this marker: ~~~EPISODE_CLOSING~~~
    5. A verbatim copy of the closing passage from the end of the script (just the closing,
       nothing before it). This archival copy is saved so future episodes can avoid repeating it.{recent_closings_block}

    SCRIPT RULES (apply to part 1 only):
    - This script is for a Text-to-Speech (TTS) engine. It will read EVERYTHING literally.
    - NEVER put pronunciation guides in parentheses (e.g., NO "LLM (L-L-M)").
    - If a term or username is hard to pronounce, use ONLY the phonetic version that sounds natural when spoken.
    - DO NOT include both the original spelling and the pronunciation. Choose one.
    - Use TODAY'S DATE ({today_str}) in your opening line. Do not use the example date from the persona.
    - Open with a warm, natural greeting that matches the CURRENT LOCAL TIME ({time_of_day}). Do NOT default to a morning greeting if it is not morning — pick wording that genuinely fits the current time of day. If it is late night, acknowledge the unusual hour with a greeting that sounds right for that time, not a recycled morning template.
    - Write "AI" naturally. Do not spell it out or use phonetic alternatives.
    - Always write "localLLaMA" as "Local-Lama".
    - For any model name containing a decimal, spell the decimal as "point" (e.g., "3.5" becomes "three-point-five", "4.1" becomes "four-point-one", "2.0" becomes "two-point-oh").
    - ALWAYS use contractions in place of formal phrasing (e.g., "it's" not "it is", "don't" not "do not", "we're" not "we are", "that's" not "that is"). The script should sound natural and spoken.
    - Always write "RAM" as "ram" (lowercase, pronounced as a word, not spelled out).
    - Always write "CUDA" as "cooda" (phonetic spelling for TTS).
    - Always write "Claude Cowork" as "Claude Co-work" (hyphenated, so TTS pronounces it "co-work", not "cow-ork").

    DESCRIPTION RULES (apply to part 3 only):
    - Normal written English. Proper capitalization of model names, terms, and companies.
    - No phonetic spellings, no "point" for decimals, no special TTS formatting.
    - Focus on the top 1-2 stories. Don't quote the script verbatim.
    - Keep it under ~400 characters.

    START IMMEDIATELY with the host's first line of the script.
    NO 'I will read...' statements.

    PERSONA:
    {persona}

    REDDIT DATA:
    {reddit_data}
    """

    print(f"Generating podcast script via Gemini API (Model: {model_name})...")
    if recent_closings:
        print(f"  (providing {len(recent_closings)} recent closings as 'don't repeat' context)")
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        raw_text = response.text

        # Parse the three-part response: script, description, closing.
        desc_marker = "~~~EPISODE_DESCRIPTION~~~"
        closing_marker = "~~~EPISODE_CLOSING~~~"

        if desc_marker in raw_text:
            script_part, rest = raw_text.split(desc_marker, 1)
        else:
            print("Warning: description marker not found. Falling back to script-only.")
            script_part = raw_text
            rest = ""

        if closing_marker in rest:
            description_part, closing_part = rest.split(closing_marker, 1)
        else:
            description_part = rest
            closing_part = ""

        lines = script_part.split('\n')
        cleaned_lines = [
            line for line in lines
            if not any(line.strip().startswith(p) for p in ["I will read", "I'll read", "Reading"])
        ]
        final_script = '\n'.join(cleaned_lines).strip()
        final_description = description_part.strip()
        final_closing = closing_part.strip()

        with open('podcast_script.txt', 'w') as f:
            f.write(final_script)
        print("Successfully generated podcast_script.txt")

        if final_description:
            with open('podcast_description.txt', 'w') as f:
                f.write(final_description)
            print("Successfully generated podcast_description.txt")

        if final_closing:
            with open('podcast_closing.txt', 'w') as f:
                f.write(final_closing)
            print("Successfully generated podcast_closing.txt")
    except Exception as e:
        print(f"Error during generation: {e}")

if __name__ == "__main__":
    summarize()
