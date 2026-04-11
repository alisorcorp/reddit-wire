#!/bin/bash

# Automatically switch to the directory where this script is located
cd "$(dirname "$0")"

# Ensure ffmpeg and other local tools are on PATH (launchd uses a minimal PATH)
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# --- Watchdog: hard-kill this script (and its children) after 25 minutes.
# Prevents a hung Kokoro/say/ffmpeg from blocking tomorrow's launchd run.
SCRIPT_PID=$$
( sleep 1500 && echo "[$(date '+%F %T')] WATCHDOG: run_daily.sh exceeded 25m, killing pgid $SCRIPT_PID" >&2 && kill -TERM -$SCRIPT_PID 2>/dev/null; sleep 5; kill -KILL -$SCRIPT_PID 2>/dev/null ) &
WATCHDOG_PID=$!
trap 'kill $WATCHDOG_PID 2>/dev/null' EXIT

# Portable per-command timeout (macOS has no `timeout`). Usage: run_with_timeout <seconds> <cmd...>
run_with_timeout() {
    local secs=$1; shift
    perl -e 'alarm shift; exec @ARGV' "$secs" "$@"
}

echo "===== [$(date '+%F %T')] run_daily.sh start (pid $$) ====="
set -o pipefail

source .venv/bin/activate

# Robustly load .env variables
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

# 1. Fetch Reddit Data
run_with_timeout 180 python3 fetch_reddit.py

# 2. Generate Podcast Script
run_with_timeout 180 python3 summarize_news.py

# Date format: "March 31, 2026"
DATE_STR=$(date "+%B %d, %Y")
FILENAME="Reddit Wire - ${DATE_STR}"
cp podcast_script.txt "output/${FILENAME}.txt"
if [ -f podcast_description.txt ]; then
    cp podcast_description.txt "output/${FILENAME}.description.txt"
fi

# 3. Generate Audio (Local Kokoro)
if run_with_timeout 900 python3 generate_vo.py "${FILENAME}"; then
    echo "VO generated successfully."

    # 4. Mix with stinger and music bed
    VO_MP3="output/${FILENAME}.mp3"
    STINGER="audio/Reddit_News-stinger.mp3"
    BED="audio/Reddit_News-bed.mp3"
    FINAL_MP3="output/${FILENAME} - Final.mp3"

    if [ -f "$STINGER" ] && [ -f "$BED" ]; then
        VO_DURATION=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$VO_MP3")
        echo "Mixing audio (stinger + VO with music bed)..."
        run_with_timeout 600 ffmpeg -y \
          -i "$STINGER" \
          -i "$VO_MP3" \
          -stream_loop -1 -i "$BED" \
          -filter_complex "
            [1:a]volume=1.4,equalizer=f=120:t=q:w=1.2:g=3[vo_boosted];
            [2:a]atrim=0:${VO_DURATION},asetpts=PTS-STARTPTS[bed_trimmed];
            [vo_boosted][bed_trimmed]amix=inputs=2:duration=first:dropout_transition=3[vo_mix];
            [0:a][vo_mix]concat=n=2:v=0:a=1[premix];
            [premix]loudnorm=I=-16:TP=-1:LRA=11[out]
          " \
          -map "[out]" -b:a 192k "$FINAL_MP3"
        if [ $? -eq 0 ] && [ -f "$FINAL_MP3" ]; then
            echo "Final mix saved: $FINAL_MP3"
        else
            echo "Error: ffmpeg mix failed. Using unmixed VO instead." >&2
            FINAL_MP3="$VO_MP3"
        fi
    else
        echo "Warning: Stinger or bed not found, skipping mix."
        FINAL_MP3="$VO_MP3"
    fi

    echo "Audio briefing generated successfully: $(date)"

    # 5. Regenerate podcast RSS feed (served via Tailscale + serve.py for Apple Podcasts)
    if [ "${PODCAST_FEED_ENABLED:-false}" = "true" ]; then
        echo "Regenerating podcast feed..."
        if run_with_timeout 60 python3 generate_feed.py; then
            echo "Feed updated."
        else
            echo "Error: generate_feed.py failed or timed out." >&2
        fi
    fi
else
    echo "[$(date '+%F %T')] Local Kokoro failed, using macOS 'say' as fallback (capped at 5m)..."
    run_with_timeout 300 say -f podcast_script.txt -o "output/${FILENAME}.aiff" \
        && echo "say fallback wrote output/${FILENAME}.aiff" \
        || echo "say fallback failed or timed out — no audio produced today"
fi

echo "===== [$(date '+%F %T')] run_daily.sh done (pid $$) ====="
