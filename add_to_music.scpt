on run argv
	set posixPath to (item 1 of argv)
	if (count of argv) ≥ 2 and (item 2 of argv) is not "" then
		set playlistName to (item 2 of argv)
	else
		set playlistName to "Reddit AI News"
	end if

	-- Launch Music and poll until it responds (critical for launchd/headless runs)
	tell application "Music" to activate
	set musicReady to false
	repeat 30 times
		try
			tell application "Music" to get name of source 1
			set musicReady to true
			exit repeat
		end try
		delay 2
	end repeat

	if not musicReady then
		error "Music app did not become responsive after 60 seconds" number -1
	end if

	-- Extra settle time after first response — Music may accept AppleEvents
	-- before it can actually perform library operations (especially on wake from sleep)
	delay 5

	tell application "Music"
		with timeout of 300 seconds
			-- Ensure the playlist exists
			if not (exists playlist playlistName) then
				make new user playlist with properties {name:playlistName}
			end if

			set theFile to (posixPath as POSIX file) as alias

			-- Retry the add up to 3 times — Music sometimes needs a moment
			-- after waking to handle file imports
			set theTrack to missing value
			set lastErr to ""
			repeat 3 times
				try
					set theTrack to (add theFile to playlist playlistName)
					exit repeat
				on error errMsg
					set lastErr to errMsg
					delay 10
				end try
			end repeat

			if theTrack is missing value then
				error "Failed to add track after 3 attempts: " & lastErr number -1
			end if

			-- Wait for Music to finish importing before setting metadata
			delay 5
			set genre of theTrack to "AI Podcast"
		end timeout
	end tell
end run
