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
    echo "Audio briefing generated successfully: $(date)"
    
    # 4. Sync to Apple Music
    if [ "$APPLE_MUSIC_SYNC" = "true" ]; then
        MP3_FILENAME="${FILENAME}.mp3"
        LOCAL_MP3="output/${MP3_FILENAME}"
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
