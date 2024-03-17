This Tools creates a 24/7 Streaming Service for your Videos hosted in Plex Playlists.

Create a playlist with the tool PlexURLGen, the modified Version is in the "loading folder" (/opt/247/loading/PlexURLGen/plex)
The Original Script and Documentation is here:
https://github.com/BalliAsghar/PlexURLGen

Everything is original from the creator, i just added the movie duration to the command "playlist"

Example Playlist Output is:
https://your-plexserver.com:8443/library/parts/593852/1555545600/file.mkv?X-Plex-Token=XXXXXXXXXXXXXXXXXXXX&download=1;5287082

The Service is made for your home usage, so the HLS Stream and ffmpeg are not running 24/7. 
The Stream.php file creates an access.txt file. If this file is not older than 1 Minute, the service.sh will start the Service for your playlist.
After you stop watching the Stream, it will be stopped after 1 Minute.

Next time you start your stream the position of the Video will be calucated based the Stream was always running since you last watched it. So it is like a 24/7 Stream.

After you first run service.sh a Service will be created with the name 247:
/lib/systemd/system/247.service

You can then stop the script and run it again with:
service 247 start

Default location for your HLS webserver is /var/www/html/247/ (you can change it in video.py)

You can also run some specific Stream as real 24/7 with "video.py your-playlist" (your-playlist = name of your playlist file without .txt)

