"""vsl_frame.py: the browser frame + compositing of an intro VSL (contract layout.browser / layout.post / face / orb; Tyler 2026-11-24 'we cant even see the browser or tabs').
chrome_png(): the 1920x96 browser bar (tab strip with THREE named tabs, the ACTIVE one white, + address bar) for one active tab.
compose(): rail bg 0a0907 + content (viewport recording, 1580x984, under the bar) + tab 1 = the job post scrolling top-to-bottom through the whole intro + the bar with the
active tab switching at each section + face card 480x270 flush bottom-right during the intro, then the RAW gold orb card 270x480 in the same corner moving with the AI voice."""
import subprocess
from PIL import Image, ImageDraw, ImageFont
BAR_H, PAGE_W = 96, 1580
FD = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"; FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def chrome_png(path, active, titles, urls):
    """active: 0 post | 1 app | 2 diagram; tab k at x = 12 + k*(300+6), w 300 h 34 top 8 (contract tab_geom); active_bg #ffffff, inactive #dee1e6."""
    im = Image.new("RGB", (1920, BAR_H), "#dee1e6"); d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FD, 14); fb = ImageFont.truetype(FD, 15)
    for k, t in enumerate(titles):
        x = 12 + k * 306; on = k == active
        d.rounded_rectangle([x, 8, x + 300, 8 + 40], radius=10, fill="#ffffff" if on else "#dee1e6")
        if on: d.rectangle([x, 40, x + 300, 50], fill="#ffffff")
        d.ellipse([x + 12, 20, x + 28, 36], fill=["#14a800", "#5f6368", "#d4a94e"][k])          # favicon dot (Upwork green / app / diagram gold)
        d.text((x + 38, 21), t[:30], font=f, fill="#202124" if on else "#5f6368")
        d.text((x + 276, 19), "x", font=fb, fill="#5f6368")
    d.rectangle([0, 50, 1920, BAR_H], fill="#ffffff")
    d.text((22, 62), "<", font=fb, fill="#5f6368"); d.text((54, 62), ">", font=fb, fill="#9aa0a6"); d.text((86, 61), "C", font=fb, fill="#5f6368")
    d.rounded_rectangle([130, 56, 1700, 90], radius=17, fill="#f1f3f4")
    d.ellipse([146, 66, 158, 78], outline="#5f6368", width=2); d.text((172, 63), urls[active], font=ImageFont.truetype(FD, 15), fill="#202124")
    for i, g in enumerate(("-", "[]", "x")): d.text((1790 + i * 40, 16), g, font=fb, fill="#5f6368")
    d.line([0, BAR_H - 1, 1920, BAR_H - 1], fill="#dadce0")
    im.save(path)

def compose(out, screen, offset, post_png, intro, audio_wav, orb_mp4, D, T_app, T_dia, total, chrome, face_wh=(960, 540), orb_wh=(270, 480)):
    """screen: recorded viewport webm (1580x984), -ss offset aligns take t=0; post_png: full-page capture of tab 1; chrome: [post.png, app.png, dia.png] bars."""
    fw, fh = face_wh; ow, oh = orb_wh
    inputs = ["-f", "lavfi", "-i", f"color=c=0x0a0907:s=1920x1080:r=30:d={total:.2f}",
              "-ss", str(offset), "-i", screen,
              "-loop", "1", "-framerate", "30", "-t", f"{max(D,1):.2f}", "-i", post_png,
              "-i", intro, "-i", audio_wav, "-i", orb_mp4,
              "-loop", "1", "-framerate", "30", "-t", f"{total:.2f}", "-i", chrome[0], "-loop", "1", "-framerate", "30", "-t", f"{total:.2f}", "-i", chrome[1],
              "-loop", "1", "-framerate", "30", "-t", f"{total:.2f}", "-i", chrome[2]]
    vh = 1080 - BAR_H
    fg = (f"[1:v]scale={PAGE_W}:{vh},setsar=1,fps=30,tpad=stop_mode=clone:stop_duration=8[scr];"
          f"[2:v]scale={PAGE_W}:-1,fps=30,crop={PAGE_W}:{vh}:0:'64+min(max(ih-{vh}-64,0),max(ih-{vh}-64,0)*t/{max(D-0.5,1):.2f})',format=yuv420p[post];"
          f"[0:v][scr]overlay=0:{BAR_H}:shortest=0[b1];"
          f"[b1][post]overlay=0:{BAR_H}:enable='lt(t,{D:.2f})':eof_action=pass[b2];"
          f"[b2][6:v]overlay=0:0:enable='lt(t,{D:.2f})'[b3];[b3][7:v]overlay=0:0:enable='between(t,{D:.2f},{T_dia:.2f})'[b4];[b4][8:v]overlay=0:0:enable='gte(t,{T_dia:.2f})'[b5];"
          f"[3:v]scale={fw}:{fh},setsar=1[face];[b5][face]overlay={1920-fw}:{1080-fh}:enable='lt(t,{D:.2f})':eof_action=pass[b6];"
          f"[5:v]scale={ow}:{oh},setsar=1,setpts=PTS+{D:.2f}/TB[orb];[b6][orb]overlay={1920-ow}:{1080-oh}:enable='gte(t,{D:.2f})':eof_action=pass,format=yuv420p[v]")
    cmd = ["ffmpeg", "-v", "error", "-y"] + inputs + ["-filter_complex", fg, "-map", "[v]", "-map", "4:a:0", "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "medium",
           "-b:v", "2500k", "-maxrate", "3M", "-bufsize", "6M", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", out]
    subprocess.run(cmd, check=True)


def compose_capture(out, capture, offset, intro, audio_wav, orb_mp4, D, total, face_wh=(960, 540), orb_wh=(270, 480)):
    """A REAL-browser capture (Eagle's seat recording, 1920x1080, the Chrome window with its own tab strip/address bar) is the base layer; the builder adds only the face card
    (intro) then the RAW orb in the same bottom-right slot, and the loudnormed audio. No drawn browser chrome."""
    fw, fh = face_wh; ow, oh = orb_wh
    fg = (f"[0:v]scale=1920:1080,setsar=1,fps=30,tpad=stop_mode=clone:stop_duration=8[bg];"
          f"[1:v]scale={fw}:{fh},setsar=1[face];[bg][face]overlay={1920-fw}:{1080-fh}:enable='lt(t,{D:.2f})':eof_action=pass[b1];"
          f"[3:v]scale={ow}:{oh},setsar=1,setpts=PTS+{D:.2f}/TB[orb];[b1][orb]overlay={1920-ow}:{1080-oh}:enable='gte(t,{D:.2f})':eof_action=pass,format=yuv420p[v]")
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", str(offset), "-i", capture, "-i", intro, "-i", audio_wav, "-i", orb_mp4, "-filter_complex", fg, "-map", "[v]", "-map", "2:a:0",
           "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "medium", "-b:v", "3M", "-maxrate", "4M", "-bufsize", "8M", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", out]
    subprocess.run(cmd, check=True)


def compose_capture_v6(out, capture, offset, intro, audio_wav, orb_mov, D, total, frac=0.18, margin=40, fade=0.6, lead=0.3):
    """Intro look v6 (Architect 22408): the real-browser capture is the base; face and orb are SAME-size circles, `frac` of the width, bottom-right; the face
    cross-fades into the orb over `fade` s starting `lead` s BEFORE D (Architect 22413: the fade begins while Tyler is still speaking); the orb is a transparent-background alpha clip (ProRes 4444) overlaid with ffmpeg."""
    d = int(round(1920 * frac / 2.0)) * 2
    x, y = 1920 - d - margin, 1080 - d - margin
    circle = f"if(lte(hypot(X-{d}/2,Y-{d}/2),{d}/2),255,0)"
    fg = (f"[0:v]scale=1920:1080,setsar=1,fps=30,tpad=stop_mode=clone:stop_duration=8[bg];"
          f"[1:v]crop='min(iw,ih)':'min(iw,ih)',scale={d}:{d},setsar=1,fps=30,format=rgba,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='{circle}',"
          f"tpad=stop_mode=clone:stop_duration={fade + 1:.2f},fade=t=out:st={D - lead:.2f}:d={fade}:alpha=1[face];"
          f"[3:v]crop=iw*0.64:ih*0.64,scale={d}:{d},setsar=1,format=rgba,fps=30,setpts=PTS+{D - lead:.2f}/TB,fade=t=in:st={D - lead:.2f}:d={fade}:alpha=1[orb];"
          f"[bg][face]overlay={x}:{y}:eof_action=pass[b1];[b1][orb]overlay={x}:{y}:eof_action=pass,format=yuv420p[v]")
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", str(offset), "-i", capture, "-i", intro, "-i", audio_wav, "-i", orb_mov, "-filter_complex", fg, "-map", "[v]", "-map", "2:a:0",
           "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "medium", "-b:v", "3M", "-maxrate", "4M", "-bufsize", "8M", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", out]
    subprocess.run(cmd, check=True)
