#######BEGIN SCRIPT############
#!/bin/bash
# This checks that the specified file is less than 28 hours old.
# returns 0 if younger than 28 hours.
# returns 1 if older than 28 hours.
 
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
ExecStart=/bin/bash /opt/247/service.sh
ExecReload=/bin/kill -HUP \$MAINPID


[Install]
WantedBy=multi-user.target

EOT
####Writing Service File END###
systemctl daemon-reload
systemctl enable 247.service








movienames=()
for dir in /opt/247/*/
do
name=$(basename "$dir")
movienames+=($name)
done

#printf '%s\n' "${movienames[@]}"

while :
do
	for moviename in ${movienames[@]}
		do
	        #find /var/www/html/247/*/*.ts -name '*.ts' -mmin +1 -delete >/dev/null 2>&1
		mkdir -p /var/www/html/247/$moviename
                mkdir -p /opt/247/$moviename
		cp /opt/247/loading/stream.php /var/www/html/247/$moviename/stream.php
		if [[ ! -e /var/www/html/247/$moviename/access.txt ]]; then
    			touch /var/www/html/247/$moviename/access.txt
		fi
	        if comparedate /var/www/html/247/$moviename/access.txt; then
		rm -f /lib/systemd/system/$moviename.service
####Writing Service File Start###
cat <<EOT >> /lib/systemd/system/$moviename.service
[Unit]
Description=$moviename service
After=network.target

[Service]
Type=simple
Restart=always
ExecStart=/bin/python3 /opt/247/video.py $moviename
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
                	find /var/www/html/247/$moviename/*.ts -name '*.ts' -delete >/dev/null 2>&1
                	find /var/www/html/247/$moviename/stream.m3u8 -name 'stream.m3u8' -delete >/dev/null 2>&1
                	cp /opt/247/loading/*.* /var/www/html/247/$moviename/ -r
        	fi
	done
	sleep 1
done
