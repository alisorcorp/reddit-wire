#!/bin/bash

# Automatically switch to the directory where this script is located
cd "$(dirname "$0")"
source .venv/bin/activate

# Robustly load .env variables
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

# 1. Fetch Reddit Data
python3 fetch_reddit.py

# 2. Generate Podcast Script
python3 summarize_news.py

# Date format: "March 31, 2026"
DATE_STR=$(date "+%B %d, %Y")
FILENAME="Reddit Daily - ${DATE_STR}"
cp podcast_script.txt "output/${FILENAME}.txt"

# 3. Generate Audio (Local Kokoro)
if python3 generate_vo.py "${FILENAME}"; then
    echo "VO generated successfully."

    # 4. Mix with stinger and music bed
    VO_MP3="output/${FILENAME}.mp3"
    STINGER="audio/Reddit_News-stinger.mp3"
    BED="audio/Reddit_News-bed.mp3"
    FINAL_MP3="output/${FILENAME} - Final.mp3"

    if [ -f "$STINGER" ] && [ -f "$BED" ]; then
        VO_DURATION=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$VO_MP3")
        echo "Mixing audio (stinger + VO with music bed)..."
        ffmpeg -y \
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
          -map "[out]" -b:a 192k "$FINAL_MP3" 2>/dev/null
        echo "Final mix saved: $FINAL_MP3"
    else
        echo "Warning: Stinger or bed not found, skipping mix."
        FINAL_MP3="$VO_MP3"
    fi

    echo "Audio briefing generated successfully: $(date)"

    # 5. Sync to Apple Music
    if [ "$APPLE_MUSIC_SYNC" = "true" ]; then
        MP3_FILENAME="$(basename "$FINAL_MP3")"
        LOCAL_MP3="$FINAL_MP3"
        # KEY FIX: Using the 'Music' folder as the safe zone for sandboxed import
        TEMP_MP3="$HOME/Music/${MP3_FILENAME}"
        
        cp "$LOCAL_MP3" "$TEMP_MP3"
        echo "Syncing $TEMP_MP3 to Apple Music..."
        
        # KEY FIX: The AppleScript now uses 'alias' to bypass sandboxing
        if osascript add_to_music.scpt "$TEMP_MP3"; then
            echo "Successfully added to 'Reddit AI News' playlist."
        else
            echo "Error: Could not sync to Apple Music. Check 'error.log'."
        fi
        
        # Clean up temporary file
        rm "$TEMP_MP3"
    else
        echo "Apple Music Sync is disabled in .env."
    fi
else
    echo "Local Kokoro failed, using macOS 'say' as fallback..."
    say -f podcast_script.txt -o "output/${FILENAME}.aiff"
fi
