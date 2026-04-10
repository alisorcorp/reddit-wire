# Reddit Wire

Your morning briefing, delivered. Reddit Wire fetches top posts from any set of subreddits, summarizes them into a professional "Apple News Today" style podcast script, and synthesizes high-quality audio 100% locally on your Mac.

Ships configured for AI news out of the box (`r/localLLaMA`, `r/ClaudeAI`, `r/singularity`, `r/ArtificialInteligence`), but it's just a few env vars and a persona file away from being a morning briefing for anything — finance, cooking, gaming, your local city sub, a favorite hobby, whatever you want piped into your ears at 6 AM.

**Requirements:** macOS 13+, Python 3.13, `ffmpeg` (via Homebrew), and [Tailscale](https://tailscale.com) if you want the Apple Podcasts delivery path. This project is macOS-only — it depends on `launchd` and the `say` fallback.

## Features
- **Daily Fetching**: Pulls top posts and comments from any subreddits you choose.
- **Smart Summarization**: Uses Gemini 3 Flash (`gemini-3-flash-preview`) for fast, TTS-optimized script generation.
- **Local TTS (Kokoro v1.0)**: Fast, high-quality audio synthesis (offline, free).
- **Audio Mixing**: Intro stinger + looping background music bed, VO boost and EQ, loudness normalized to -16 LUFS for consistent playback.
- **Apple Podcasts Delivery**: Generates a standards-compliant RSS feed served privately over your Tailscale tailnet — subscribe once on Mac, episodes auto-sync to your iPhone / iPad / CarPlay.
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

## Apple Podcasts delivery (via Tailscale Serve)

Reddit Wire produces a standard MP3 you can play anywhere, but the turnkey delivery path is a self-hosted RSS feed that Apple Podcasts subscribes to — native playback speed, resume-where-you-left-off, CarPlay, Apple Watch, auto-download, and cross-device sync via iCloud. The trick is that you need your own feed hosted somewhere your iPhone can reach. [Tailscale](https://tailscale.com) solves that cleanly — no public exposure, free for personal use, HTTPS included.

**One-time setup:**

1. Install Tailscale on your Mac and iPhone, log into the same tailnet.
2. In the Tailscale admin console, enable **Serve** and **HTTPS certificates** for your tailnet.
3. Generate the RSS feed and run the local HTTP server (a tiny custom Python server with HTTP Range support, required for Podcasts scrubbing):
   ```bash
   # Load the HTTP server as a LaunchAgent so it survives reboots
   cp com.redditwire.server.plist ~/Library/LaunchAgents/
   # Edit the plist paths to match your location, then:
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.redditwire.server.plist
   ```
4. Expose it on your tailnet via Tailscale Serve:
   ```bash
   tailscale serve --bg 8080
   ```
   Tailscale will print your feed's HTTPS URL, e.g. `https://your-mac.tailnet-name.ts.net`.
5. Set `PODCAST_FEED_ENABLED="true"` and `PODCAST_BASE_URL="https://your-mac.tailnet-name.ts.net"` in `.env`, plus your title/author/description/artwork overrides.
6. Drop a square cover image at `output/artwork.jpg` (1400×1400 or larger, sRGB).
7. Run `python3 generate_feed.py` once to write `output/feed.xml`. Then in Apple Podcasts on your Mac: **File → Follow a Show by URL** → paste `https://your-mac.tailnet-name.ts.net/feed.xml`. The subscription syncs to your iPhone automatically via iCloud; iOS picks up the feed via Tailscale.

From then on, `run_daily.sh` regenerates the feed after each episode, and Podcasts discovers the new episode on its next refresh.

**Caveats:**
- Your Mac must be awake when Podcasts refreshes on any device (iPhone / iPad / Watch). If the Mac is asleep with the lid closed, enable *Wake for network access* in System Settings → Battery → Options, or keep it plugged in with the lid open.
- The HTTP server binds to `127.0.0.1` only — Tailscale proxies from your tailnet to it, so nothing is exposed on your LAN or the public internet.
- `tailscale serve` config persists across reboots (stored in tailscaled state), so you only run it once.
- For iOS devices to refresh, the **Tailscale iOS app must be installed and the VPN profile active** — once set up, it runs quietly in the background with minimal battery impact.

## Customization
- **Subreddits**: Update `REDDIT_SUBREDDITS` in `.env` (comma-separated). This is the main knob for repurposing — point it at any communities you care about (`cooking,recipes,mealprep` for a food briefing; `personalfinance,investing,stocks` for a market rundown; `r/yourcity` for neighborhood news, and so on).
- **Persona & style**: Edit `podcast-persona.md` to rewrite the host's tone, length, and pronunciation rules. The default persona is tuned for AI news — rewrite it to match whatever topic you're briefing on.
- **Prompt overrides**: `summarize_news.py` also contains topic-specific pronunciation rules in its Gemini prompt (RAM, CUDA, localLLaMA, Claude Co-work, etc.). Remove or replace these for non-AI topics.
- **Voice**: Update `KOKORO_VOICE` in `.env`.
- **Podcast feed metadata**: `PODCAST_TITLE`, `PODCAST_DESCRIPTION`, `PODCAST_AUTHOR`, `PODCAST_LANGUAGE`, `PODCAST_CATEGORY`, and `PODCAST_ARTWORK_URL` in `.env` control how your show appears in Apple Podcasts.

## Structure
- `run_daily.sh`: Orchestrator — fetch → summarize → TTS → mix → feed regen.
- `fetch_reddit.py`: Pulls top posts and comments via PRAW.
- `summarize_news.py`: Generates podcast script via Gemini (with data trimming and staleness check).
- `generate_vo.py`: Kokoro v1.0 TTS → WAV → MP3 via ffmpeg.
- `generate_feed.py`: Scans `output/` and emits an iTunes-compatible RSS 2.0 feed (`feed.xml`) for Apple Podcasts.
- `serve.py`: Tiny HTTP file server with Range request support (required by Podcasts). Runs as a LaunchAgent on `127.0.0.1:8080` and is proxied by Tailscale Serve.
- `podcast-persona.md`: Prompt persona defining the host's tone, style, and pronunciation rules.
- `audio/`: Intro stinger and background music bed.
- `output/`: Dated `.mp3` (raw VO + final mix), `.txt` scripts, `feed.xml`, and `artwork.jpg`.

## License
[MIT](LICENSE)
