on run argv
	set posixPath to (item 1 of argv)
	set playlistName to "Reddit AI News"

	-- Launch Music and wait for it to be ready (critical for launchd/headless runs)
	tell application "Music" to activate
	delay 5

	tell application "Music"
		with timeout of 120 seconds
			-- Ensure the playlist exists
			if not (exists playlist playlistName) then
				make new user playlist with properties {name:playlistName}
			end if

			try
					set theFile to (posixPath as POSIX file) as alias

				-- Add the track to the specific playlist
				set theTrack to (add theFile to playlist playlistName)

				-- Wait for Music to finish importing before setting metadata
				delay 5

				-- Now set the genre
				set genre of theTrack to "AI Podcast"
			on error errMsg number errNum
				log "Error adding track: " & errMsg & " (" & errNum & ")"
				error errMsg number errNum
			end try
		end timeout
	end tell
end run
