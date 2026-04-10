# Reddit Wire

Your morning briefing, delivered. Reddit Wire fetches top posts from any set of subreddits, summarizes them into a professional "Apple News Today" style podcast script, and synthesizes high-quality audio 100% locally on your Mac.

Ships configured for AI news out of the box (`r/localLLaMA`, `r/ClaudeAI`, `r/singularity`, `r/ArtificialInteligence`), but it's just a few env vars and a persona file away from being a morning briefing for anything — finance, cooking, gaming, your local city sub, a favorite hobby, whatever you want piped into your ears at 6 AM.

**Requirements:** macOS 13+, Python 3.13, `ffmpeg` (via Homebrew). This project is macOS-only — it depends on `launchd`, `osascript`, Apple Music, and the `say` fallback.

## Features
- **Daily Fetching**: Pulls top posts and comments from any subreddits you choose.
- **Smart Summarization**: Uses Gemini 3 Flash (`gemini-3-flash-preview`) for fast, TTS-optimized script generation.
- **Local TTS (Kokoro v1.0)**: Fast, high-quality audio synthesis (offline, free).
- **Audio Mixing**: Intro stinger + looping background music bed, VO boost and EQ, loudness normalized to -16 LUFS for consistent playback.
- **Apple Music Sync**: Automatically adds the morning briefing to a playlist of your choice (created automatically if it doesn't exist).
- **Set & Forget**: Runs every morning at 6:00 AM via macOS `launchd`.

## Setup
1. **API Keys**: Copy `.env.example` to `.env` and fill in your Reddit credentials and [Google AI Studio API Key](https://aistudio.google.com/).
2. **Dependencies**:
   ```bash
   # Python environment
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt

   # ffmpeg (required for MP3 encoding and audio mixing)
   brew install ffmpeg
   ```
3. **Local Models**: Download `kokoro-v1.0.onnx` and `voices.bin` into the project root. You can use `python3 download_models.py` or grab them from the [Kokoro ONNX releases](https://github.com/thewh1teagle/kokoro-onnx).
4. **Audio Assets**: Place your intro stinger and background music bed in `audio/`:
   - `audio/Reddit_News-stinger.mp3` — plays before the VO
   - `audio/Reddit_News-bed.mp3` — loops under the VO for its full duration
5. **Automation (6 AM Trigger)**:
   Run this command from the project root to set up your specific macOS LaunchAgent:
   ```bash
   cat > ~/Library/LaunchAgents/com.redditwire.daily.plist <<EOF
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>Label</key>
       <string>com.redditwire.daily</string>
       <key>ProgramArguments</key>
       <array>
           <string>/bin/bash</string>
           <string>$(pwd)/run_daily.sh</string>
       </array>
       <key>StartCalendarInterval</key>
       <dict>
           <key>Hour</key>
           <integer>6</integer>
           <key>Minute</key>
           <integer>0</integer>
       </dict>
       <key>StandardErrorPath</key>
       <string>$(pwd)/error.log</string>
       <key>StandardOutPath</key>
       <string>$(pwd)/output.log</string>
       <key>WorkingDirectory</key>
       <string>$(pwd)</string>
   </dict>
   </plist>
   EOF
   launchctl load ~/Library/LaunchAgents/com.redditwire.daily.plist
   ```
   Notes:
   - Your Mac must be awake (or asleep, not shut down) at 6 AM. If asleep, launchd runs it on wake. If powered off, the run is skipped.
   - **Do not place this project inside `~/Documents`, `~/Desktop`, or `~/Downloads`.** Those paths are TCC-protected on modern macOS, and `launchd`-spawned `bash` may be silently denied permission to read scripts in them (exit code `78 EX_CONFIG`), breaking the daily run. A plain `~/Code/reddit-wire` or `~/Projects/reddit-wire` works reliably.

## Customization
- **Subreddits**: Update `REDDIT_SUBREDDITS` in `.env` (comma-separated). This is the main knob for repurposing — point it at any communities you care about (`cooking,recipes,mealprep` for a food briefing; `personalfinance,investing,stocks` for a market rundown; `r/yourcity` for neighborhood news, and so on).
- **Persona & style**: Edit `podcast-persona.md` to rewrite the host's tone, length, and pronunciation rules. The default persona is tuned for AI news — rewrite it to match whatever topic you're briefing on.
- **Prompt overrides**: `summarize_news.py` also contains topic-specific pronunciation rules in its Gemini prompt (RAM, CUDA, localLLaMA, Claude Co-work, etc.). Remove or replace these for non-AI topics.
- **Voice**: Update `KOKORO_VOICE` in `.env`.
- **Music Sync**: Toggle `APPLE_MUSIC_SYNC` in `.env` (`true` or `false`).
- **Playlist Name**: Set `APPLE_MUSIC_PLAYLIST` in `.env` (default: `Reddit Wire`). The playlist is created automatically on first run if it doesn't exist.

## Structure
- `run_daily.sh`: Orchestrator — fetch → summarize → TTS → mix → Apple Music sync.
- `fetch_reddit.py`: Pulls top posts and comments via PRAW.
- `summarize_news.py`: Generates podcast script via Gemini (with data trimming and staleness check).
- `generate_vo.py`: Kokoro v1.0 TTS → WAV → MP3 via ffmpeg.
- `podcast-persona.md`: Prompt persona defining the host's tone, style, and pronunciation rules.
- `audio/`: Intro stinger and background music bed.
- `add_to_music.scpt`: Apple Music integration.
- `output/`: Dated `.mp3` (raw VO + final mix) and `.txt` files.

## License
[MIT](LICENSE)
