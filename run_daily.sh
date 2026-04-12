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

# --- llama-server lifecycle state (populated later if LLM_BACKEND=local).
# Declared up front so the EXIT trap can read them unconditionally.
LLAMA_SERVER_PID=""
LLAMA_SERVER_STARTED_BY_US=""

on_exit() {
    [ -n "$WATCHDOG_PID" ] && kill "$WATCHDOG_PID" 2>/dev/null
    if [ -n "$LLAMA_SERVER_STARTED_BY_US" ] && [ -n "$LLAMA_SERVER_PID" ]; then
        echo "[$(date '+%F %T')] Stopping llama-server (pid $LLAMA_SERVER_PID)"
        kill -TERM "$LLAMA_SERVER_PID" 2>/dev/null
    fi
}
trap on_exit EXIT

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

# --- 0. Start llama-server if local backend selected (default).
# If a llama-server is already reachable at LLM_BASE_URL we reuse it without
# killing it on exit (e.g. an always-on manual session). Otherwise we spawn
# one, wait for /health, and tear it down in the EXIT trap.
if [ "${LLM_BACKEND:-local}" = "local" ]; then
    LLM_URL="${LLM_BASE_URL:-http://127.0.0.1:8081}"
    LLM_PORT=$(echo "$LLM_URL" | sed -E 's|.*:([0-9]+)(/.*)?$|\1|')

    if curl -sS -m 2 -o /dev/null "${LLM_URL}/health" 2>/dev/null; then
        echo "[$(date '+%F %T')] llama-server already reachable at ${LLM_URL}, reusing"
    else
        if [ -z "${LLAMA_SERVER_BIN:-}" ] || [ ! -x "$LLAMA_SERVER_BIN" ]; then
            echo "ERROR: LLAMA_SERVER_BIN not set or not executable: '${LLAMA_SERVER_BIN:-<unset>}'" >&2
            echo "  Set it in .env to the path of your llama.cpp llama-server binary." >&2
            exit 1
        fi
        if [ -z "${LLM_MODEL_PATH:-}" ] || [ ! -f "$LLM_MODEL_PATH" ]; then
            echo "ERROR: LLM_MODEL_PATH not set or missing: '${LLM_MODEL_PATH:-<unset>}'" >&2
            exit 1
        fi

        REASONING_FLAG=""
        if [ "${LLM_REASONING:-on}" = "on" ]; then
            REASONING_FLAG="--reasoning on"
        fi

        echo "[$(date '+%F %T')] Starting llama-server: $(basename "$LLM_MODEL_PATH") (ctx=${LLM_CONTEXT:-32768}, port=${LLM_PORT})"
        "$LLAMA_SERVER_BIN" \
            -m "$LLM_MODEL_PATH" \
            -c "${LLM_CONTEXT:-32768}" \
            -ngl 99 \
            --host 127.0.0.1 --port "$LLM_PORT" \
            --jinja \
            $REASONING_FLAG \
            > llama-server.log 2>&1 &
        LLAMA_SERVER_PID=$!
        LLAMA_SERVER_STARTED_BY_US=1

        # Wait up to 180s for the model to load and /health to return 200.
        # 26B MoE on M-series Metal typically loads in 20-40s cold.
        HEALTH_OK=""
        for i in $(seq 1 180); do
            if curl -sS -m 2 -o /dev/null "${LLM_URL}/health" 2>/dev/null; then
                HEALTH_OK=1
                break
            fi
            # Detect early crash so we don't wait the full 3 minutes.
            if ! kill -0 "$LLAMA_SERVER_PID" 2>/dev/null; then
                echo "ERROR: llama-server exited before becoming healthy. Last log lines:" >&2
                tail -20 llama-server.log >&2
                exit 1
            fi
            sleep 1
        done
        if [ -z "$HEALTH_OK" ]; then
            echo "ERROR: llama-server did not become healthy within 180s. Last log lines:" >&2
            tail -20 llama-server.log >&2
            kill -TERM "$LLAMA_SERVER_PID" 2>/dev/null
            exit 1
        fi
        echo "[$(date '+%F %T')] llama-server ready (pid $LLAMA_SERVER_PID)"
    fi
fi

# 1. Fetch Reddit Data
run_with_timeout 180 python3 fetch_reddit.py

# 2. Generate Podcast Script
# Timeout is generous because local inference (Gemma 4 26B-A4B + reasoning)
# takes ~75s on M4 Max Metal — 600s leaves ~8x headroom for thermal throttling
# or cold-start edge cases. Gemini API path typically returns in ~10-15s and
# is unaffected.
run_with_timeout 600 python3 summarize_news.py

# Date format: "March 31, 2026"
DATE_STR=$(date "+%B %d, %Y")

# Time-of-day suffix so manual runs (or additional cron entries) don't
# collide with the default 6 AM morning episode. Morning stays unadorned
# for backward compatibility with the existing episode archive.
HOUR_NUM=$((10#$(date "+%H")))
if [ $HOUR_NUM -ge 12 ] && [ $HOUR_NUM -lt 17 ]; then
    TOD_SUFFIX=" - Afternoon"
elif [ $HOUR_NUM -ge 17 ] && [ $HOUR_NUM -lt 21 ]; then
    TOD_SUFFIX=" - Evening"
elif [ $HOUR_NUM -ge 21 ] || [ $HOUR_NUM -lt 5 ]; then
    TOD_SUFFIX=" - Late Night"
else
    TOD_SUFFIX=""  # 5-11, morning default
fi
FILENAME="Reddit Wire${TOD_SUFFIX} - ${DATE_STR}"
cp podcast_script.txt "output/${FILENAME}.txt"
if [ -f podcast_description.txt ]; then
    cp podcast_description.txt "output/${FILENAME}.description.txt"
fi
if [ -f podcast_closing.txt ]; then
    cp podcast_closing.txt "output/${FILENAME}.closing.txt"
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
