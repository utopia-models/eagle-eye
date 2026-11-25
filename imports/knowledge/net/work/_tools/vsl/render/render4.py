#!/usr/bin/env python3
"""render2.py <schedule.json> : sched = {post, tabs:[app,diagram], steps:[{t, do: app|click:<text>|diagram|beat:<n>}], end}. Times in take seconds (already cued early)."""
import json, sys, time, base64
from playwright.sync_api import sync_playwright

CUR = """(()=>{if(document.getElementById('__cur'))return;const c=document.createElement('div');c.id='__cur';
c.style.cssText='position:fixed;left:0;top:0;width:24px;height:24px;z-index:2147483647;pointer-events:none;transform:translate(960px,540px)';
c.innerHTML='<svg width=24 height=24 viewBox="0 0 22 22"><path d="M2 2 L2 18 L7 13.5 L10.5 20 L13 18.8 L9.6 12.5 L16 12 Z" fill="#111" stroke="#fff" stroke-width="1.5"/></svg>';
document.documentElement.appendChild(c);window.__mv=(x,y)=>{c.style.transform='translate('+x+'px,'+y+'px)'};})();"""
POS = [960.0, 540.0]
def ease(t): return t * t * (3 - 2 * t)
def glide(pg, x, y, dur=0.7):
    """eased move with a small overshoot, then settle, so it reads as a hand not a robot"""
    pg.evaluate(CUR)
    ox, oy = x + 9, y + 6
    for (tx, ty, d) in ((ox, oy, dur), (x, y, 0.12)):
        n = max(6, int(d * 30)); x0, y0 = POS
        for i in range(1, n + 1):
            e = ease(i / n); px, py = x0 + (tx - x0) * e, y0 + (ty - y0) * e
            pg.mouse.move(px, py); pg.evaluate("([x,y])=>window.__mv&&__mv(x,y)", [px, py]); time.sleep(d / n)
        POS[0], POS[1] = tx, ty
def human_click(pg, text):
    loc = pg.get_by_test_id(text[7:]) if text.startswith("testid:") else pg.get_by_text(text).first; box = loc.bounding_box()
    glide(pg, box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)   # hover highlight comes from the page's own :hover
    time.sleep(0.35); loc.click()

CHECKS_JS = r"""(()=>{
const rows=[["Manifest valid (HLS)","pass"],["Manifest valid (DASH)","pass"],["DRM license issued","pass"],["Adaptive bitrate switch","fail"],["Segment duration in limit","pass"],["Rendition ladder complete","pass"]];
function paint(){
 const a=[...document.querySelectorAll('a[data-sidebar="menu-button"]')].find(x=>/Viewer Chat|Checks/.test(x.textContent));
 if(a&&!a.dataset.k){const w=document.createTreeWalker(a,NodeFilter.SHOW_TEXT);let n;while(n=w.nextNode()){if(n.nodeValue.includes('Viewer Chat'))n.nodeValue=n.nodeValue.replace('Viewer Chat','Checks')}a.dataset.k=1;const b=a.querySelector('[data-sidebar="menu-badge"]');if(b)b.remove();}
 if(!/\/chats\/?$/.test(location.pathname))return;
 const m=document.querySelector('main'); if(!m||m.dataset.checks)return; m.dataset.checks=1;
 const row=r=>'<tr style="border-top:1px solid #e5e5e5"><td style="padding:12px 8px">'+r[0]+'</td><td style="padding:12px 8px"><span style="padding:2px 10px;border-radius:999px;font-size:13px;font-weight:600;background:'+(r[1]=='pass'?'#dcfce7':'#fee2e2')+';color:'+(r[1]=='pass'?'#166534':'#991b1b')+'">'+r[1]+'</span></td></tr>';
 m.innerHTML='<div style="padding:8px 4px"><h2 style="font-size:24px;font-weight:700;margin:0">Checks</h2><p style="color:#737373;margin:4px 0 20px">Pass or fail on each check a tester can verify without opinion.</p><table style="width:100%;border-collapse:collapse;font-size:15px"><thead><tr><th style="text-align:left;padding:8px;color:#737373;font-weight:500">Check</th><th style="text-align:left;padding:8px;color:#737373;font-weight:500">Result</th></tr></thead><tbody>'+rows.map(row).join('')+'</tbody></table></div>';
}
setInterval(paint,80);})();"""
S = json.load(open(sys.argv[1]))
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--ignore-certificate-errors"])
    ctx = b.new_context(viewport={"width": S.get("viewport", [1920, 1080])[0], "height": S.get("viewport", [1920, 1080])[1]}, record_video_dir="vid", record_video_size={"width": S.get("viewport", [1920, 1080])[0], "height": S.get("viewport", [1920, 1080])[1]}, ignore_https_errors=True)
    if S.get("checks"): ctx.add_init_script(CHECKS_JS)
    _img = base64.b64encode(open(S["post"], "rb").read()).decode()
    ctx.add_init_script("(()=>{if(!location.pathname.includes('-mvp/'))return;const d=document.createElement('div');d.id='postcover';d.style.cssText='position:fixed;inset:0;z-index:2147483640;background:#fff;overflow:hidden';d.innerHTML='<img style=\"width:100%\" src=\"data:image/png;base64,"+_img+"\">';const go=()=>{if(document.documentElement){document.documentElement.appendChild(d);return 1}};if(!go()){const i=setInterval(()=>{if(go())clearInterval(i)},2)}})();")
    if S.get("diagram_html"):
        _h = open(S["diagram_html"]).read()
        ctx.route(S["tabs"][1], lambda r: r.fulfill(body=_h, content_type="text/html"))
    pg = ctx.new_page(); tpc = time.time()
    w2 = ctx.new_page(); w2.goto(S["tabs"][1], wait_until="networkidle")
    pg.goto(S["tabs"][0], wait_until="domcontentloaded"); pg.wait_for_selector("#postcover", state="attached"); pg.wait_for_timeout(1500)
    t0 = time.time(); open('vid_offset.txt','w').write(str(round(t0 - tpc, 2)))   # post is on screen now; the video is trimmed to this moment in ffmpeg
    for st in S["steps"]:
        d = st["t"] - (time.time() - t0)
        if d > 0: time.sleep(d)
        do = st["do"]
        if do == "app": pg.evaluate("document.getElementById('postcover')&&document.getElementById('postcover').remove()"); pg.evaluate(CUR)
        elif do == "diagram": pg.goto(S["tabs"][1], wait_until="domcontentloaded")
        elif do.startswith("click:"): human_click(pg, do[6:])
        elif do.startswith("beat:"): pg.evaluate(f"location.hash='#beat={do[5:]}'")
    d = S["end"] - (time.time() - t0)
    if d > 0: time.sleep(d)
    vp = pg.video.path(); ctx.close(); b.close(); open('recorded.txt','w').write(str(vp))
