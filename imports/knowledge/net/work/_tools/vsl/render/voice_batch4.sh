#!/bin/bash
# voice_batch.sh : on Ra, build each intro VSL as soon as Eagle's voice dir for it is complete (cues.json present + one NN.wav per row); one at a time
cd ~/render
declare -A INTRO=( [3307]=intro-C2-take2.mkv [7816]=intro-C4-take1.mkv [6728]=intro-C4-take1.mkv [3463]=intro-C7-take1.mkv )
declare -A PKG=( [3307]=up-technical-lead-cto-for-ai-styling-3307 [7816]=up-supplier-account-data-scraper-7816 [6728]=up-senior-python-engineer-discord-ale-6728 [3463]=up-head-of-ai-ai-manager-3463 )
done_list=" "
while true; do
  for t in 3463; do
    case "$done_list" in *" $t "*) continue;; esac
    d=/var/tmp/eagle-send/voice-out/$t; [ -f $d/cues.json ] || continue
    n=$(wc -l < /var/tmp/eagle-send/voice/$t/rows.txt); w=$(ls $d/[0-9][0-9].wav 2>/dev/null | wc -l); [ "$w" -ge "$n" ] || continue
    s=$(date +%s); rm -rf $t
    /opt/voice-v3/venv/bin/python build_intro.py /home/upwork/oneshot/packages/${PKG[$t]} $t --intro /var/tmp/eagle-send/intros/${INTRO[$t]} --voice-dir $d > $t.voice3.log 2>&1
    if [ -f $t/$t-intro.mp4 ]; then cp $t/$t-intro.mp4 /var/tmp/eagle-send/$t-intro-v2.mp4; cp $t/$t-intro.json /var/tmp/eagle-send/$t-intro-v2-qa.json; chmod 664 /var/tmp/eagle-send/$t-intro-v2*
      echo "$(date -u +%H:%MZ) DONE $t $(( $(date +%s)-s ))s $(sha256sum /var/tmp/eagle-send/$t-intro-v2.mp4 | cut -c1-16)" >> voice_batch3.log
    else echo "$(date -u +%H:%MZ) FAIL $t" >> voice_batch3.log; fi
    done_list="$done_list$t "
  done
  [ $(echo $done_list | wc -w) -ge 1 ] && break
  sleep 10
done
