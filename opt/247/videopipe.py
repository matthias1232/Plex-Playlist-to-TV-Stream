#!/usr/bin/env python3

import subprocess
import shlex
import os, time
import sys
from pathlib import Path
import socket
import datetime
from dateutil import tz
from xml.etree import ElementTree as ET
import threading
import argparse
import json
import subprocess, sys, os, time, xml.etree.ElementTree as ET
shutdown_event = threading.Event()

def fast_get_video_url_from_epg(epg_file):
    if not os.path.exists(epg_file):
        return []

    context = ET.iterparse(epg_file, events=("start", "end"))
    _, root = next(context)  # get root element
    now = datetime.datetime.now(tz=tz.tzlocal())

    for event, elem in context:
        if event == "end" and elem.tag == "programme":
            start_str = elem.attrib.get('start')
            stop_str = elem.attrib.get('stop')
            video_url = elem.findtext('url')
            if not (start_str and stop_str and video_url):
                elem.clear()
                continue

            try:
                start = datetime.datetime.strptime(start_str[:14], "%Y%m%d%H%M%S")
                stop = datetime.datetime.strptime(stop_str[:14], "%Y%m%d%H%M%S")
                if len(start_str) > 14:
                    start = start.replace(tzinfo=tz.tzoffset(None, int(start_str[15:18]) * 60))
                else:
                    start = start.replace(tzinfo=tz.tzlocal())
                if len(stop_str) > 14:
                    stop = stop.replace(tzinfo=tz.tzoffset(None, int(stop_str[15:18]) * 60))
                else:
                    stop = stop.replace(tzinfo=tz.tzlocal())
            except Exception:
                elem.clear()
                continue

            if start <= now < stop:
                offset = int((now - start).total_seconds())
                return [video_url, offset]
            elif now < start:
                # Since EPG is sorted, we can stop early
                break
            elem.clear()
    return []




def stream_loop_from_epg_playlist(epg_file, playlistfolder, moviename):
    playlist_path = os.path.join(playlistfolder, "userdata", "movies", moviename, "playlist-stream.txt")
    os.makedirs(os.path.dirname(playlist_path), exist_ok=True)

    # 🧠 Step 1: EPG auslesen, Start-URL ermitteln
    result = fast_get_video_url_from_epg(epg_file)
    if not result or not result[0]:
        print("❌ Keine gültige Start-URL aus EPG gefunden.", file=sys.stderr)
        return
    start_url = result[0]
    start_offset = result[1] if len(result) > 1 else 0
    print(f"🔎 Start-URL aus EPG: {start_url} (Offset: {start_offset}s)", file=sys.stderr)

    # 📝 Step 2: Playlist ab Start-URL generieren
    url_list, seen = [], set()
    start_found = False

    for _, elem in ET.iterparse(epg_file, events=("end",)):
        if elem.tag != "programme":
            continue
        url = elem.findtext("url")
        if not url:
            continue

        if not start_found:
            if url == start_url:
                start_found = True
                url_list.append(url)
                seen.add(url)
        else:
            if url in seen:
                print(f"🔁 Wiederholende URL erkannt: {url} → Playlist abgeschlossen.", file=sys.stderr)
                break
            url_list.append(url)
            seen.add(url)
        elem.clear()

    if not url_list:
        print("⚠️ Keine gültige Playlist gefunden.", file=sys.stderr)
        return

    with open(playlist_path, "w") as f:
        for url in url_list:
            f.write(f"{url}\n")
    print(f"✅ Playlist gespeichert mit {len(url_list)} Einträgen: {playlist_path}", file=sys.stderr)

    # 🔧 Helper: Audio-Codec erkennen
    def get_audio_codec(url):
        try:
            codec = subprocess.check_output([
                'ffprobe', '-v', 'error',
                '-select_streams', 'a:0',
                '-show_entries', 'stream=codec_name',
                '-of', 'default=noprint_wrappers=1:nokey=1', url
            ], stderr=subprocess.DEVNULL).decode().strip()
            return 'eac3' if codec == 'dts' else codec if codec in ('aac', 'ac3', 'eac3') else 'ac3'
        except Exception as e:
            print(f"🔊 Fehler bei Codec-Erkennung: {e}", file=sys.stderr)
            return 'ac3'

    # 🚀 Step 3: Streaming-Loop
    env = os.environ.copy()
    for var in ['SDL_VIDEODRIVER', 'SDL_AUDIODRIVER', 'DISPLAY', 'XAUTHORITY', 'XDG_RUNTIME_DIR', 'WAYLAND_DISPLAY']:
        env[var] = ''

    print("📡 Starte Streaming-Loop…", file=sys.stderr)

    while True:
        with open(playlist_path) as f:
            urls = [line.strip() for line in f if line.strip()]

        for idx, url in enumerate(urls):
            offset = start_offset if idx == 0 else 0
            audio_codec = get_audio_codec(url)
            # Detect video codec to conditionally add h264_mp4toannexb filter
            def get_video_codec(url):
                try:
                    codec = subprocess.check_output([
                        'ffprobe', '-v', 'error',
                        '-select_streams', 'v:0',
                        '-show_entries', 'stream=codec_name',
                        '-of', 'default=noprint_wrappers=1:nokey=1', url
                    ], stderr=subprocess.DEVNULL).decode().strip()
                    return codec
                except Exception as e:
                    print(f"🔊 Fehler bei Video-Codec-Erkennung: {e}", file=sys.stderr)
                    return ''
            video_codec = get_video_codec(url)
            # If audio_codec is 'ac3', force to 'eac3'
            if audio_codec == 'ac3':
                ffmpeg_audio_codec = 'ac3'
            elif audio_codec == 'aac':
                ffmpeg_audio_codec = 'aac'
            elif audio_codec == 'eac3':
                ffmpeg_audio_codec = 'eac3'
            elif audio_codec == 'dts':
                ffmpeg_audio_codec = 'eac3'
            elif video_codec == 'hevc':
                ffmpeg_audio_codec = 'eac3'
            else:
                ffmpeg_audio_codec = audio_codec
            
            
            
            print(f"🎬 Streame: {url} (Offset: {offset})", file=sys.stderr)
            print(f"🎬 Codec: {audio_codec} -> {ffmpeg_audio_codec}", file=sys.stderr)
            print(f"🎬 ID: {idx}", file=sys.stderr)




            # Dynamically determine maxrate based on input file bitrate
            def get_maxrate(url):
                try:
                    # Use ffprobe to get the overall bitrate in bits per second
                    bitrate = subprocess.check_output([
                        'ffprobe', '-v', 'error',
                        '-select_streams', 'v:0',
                        '-show_entries', 'format=bit_rate',
                        '-of', 'default=noprint_wrappers=1:nokey=1', url
                    ], stderr=subprocess.DEVNULL).decode().strip()
                    if bitrate and bitrate.isdigit():
                        # Add a small buffer (e.g., 10%) to the detected bitrate
                        return str(int(int(bitrate) * 1.1))
                except Exception as e:
                    print(f"⚠️ Fehler beim Ermitteln der Bitrate: {e}", file=sys.stderr)
                # Fallback to 8 Mbps if detection fails
                return '8000000'

            maxrate_value = get_maxrate(url)

            ffmpeg_cmd = [
                'ffmpeg', '-y',
                *(['-re'] if idx != 0 else []),
                #'-re',
                '-loglevel', 'error',
                '-ss', str(offset) if idx == 0 else '0',
                #'-ss', str(offset), 
                '-i', url,
                #'-movflags', '+faststart',
                '-tune', 'fastdecode',
                #'-preset', 'ultrafast',
                '-strftime', '1',
                '-map', '0:v:0', '-map', '0:a:0', '-map', '0:a:1?',  # force mapping
                #'-map', '-0:s',  # explicitly disable subtitles
                #'-map', '-0:d',  # explicitly disable data streams
                '-c:a', ffmpeg_audio_codec,
                #'-b:a', '128k',
                '-c:v', 'copy',
                '-crf', '28' if video_codec == 'hevc' else '23',
                *(['-x264-params', 'keyint=50:min-keyint=25:scenecut=1'] if video_codec != 'hevc' else []),
                '-level', '3.1',
                '-flags', '+cgop',
                '-maxrate', str(int(maxrate_value) * 1.5),  # Add a 20% buffer
                #'-preset', 'veryfast',
                #'-tune', 'fastdecode',
                '-avoid_negative_ts', 'make_zero',
                '-muxdelay', '0',
                '-muxpreload', '10' if (idx == 0 and video_codec == 'h264' and audio_codec == 'eac3') else ('50' if idx == 0 else '10'),
                '-threads', '4',
                #'-fflags', '+discardcorrupt',
                #'-fflags', 'igndts+genpts',  # <-- Add this to help with timestamp issues
            ]
            if video_codec == 'h264':
                ffmpeg_cmd += ['-bsf:v', 'h264_mp4toannexb']
            if video_codec == 'hevc':
                ffmpeg_cmd += ['-bsf:v', 'hevc_mp4toannexb']
            ffmpeg_cmd += [
                '-f', 'mpegts',
                '-bufsize', '400M',
                'pipe:1'
            ]
            # Buffer the first segment to allow tvheadend to fill its buffer before playback
            #if idx == 0:
            buffer = bytearray()
            threshold = 25 * 1024 * 1024 if idx != 0 else 20 * 1024 * 1024  # 20 MB buffer except for first segment (5MB)
            if video_codec == 'h264' and audio_codec == 'eac3':
                threshold = 30 * 1024 * 1024 if idx != 0 else 60 * 1024 * 1024  # 20 MB buffer except for first segment (5MB)
            if video_codec == 'hevc':
                threshold = 30 * 1024 * 1024 if idx != 0 else 100 * 1024 * 1024  # 20 MB buffer except for first segment (5MB)
            if video_codec == 'h264' and audio_codec == 'ac3':
                threshold = 30 * 1024 * 1024 if idx != 0 else 40 * 1024 * 1024  # 20 MB buffer except for first segment (5MB)
            with subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=sys.stderr, env=env) as proc:
                if proc.stdout is None:
                    raise RuntimeError("Failed to open ffmpeg subprocess with stdout=PIPE")
                if idx == 0:
                    while True:
                        # Prevent tvheadend from using DTS: if detected, skip or convert
                        if audio_codec == "dts":
                            # Skip this chunk (or optionally, replace with silence or convert)
                            continue
                        #sys.stdout.buffer.flush()
                        chunk = proc.stdout.read(18192)  # Continue reading in larger chunks
                        if not chunk:
                            break
                        buffer.extend(chunk)
                        if len(buffer) >= threshold:
                            #sys.stdout.buffer.write(buffer)
                            sys.stdout.buffer.flush()
                            time.sleep(0.000015) 
                            break
                # After threshold, stream the rest directly
                while True:
                    chunk = proc.stdout.read(8192)  # Continue reading in larger chunks
                    buffer.extend(chunk)
                    if not chunk:
                        break
                    sys.stdout.buffer.write(chunk)
                    sys.stdout.buffer.flush()
                    time.sleep(0.000015)  # Short sleep to avoid overwhelming the output
                proc.wait()

                #time.sleep(0)  # Short sleep to avoid overwhelming the output
            # else:
            #     with subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=sys.stderr, env=env) as proc:
            #         while True:
            #             chunk = proc.stdout.read(8192)
            #             if not chunk:
            #                 break
            #             sys.stdout.buffer.write(chunk)
            #             sys.stdout.buffer.flush()
            #         proc.wait()
                    

        print("🔁 Playlist vollständig durchlaufen. Starte von vorne…", file=sys.stderr)

# Start streaming immediately after EPG handling
try:
    parser = argparse.ArgumentParser(description='Video pipe streaming tool')
    parser.add_argument('--moviename', required=True, help='Name of the movie/channel')
    parser.add_argument('--epg', action='store_true', help='Generate and send EPG')
    parser.add_argument('--epgupdate', action='store_true', help='Update EPG only')

    args = parser.parse_args()

    moviename = args.moviename
    epg = "epg" if args.epg else "False"
    epgupdate = "epgupdate" if args.epgupdate else "False"
    playlistfolder = str(Path(__file__).parent) + "/"
    moviefolder = f"{playlistfolder}userdata/movies/"

    if not moviename:
        print("Fehler: Kein Filmname übergeben!", file=sys.stderr)
        sys.exit(1)

    mkdir = Path(playlistfolder)
    mkdir.mkdir(parents=True, exist_ok=True)

    mkdir = Path(moviefolder)
    mkdir.mkdir(parents=True, exist_ok=True)
    
    mkdir = Path(moviefolder + moviename)
    mkdir.mkdir(parents=True, exist_ok=True)

    epg_file = moviefolder + moviename + "/epg.xml"

    if epg == "epg":
        subprocess.run(shlex.split(f'{playlistfolder}epg.py --epgfile {moviefolder}{moviename}/epg.json --offset {str(0)} --startline {0} --output {epg_file}'))
        # Send epg.xml content to the UNIX socket using Python's socket module
        #time.sleep(2)

        epg_path = epg_file
        socket_path = "/var/lib/tvheadend/epggrab/xmltv.sock"

        with open(epg_path, "rb") as f:
            epg_data = f.read()

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(socket_path)
            sock.sendall(epg_data)
    
    if epgupdate == "epgupdate":

        epg_path = epg_file
        # Load socket_path from settings.json
        try:
            with open(f"{playlistfolder}userdata/settings.json", "r") as f:
                settings = json.load(f)
                socket_path = settings.get("socket_path", "/var/lib/tvheadend/epggrab/xmltv.sock")
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            socket_path = "/var/lib/tvheadend/epggrab/xmltv.sock"  # fallback default

        with open(epg_path, "rb") as f:
            epg_data = f.read()

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(socket_path)
            sock.sendall(epg_data)
            print(f"EPG for {moviename} sent to tvheadend successfully")
            
    if epg != "epg" and epgupdate != "epgupdate":
        stream_loop_from_epg_playlist(epg_file, playlistfolder, moviename)
        
except KeyboardInterrupt:
    print("Interrupted by user", file=sys.stderr)
    shutdown_event.set()
except Exception as e:
    print(f"Error in main stream: {e}", file=sys.stderr)

