#!/bin/bash
# batch.sh tag:package-dir:introCx ... : builds intro VSLs one at a time (Ra RAM), publishes each to /var/tmp/eagle-send, logs to ~/render/batch.log
cd ~/render
for spec in "$@"; do
  IFS=: read tag pkg intro <<< "$spec"
  s=$(date +%s)
  /opt/voice-v3/venv/bin/python build_intro.py /home/upwork/oneshot/packages/$pkg $tag --intro /var/tmp/eagle-send/intros/$intro > $tag.log 2>&1
  if [ -f $tag/$tag-intro.mp4 ]; then
    cp $tag/$tag-intro.mp4 /var/tmp/eagle-send/$tag-intro.mp4; cp $tag/$tag-intro.json /var/tmp/eagle-send/$tag-intro-qa.json; chmod 664 /var/tmp/eagle-send/$tag-intro*
    echo "$(date -u +%H:%MZ) DONE $tag $(( $(date +%s)-s ))s $(sha256sum /var/tmp/eagle-send/$tag-intro.mp4 | cut -c1-16)" >> batch.log
  else echo "$(date -u +%H:%MZ) FAIL $tag (see $tag.log)" >> batch.log; fi
done
