on run argv
    set inputFile to POSIX file (item 1 of argv)
    set outputFile to POSIX file (item 2 of argv)
    set uniqueName to item 3 of argv
    tell application id "com.microsoft.Powerpoint"
        with timeout of 45 seconds
            open inputFile
            set privateDeck to presentation uniqueName
            try
                save privateDeck in (outputFile as text) as save as PDF
            on error errorText number errorNumber
                close privateDeck saving no
                error errorText number errorNumber
            end try
            close privateDeck saving no
            return version
        end timeout
    end tell
end run
