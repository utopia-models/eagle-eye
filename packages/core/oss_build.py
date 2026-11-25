#!/usr/bin/env python3
"""oss_build.py V2 OUT: the open-source Eagle Eye build from the v2 page (knowledge#13617). Replaces the PIPES/DOORS
defaults with neutral lanes, drops every comment line, and stamps the Apache-2.0 header. Grep OUT for internal names
before pushing to github.com/utopia-models/eagle-eye."""
import re,sys
s=open(sys.argv[1]).read()
i=s.index("const PIPES = ["); j=s.index("];",i)+2
s=s[:i]+"""const PIPES = [   // default lanes; config.js (window.EAGLE_EYE.pipes) replaces them
  {id:'applications', ring:0, hk:'applications', name:'Applications', short:'Applications', w:3},
  {id:'outreach', ring:0, hk:'outreach', name:'Outreach', short:'Outreach', w:1},
  {id:'network', ring:1, rk:'network', name:'Network', short:'Network', w:1},
];"""+s[j:]
s=re.sub(r"const DOORS = \{.*?\};\n", "const DOORS = {};   // lane -> {agent, kind:'desk'|'view', url, where}; config.js (window.EAGLE_EYE.doors) fills it\n", s, count=1, flags=re.S)
s=re.sub(r"const SRCNAME = \{[^}]*\};", "const SRCNAME = {};", s, count=1)
out=[]
for ln in s.split("\n"):
    t=ln.strip()
    if t.startswith("//"):
        continue
    ln=re.sub(r"\s+//[^'\"`]*$", "", ln)   # trailing comments with no quotes after them
    out.append(ln)
s="\n".join(out)
s=re.sub(r"\s*\(knowledge#\d+\)","",s)
s=s.replace("<<HDR>>","")
hdr="""// Eagle Eye: one screen for every outreach pipeline you run. The eye in the middle, your hunts (what you send out)
// on the outer ring, your roosts (what comes back) on the inner ring, and the live lane's funnel in a card.
// Copyright 2026 Utopia Models, Inc. Licensed under the Apache License, Version 2.0 (see LICENSE).
// Config: window.EAGLE_EYE = {feed, title, pipes, doors, stages, key4, liveLabel, hero:false, pipelines:false}
// (config.js documents every key). Feed shape: docs/FEED.md.
"""
s=s.replace("CFG.lanePages===false","!CFG.lanePages")   # lane pages are opt-in outside Utopia (lanePages:true + laneBase)
open(sys.argv[2],'w').write(hdr+s)
