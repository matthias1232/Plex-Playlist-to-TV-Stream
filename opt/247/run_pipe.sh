#!/bin/bash
python3 /opt/247/videopipe.py --moviename="$1" | ffmpeg -i - -map 0 -fflags igndts+genpts+discardcorrupt -c copy -f mpegts - 2>/dev/null | mbuffer -m 600M 2>/dev/null
