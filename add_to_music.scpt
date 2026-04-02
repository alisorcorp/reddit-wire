on run argv
	set posixPath to (item 1 of argv)
	set playlistName to "Reddit AI News"
	
	tell application "Music"
		-- Ensure the playlist exists
		if not (exists playlist playlistName) then
			make new user playlist with properties {name:playlistName}
		end if
		
		try
			-- KEY FIX: Use 'as alias' to grant the sandboxed Music app permission
			set theFile to (posixPath as POSIX file) as alias
			
			-- Add the track to the specific playlist
			set theTrack to (add theFile to playlist playlistName)
			
			-- KEY FIX: Add a small delay so Music app can finish processing
			delay 2
			
			-- Now set the genre
			set genre of theTrack to "AI Podcast"
		on error errMsg number errNum
			log "Error adding track: " & errMsg & " (" & errNum & ")"
			error errMsg number errNum
		end try
	end tell
end run
