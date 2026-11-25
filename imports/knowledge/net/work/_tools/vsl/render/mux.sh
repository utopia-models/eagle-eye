#!/bin/bash
# mux.sh <jobdir> <take.mp4> <reveal_sched_s> <dur_s> <out.mp4> : aligns the recorded screen track by the first dark frame (= the app reveal), adds face card + take audio
set -e; cd "$1"; V=$(cat recorded.txt)
T=$(ffmpeg -i "$V" -vf "select='gt(scene,0.25)',showinfo" -an -f null - 2>&1 | grep -o "pts_time:[0-9.]*" | head -1 | sed 's/pts_time://')
O=$(python3 -c "print(round($T-$3+0.35,2))")   # +0.35: the screen clock drifts ~0.7 s slower over a take; split the difference; echo "detected offset $O (first dark $T, reveal $3)"
ffmpeg -v error -y -ss $O -i "$V" -i "$2" -filter_complex "[0:v]scale=1920:1080,setsar=1[bg];[1:v]scale=320:180[f];[bg][f]overlay=W-w-12:H-h-12[v]" -map "[v]" -map 1:a -t $4 -c:v libx264 -preset medium -b:v 2500k -maxrate 3M -bufsize 6M -pix_fmt yuv420p -c:a aac -b:a 160k "$5"
