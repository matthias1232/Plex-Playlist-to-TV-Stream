basefolder="$(dirname "$(realpath "$0")")"
movienames=()
for dir in $basefolder/userdata/movies/*/
    do
    name=$(basename "$dir")
    movienames+=($name)
done

rm -f $basefolder/userdata/playlist.m3u8x
touch $basefolder/userdata/playlist.m3u8x
chmod 777 $basefolder/userdata/playlist.m3u8x

#####Writing Playlist file#####
echo "#EXTM3U" >> $basefolder/userdata/playlist.m3u8x
for moviename in "${movienames[@]}"; do
    echo '#EXTINF:0001 tvg-id="'${moviename}'" group-title="24x7" tvg-name="'${moviename}' EPG", 24x7' ${moviename} >> $basefolder/userdata/playlist.m3u8x
    echo "pipe:///opt/247/run_pipe.sh ${moviename}" >> $basefolder/userdata/playlist.m3u8x
done

cp $basefolder/userdata/playlist.m3u8x $basefolder/userdata/playlist.m3u8
rm $basefolder/userdata/playlist.m3u8x
chmod 777 $basefolder/userdata/playlist.m3u8