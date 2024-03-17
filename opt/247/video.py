#!/usr/bin/env python3

import subprocess
import shlex
import re
import os, time
from timeit import default_timer as timer
import sys
from pathlib import Path
import argparse

def file_age(filepath):
    return time.time() - os.path.getmtime(filepath)

moviename = sys.argv[1]
playlistfolder = "/opt/247/"
hlsfolder = "/var/www/html/247/"

mkdir = Path(playlistfolder)
mkdir.mkdir(parents=True, exist_ok=True)

mkdir = Path(hlsfolder)
mkdir.mkdir(parents=True, exist_ok=True)

mkdir = Path(playlistfolder + moviename)
mkdir.mkdir(parents=True, exist_ok=True)

mkdir = Path(hlsfolder + moviename)
mkdir.mkdir(parents=True, exist_ok=True)
os.chmod(hlsfolder + moviename, 0o0777)

phpfile= hlsfolder + moviename + '/stream.php'
phpfilecontent = ["<?php", "$stream = file_get_contents('stream.m3u8');", "echo $stream;", "file_put_contents('access.txt', '0');", "?>"]
with open(phpfile, 'w') as f:
    for php in phpfilecontent:
        f.write(php)
        f.write('\n')
print("stream.php created")

#subprocess.run(shlex.split('/usr/bin/ffmpeg -re -err_detect ignore_err -f concat -safe 0 -protocol_whitelist file,http,https,tcp,crypto,data,tls -stream_loop -1 -i /opt/247/two-and-a-half-men/playlist.txt -max_muxing_queue_size 999999 -map 0:v:0 -map 0:a:0 -map 0:a:1? -c:a copy -c:v copy -f hls -hls_time 8 -hls_list_size 10 -hls_flags delete_segments /var/www/html/247/two-and-a-half-men/stream.m3u8'))

playlistfile = playlistfolder + moviename + "/playlist.txt"



with open(playlistfile) as play:
    playlistfile = [play.rstrip() for play in play]

###get last played seconds ago###
try:
    lastplaytimesecago = file_age(playlistfolder + moviename + '/timer.txt') # 7200 seconds
except:
    lastplaytimesecago = 0

lastplaytimesecago = int(lastplaytimesecago)
print("Last Timer: " + str(lastplaytimesecago))


playlist = []
for entry in playlistfile:
    entry = re.sub(r"^.*?'", "", entry)
    duration = entry.split(";", 1)[1]
    duration = int(duration)
    durationsec = int(duration) / 1000
    durationsec = int(durationsec)
    entry = entry.split(";", 1)[0]
    playlist.append(entry)

    #print(str(durationsec))

#print("Duration: " + str(durationsec))
#print(playlist)

playlistentries=len(playlist)
playlistentries=int(playlistentries)

try:
    with open(playlistfolder + moviename + '/position.txt') as f:
        position = f.readline().strip('\n')
        position=int(position)
        if position == False:
            position = 1
        position = int(position)
except:
    position = 1

if position > playlistentries:
    position = 1

#print(position)

try:
    with open(playlistfolder + moviename + '/timer.txt') as f:
        lasttime = f.readline().strip('\n')
        if lasttime == '':
            lasttime  = 0
        lasttime = int(lasttime)
except:
    lasttime = 0


#####Calculate new Video Point###
while lastplaytimesecago > 0:
    entry_number = 1
    for entry in playlistfile:
        entry = re.sub(r"^.*?'", "", entry)
        duration = entry.split(";", 1)[1]
        duration = int(duration)
        durationsec = int(duration) / 1000
        durationsec = int(durationsec)
        entry = entry.split(";", 1)[0]
        if position > playlistentries:
            position = 1
        if entry_number > playlistentries:
            entry_number = 1
        if entry_number == position:
            if lastplaytimesecago >= durationsec:
                if durationsec == 0:
                    durationsec = 1
                lastplaytimesecago = lastplaytimesecago - durationsec
                position = position + 1
                continue
            if lastplaytimesecago < durationsec:
               if durationsec < lasttime:
                   lasttime = lasttime - durationsec
                   position = position + 1
               if durationsec > lasttime:
                   lasttime = lasttime + lastplaytimesecago
                   lastplaytimesecago = 0

        entry_number = entry_number + 1
    #lastplaytimesecago = 0

print("New Position = " + str(position))
print("New Lst Time = " + str(lasttime))



#print(str(playlistentries))

retry = 0
while True:
    entry_number = 1
    if position > playlistentries:
        position = 1

    for play in playlist:

        if position > playlistentries:
            position = 1
        if entry_number > playlistentries:
            entry_number = 1
        now = time.time()

        #print(str(retry) + " " + str(entry_number) + " " + str(position))
        if retry < 5 and entry_number == position:
            try:
                start = timer()
                #subprocess.run(shlex.split('/usr/bin/ffmpeg -fflags +igndts -re -sseof -15 -err_detect ignore_err -protocol_whitelist file,http,https,tcp,crypto,data,tls -i "/opt/247/cow.mp4" -tune zerolatency -strftime 1 -max_muxing_queue_size 999999 -map 0:v:0 -map 0:a:0 -map 0:a:1? -c:a ac3 -c:v copy -crf 23 -x264-params keyint=50:min-keyint=25:scenecut=-1 -maxrate 1300k -bufsize 2600k -preset faster -tune zerolatency -level 3.1 -c:a ac3 -flags +cgop -f hls -hls_time 15 -hls_list_size 6 -hls_flags append_list+delete_segments+omit_endlist /var/www/html/247/two-and-a-half-men/stream.m3u8')) 
                subprocess.run(shlex.split('/usr/bin/ffmpeg -fflags +igndts -re -ss ' + str(lasttime) + ' -protocol_whitelist file,http,https,tcp,crypto,data,tls -i ' + '"' + play + '"' + ' -movflags +faststart -tune zerolatency -strftime 1 -max_muxing_queue_size 999999 -map 0:v:0? -map 0:a:0? -map 0:a:1? -c:a ac3 -c:v copy -crf 23 -x264-params keyint=50:min-keyint=25:scenecut=-1 -maxrate 1300k -bufsize 2600k -preset faster -tune zerolatency -level 3.1 -c:a ac3 -flags +cgop -f hls -hls_time 6 -hls_list_size 7 -hls_flags append_list+delete_segments+omit_endlist ' + hlsfolder + moviename + '/stream.m3u8'))
                #subprocess.run(shlex.split('/usr/bin/ffmpeg -ss 2 -re -err_detect ignore_err -protocol_whitelist file,http,https,tcp,crypto,data,tls -i ' + '"' + play + '"' + ' -max_muxing_queue_size 999999 -map 0:v:0 -map 0:a:0 -map 0:a:1? -c:a copy -c:v copy -f hls -hls_time 8 -hls_list_size 2 -hls_wrap 2 -hls_flags delete_segments+append_list+split_by_time /var/www/html/247/two-and-a-half-men/stream.m3u8'))
                position = position +1
                retry = 0
                elapsed_time = 0
                lasttime = 0
                f = open(playlistfolder + moviename + "/timer.txt", "w")
                f.write(str(elapsed_time))
                f.close()
                time.sleep(3)
            except KeyboardInterrupt:
                elapsed_time = timer() - start # in seconds
                elapsed_time = int(elapsed_time)
                elapsed_time = elapsed_time + lasttime
                f = open(playlistfolder + moviename + "/timer.txt", "w")
                f.write(str(elapsed_time))
                f.close()
                f = open(playlistfolder + moviename + "/position.txt", "w")
                f.write(str(position))
                f.close()
                print ("Bye")
                sys.exit()
            except:
                retry = retry + 1
                elapsed_time = timer() - start # in seconds
                elapsed_time = int(elapsed_time)
                elapsed_time = elapsed_time + lasttime
                f = open(playlistfolder + moviename + "/timer.txt", "w")
                f.write(str(elapsed_time))
                f.close()
                f = open(playlistfolder + moviename + "/position.txt", "w")
                f.write(str(position))
                f.close()
                time.sleep(3)
        else:
             if retry >= 5:
                position = position +1
                elapsed_time = 0
                lasttime = 0
                retry = 0
        entry_number = entry_number + 1

    if position > playlistentries:
        position = 1
    retry = 0
    f = open(playlistfolder + moviename + "/position.txt", "w")
    f.write(str(position))
    f.close()
