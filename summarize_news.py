import os
import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# `google.genai` is imported lazily inside summarize() only when
# LLM_BACKEND != "local", so users running 100% local inference don't need
# the google-genai package installed at all.

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


def generate_via_local_llm(prompt: str) -> str:
    """POST the prompt to a local llama-server OpenAI-compatible endpoint.

    This is the default backend (LLM_BACKEND=local). Talks to a llama.cpp
    `llama-server` — expected model is Gemma 4 26B-A4B-it (MoE, 4B active)
    with reasoning enabled. Gemini remains available via LLM_BACKEND=gemini.
    """
    base_url = os.getenv("LLM_BASE_URL", "http://127.0.0.1:8081").rstrip("/")
    model = os.getenv("LLM_LOCAL_MODEL", "local-model")
    # max_tokens budget = reasoning/thinking trace + script (~2k tokens) +
    # description + closing + markers. Reasoning traces on Gemma 4 are
    # unpredictable (seen 1k-2.5k), so we give 8192 to leave comfortable
    # headroom — truncating mid-script is a silent failure mode that
    # breaks the downstream marker parser.
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "top_p": 0.9,
        "max_tokens": 8192,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload["choices"][0]["message"]["content"]


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

    backend = os.getenv("LLM_BACKEND", "local").lower()
    client = None
    if backend != "local":
        # Lazy import so a 100%-local setup doesn't require google-genai.
        try:
            from google import genai
        except ImportError:
            print(
                "Error: LLM_BACKEND=gemini but the google-genai package is not installed.\n"
                "  Install it with:  pip install google-genai\n"
                "  Or set LLM_BACKEND=local to use llama-server."
            )
            return
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
    - Write "AI" as "AI" — a single two-letter word. NEVER write it as "A-I", "A.I.", "A I", or any hyphenated/spaced/punctuated variant. The TTS engine reads "AI" as "ay-eye" correctly on its own; any hyphen or punctuation between the letters makes it read as letter-by-letter spelling ("A dash I"), which sounds wrong. Same rule applies to "CLI" — write it as "CLI", not "C-L-I" — or replace it with "command-line tool" if the context allows.
    - Always write "localLLaMA" as "Local-Lama".
    - For any model name containing a decimal, spell the decimal as "point" (e.g., "3.5" becomes "three-point-five", "4.1" becomes "four-point-one", "2.0" becomes "two-point-oh").
    - ALWAYS use contractions in place of formal phrasing (e.g., "it's" not "it is", "don't" not "do not", "we're" not "we are", "that's" not "that is"). The script should sound natural and spoken.
    - Always write "RAM" as "ram" (lowercase, pronounced as a word, not spelled out).
    - Always write "CUDA" as "cooda" (phonetic spelling for TTS).
    - Always write "Claude Cowork" as "Claude Co-work" (hyphenated, so TTS pronounces it "co-work", not "cow-ork").
    - NEVER write "AM", "PM", "a.m.", or "p.m." anywhere in the script. The TTS engine reads them letter-by-letter with pauses ("P. M.") which sounds robotic. Use natural spoken phrasing instead: "in the morning", "in the afternoon", "in the evening", "at night", "tonight", "this morning", "o'clock at night", etc. For example, ten at night should be written as "ten o'clock at night" or "ten in the evening", not "10 PM".

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

    if backend == "local":
        local_model_label = os.getenv("LLM_LOCAL_MODEL", "llama-server")
        print(f"Generating podcast script via local llama-server ({local_model_label})...")
    else:
        print(f"Generating podcast script via Gemini API (Model: {model_name})...")
    if recent_closings:
        print(f"  (providing {len(recent_closings)} recent closings as 'don't repeat' context)")
    try:
        if backend == "local":
            raw_text = generate_via_local_llm(prompt)
        else:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            raw_text = response.text

        # Parse the three-part response: script, description, closing.
        desc_marker = "~~~EPISODE_DESCRIPTION~~~"
        closing_marker = "~~~EPISODE_CLOSING~~~"

        # Some models (notably Gemma) rewrite the tilde markers as markdown
        # emphasis (`***EPISODE_DESCRIPTION***`, `**EPISODE_CLOSING**`, etc.).
        # Normalize any 2-4 `*` or `~` delimiter variant back to the canonical
        # tilde form so the split below works regardless of backend quirks.
        raw_text = re.sub(r"[*~]{2,4}\s*EPISODE_DESCRIPTION\s*[*~]{2,4}", desc_marker, raw_text)
        raw_text = re.sub(r"[*~]{2,4}\s*EPISODE_CLOSING\s*[*~]{2,4}", closing_marker, raw_text)

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
