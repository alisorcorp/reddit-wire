# Reddit AI News Pipeline 🎙️

An automated morning briefing that fetches top AI news from Reddit, summarizes it into a professional "Apple News Today" style podcast script, and synthesizes high-quality audio 100% locally on your Mac.

## 🚀 Features
- **Daily Fetching**: Pulls top posts and comments from customizable subreddits.
- **Smart Summarization**: Uses Gemini 3 Flash (`gemini-3-flash-preview`) for fast, TTS-optimized script generation.
- **Local TTS (Kokoro)**: Blazing fast high-quality audio synthesis (offline, free).
- **Apple Music Sync**: Automatically adds the morning briefing to your "Reddit AI News" playlist.
- **Set & Forget**: Runs every morning at 6:00 AM EST via macOS `launchd`.

## 🛠️ Setup
1. **API Keys**: Copy `.env.example` to `.env` and fill in your Reddit credentials and [Google AI Studio API Key](https://aistudio.google.com/).
2. **Environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Local Models**: Run `python3 download_models.py` to pull the latest Kokoro models.
4. **Automation (6 AM Trigger)**:
   Run this command from the project root to set up your specific macOS LaunchAgent:
   ```bash
   cat > ~/Library/LaunchAgents/com.redditnews.daily.plist <<EOF
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>Label</key>
       <string>com.redditnews.daily</string>
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
   launchctl load ~/Library/LaunchAgents/com.redditnews.daily.plist
   ```

## 🎙️ Customization
- **Subreddits**: Update `REDDIT_SUBREDDITS` in `.env` (comma-separated).
- **Voice**: Update `KOKORO_VOICE` in `.env`.
- **Music Sync**: Toggle `APPLE_MUSIC_SYNC` in `.env` (`true` or `false`).
- **Style**: Edit `podcast-persona.md` to change the host's tone or length.

## 📂 Structure
- `run_daily.sh`: Main portable runner script.
- `fetch_reddit.py`: Data gathering.
- `summarize_news.py`: Script generation via Gemini.
- `generate_vo.py`: Local audio synthesis.
- `add_to_music.scpt`: Apple Music integration.
- `output/`: Dated `.mp3` and `.txt` files.

---
*Built with ❤️ by Gemini CLI and an M4 Max Mac.*
