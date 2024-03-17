#######BEGIN SCRIPT############
#!/bin/bash


playlistfolder=/opt/247
hlsfolder=/var/www/html/247


 
#funtion arguments -> filename to comapre against curr time
function comparedate() {
if [ ! -f $1 ]; then
  echo "file $1 does not exist"
	exit 1
fi

MAXAGE=60 #seconds
# file age in seconds = current_time - file_modification_time.
FILEAGE=$(($(date +%s) - $(stat -c '%Y' "$1")))
test $FILEAGE -lt $MAXAGE && {
    #echo "$1 is less than 60 Seconds"
    return 0
}
#echo "$1 is older than 60 seconds."
return 1
}


rm -f /lib/systemd/system/247.service
####Writing Service File Start###
cat <<EOT >> /lib/systemd/system/247.service
[Unit]
Description=247 service
After=network.target

[Service]
Type=simple
Restart=always
ExecStart=/bin/bash $playlistfolder/service.sh
ExecReload=/bin/kill -HUP \$MAINPID


[Install]
WantedBy=multi-user.target

EOT
####Writing Service File END###
systemctl daemon-reload
systemctl enable 247.service



#printf '%s\n' "${movienames[@]}"

while :
	do
	movienames=()
	for dir in $playlistfolder/*/
		do
		name=$(basename "$dir")
		movienames+=($name)
	done


	for moviename in ${movienames[@]}
		do
	        #find $hlsfolder/*/*.ts -name '*.ts' -mmin +1 -delete >/dev/null 2>&1
		mkdir -p $hlsfolder/$moviename
                mkdir -p $playlistfolder/$moviename
		cp $playlistfolder/loading/stream.php $hlsfolder/$moviename/stream.php
		if [[ ! -e $hlsfolder/$moviename/access.txt ]]; then
    			touch $hlsfolder/$moviename/access.txt
			chmod 777 $hlsfolder/$moviename/access.txt
		fi
	        if comparedate $hlsfolder/$moviename/access.txt; then
		rm -f /lib/systemd/system/$moviename.service
####Writing Service File Start###
cat <<EOT >> /lib/systemd/system/$moviename.service
[Unit]
Description=$moviename service
After=network.target

[Service]
Type=simple
Restart=always
ExecStart=/bin/python3 $playlistfolder/video.py $moviename
ExecReload=/bin/kill -HUP \$MAINPID
KillSignal=SIGINT

[Install]
WantedBy=multi-user.target
EOT
####Writing Service File END###
			systemctl daemon-reload
        	        /usr/bin/systemctl start $moviename.service
        	else
               		/usr/bin/systemctl stop $moviename.service
			rm -f /lib/systemd/system/$moviename.service
			systemctl daemon-reload
                	find $hlsfolder/$moviename/*.ts -name '*.ts' -delete >/dev/null 2>&1
                	find $hlsfolder/$moviename/stream.m3u8 -name 'stream.m3u8' -delete >/dev/null 2>&1
                	cp $playlistfolder/loading/*.* $hlsfolder/$moviename/ -r
        	fi
	done
	sleep 1
done
