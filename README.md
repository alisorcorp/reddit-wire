# Reddit Wire

Reddit Wire fetches top posts from any set of subreddits, summarizes them into a professional "Apple News Today" style podcast script, and synthesizes high-quality audio 100% locally on your Mac.

Ships configured for AI news out of the box (`r/localLLaMA`, `r/ClaudeAI`, `r/singularity`, `r/ArtificialInteligence`), but it's just a few env vars and a persona file away from being a morning briefing for anything — finance, cooking, gaming, your local city sub, a favorite hobby, whatever you want piped into your ears at 6 AM.

**Requirements:** macOS 13+ with Apple Silicon (M-series), Python 3.13, `ffmpeg` (via Homebrew), a built [`llama.cpp`](https://github.com/ggml-org/llama.cpp) with Metal support, a local GGUF model (default: Gemma 4 26B-A4B-it Q6_K_XL), and [Tailscale](https://tailscale.com) if you want the Apple Podcasts delivery path. This project is macOS-only — it depends on `launchd` and the `say` fallback. Gemini API remains available as an optional fallback backend if you prefer cloud inference.

## Features
- **Daily Fetching**: Pulls top posts and comments from any subreddits you choose.
- **Local LLM Script Generation (default)**: Gemma 4 26B-A4B-it running on `llama.cpp` with Metal + thinking mode — ~75-100 seconds per episode on Apple Silicon, fully offline, no API bills. Swap to Gemini API with a single env var flip if you prefer.
- **Local TTS (Kokoro v1.0)**: Fast, high-quality audio synthesis (offline, free).
- **Audio Mixing**: Intro stinger + looping background music bed, VO boost and EQ, loudness normalized to -16 LUFS for consistent playback.
- **Apple Podcasts Delivery**: Generates a standards-compliant RSS feed served privately over your Tailscale tailnet — subscribe once on Mac, episodes auto-sync to your iPhone / iPad / CarPlay.
- **Set & Forget**: Runs every morning at 6:00 AM via macOS `launchd`.

## Setup
1. **API Keys**: Copy `.env.example` to `.env` and fill in your Reddit credentials. A Google AI Studio key is only needed if you want to switch to `LLM_BACKEND=gemini` — the default is 100% local.
2. **Dependencies**:
   ```bash
   # Python environment
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt

   # ffmpeg (required for MP3 encoding and audio mixing)
   brew install ffmpeg
   ```
3. **llama.cpp (local LLM backend, default)**: Build from source with Metal support:
   ```bash
   git clone https://github.com/ggml-org/llama.cpp ~/llama.cpp
   cd ~/llama.cpp
   cmake -B build -DCMAKE_BUILD_TYPE=Release
   cmake --build build -j
   ```
   Point `LLAMA_SERVER_BIN` in `.env` at the resulting `build/bin/llama-server` binary. `run_daily.sh` starts and stops the server ephemerally around each run, so you don't need a separate LaunchAgent for it.
4. **LLM model weights**: Download a GGUF model. The default is Gemma 4 26B-A4B-it at Q6_K_XL quant (~22 GB) from [unsloth/gemma-4-26B-A4B-it-GGUF](https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF). Set `LLM_MODEL_PATH` in `.env` to the downloaded `.gguf` file. Any chat-tuned GGUF that `llama.cpp` supports will work — Gemma 4 26B-A4B is the default because its instruction-following is strong enough to obey the persona's TTS rules (decimal spelling, literal replacements like `localLLaMA` → `Local-Lama`) on the first pass without post-processing. Smaller models (Gemma 4 E4B, Qwen 3 class) can be used but will need either a regex post-processor or manual cleanup.
5. **Kokoro TTS models**: Download `kokoro-v1.0.onnx` and `voices.bin` into the project root. Use `python3 download_models.py` or grab them from the [Kokoro ONNX releases](https://github.com/thewh1teagle/kokoro-onnx).
6. **Audio Assets**: Place your intro stinger and background music bed in `audio/`:
   - `audio/Reddit_News-stinger.mp3` — plays before the VO
   - `audio/Reddit_News-bed.mp3` — loops under the VO for its full duration
7. **Automation (6 AM Trigger)**:
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

## LLM backend (local by default, Gemini as fallback)

Reddit Wire has one knob that controls how the script is generated: `LLM_BACKEND` in `.env`.

```bash
# Default — free, offline, ~75-100s per episode on Apple Silicon
LLM_BACKEND="local"

# Cloud fallback — requires GOOGLE_API_KEY, returns in ~10-15s
LLM_BACKEND="gemini"
```

**Local backend** (`LLM_BACKEND=local`) runs `llama.cpp`'s `llama-server` with your chosen GGUF model. `run_daily.sh` handles the full lifecycle: on each run it checks whether a `llama-server` is already reachable at `LLM_BASE_URL`; if not, it starts one, waits for `/health`, runs summarization, and stops the server in the EXIT trap. If you're running an always-on `llama-server` yourself (manual session, LM Studio, or a separate LaunchAgent), the pipeline detects it and reuses it without killing it on exit.

Relevant `.env` keys for the local backend:

| Key                | Default                            | What it controls                                                 |
| ------------------ | ---------------------------------- | ---------------------------------------------------------------- |
| `LLM_BACKEND`      | `local`                            | `local` or `gemini`                                              |
| `LLM_BASE_URL`     | `http://127.0.0.1:8081`            | OpenAI-compatible endpoint llama-server listens on               |
| `LLAMA_SERVER_BIN` | —                                  | Absolute path to your `llama-server` binary                      |
| `LLM_MODEL_PATH`   | —                                  | Absolute path to the `.gguf` weights                             |
| `LLM_LOCAL_MODEL`  | `gemma-4-26b-a4b-it`               | Cosmetic label used in log output                                |
| `LLM_CONTEXT`      | `32768`                            | KV cache size in tokens                                          |
| `LLM_REASONING`    | `on`                               | `on` to enable Gemma 4's native thinking; `off` to save ~30s    |

**Gemini backend** (`LLM_BACKEND=gemini`) uses the existing `google-genai` SDK against Google AI Studio. Requires `GOOGLE_API_KEY` and `GEMINI_MODEL` in `.env`. The `google-genai` dependency is imported lazily inside `summarize_news.py`, so a pure-local setup doesn't need the package installed at all.

The pipeline is identical downstream of script generation — the `podcast_script.txt`, `podcast_description.txt`, and `podcast_closing.txt` files that TTS and RSS generation consume look the same regardless of backend.

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
- **Prompt overrides**: `summarize_news.py` also contains topic-specific pronunciation rules in its prompt (RAM, CUDA, localLLaMA, Claude Co-work, AI vs A-I, etc.). These apply equally to both backends. Remove or replace them for non-AI topics.
- **LLM backend**: Flip `LLM_BACKEND` between `local` (default, Gemma 4 26B-A4B via llama.cpp) and `gemini` (Google AI Studio). See the [LLM backend](#llm-backend-local-by-default-gemini-as-fallback) section above.
- **Voice**: Update `KOKORO_VOICE` in `.env`.
- **Podcast feed metadata**: `PODCAST_TITLE`, `PODCAST_DESCRIPTION`, `PODCAST_AUTHOR`, `PODCAST_LANGUAGE`, `PODCAST_CATEGORY`, and `PODCAST_ARTWORK_URL` in `.env` control how your show appears in Apple Podcasts.
- **Closing variety window**: Each episode's script ends with a creative closing thought generated by the active LLM. `summarize_news.py` persists every closing to its own `*.closing.txt` file and feeds the most recent 7 back into the next day's prompt as explicit "do not repeat" context, so closings actually vary across episodes instead of drifting toward a house formula. Adjust `RECENT_CLOSINGS_WINDOW` in `summarize_news.py` to widen or narrow the memory window.
- **Manual runs and multiple cron entries**: You can trigger `./run_daily.sh` at any hour, or add additional `launchd`/`cron` schedules for afternoon or evening recaps. The pipeline auto-detects the time of day and both (a) tells the LLM to open with a greeting appropriate to the hour (not a stale "Good morning" at 10 PM) and (b) adds a time-of-day suffix to the filename so episodes at different times on the same calendar day don't collide. Buckets: `5-11` morning (unadorned filename), `12-16` Afternoon, `17-20` Evening, `21-4` Late Night. Episodes render in Apple Podcasts as `Reddit Wire - <date>` or `Reddit Wire - <date> (Afternoon|Evening|Late Night)`, sorted chronologically within each day.

## Structure
- `run_daily.sh`: Orchestrator — start llama-server (if local) → fetch → summarize → TTS → mix → feed regen → stop llama-server.
- `fetch_reddit.py`: Pulls top posts and comments via PRAW.
- `summarize_news.py`: Generates script + app description + archived closing in a single LLM call (local `llama-server` by default, Gemini API when `LLM_BACKEND=gemini`), with the last 7 closings fed back as "don't repeat" context. Parser normalizes common model-introduced marker variants (`***EPISODE_DESCRIPTION***` → `~~~EPISODE_DESCRIPTION~~~`) so both backends produce a clean 3-part split regardless of markdown-rewriting habits.
- `generate_vo.py`: Kokoro v1.0 TTS → WAV → MP3 via ffmpeg.
- `generate_feed.py`: Scans `output/` and emits an iTunes-compatible RSS 2.0 feed (`feed.xml`) for Apple Podcasts. Prefers per-episode `.description.txt` files; falls back to a truncated script intro for legacy episodes.
- `serve.py`: Tiny HTTP file server with Range request support (required by Podcasts). Runs as a LaunchAgent on `127.0.0.1:8080` and is proxied by Tailscale Serve.
- `podcast-persona.md`: Prompt persona defining the host's tone, style, pronunciation rules, and closing guidance.
- `audio/`: Intro stinger and background music bed.
- `output/`: Per-episode files — `.mp3` (raw VO), ` - Final.mp3` (mixed), `.txt` (full script), `.description.txt` (Podcasts app blurb), `.closing.txt` (closing paragraph, used as history for future runs) — plus `feed.xml` and `artwork.jpg`.

## License
[MIT](LICENSE)
