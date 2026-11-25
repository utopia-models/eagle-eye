; layout.ahk: the laptop's screen for a custom VSL take (knowledge#14099). Run by `vsl prep <client>` from Ra, in Tyler's
; session (fast.py ps starts it), from C:\vsl\_tools\. AutoHotkey v2 (C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe).
;
;   AutoHotkey64.exe layout.ahk <demo-url> <obs x,y,w,h> <vizier x,y,w,h> <demo x,y,w,h> <result.json> [fix]
;   (each box in fractions of the primary monitor's work area, e.g. 0.75,0,0.25,0.25)
;   `fix` (knowledge#14117: laptop-eye.py on Ra, when a frame mid-session breaks the layout): the demo window already
;   open (a Chrome of profile C:\vsl\chrome) is KEPT, page and all, and only re-placed; every other browser window,
;   a second demo-profile window included, is closed as in prep. The demo is launched only when none is open.
;
; 🔴 knowledge#15113: DEMO TAKES ONLY. `vsl prep` / `vsl rec` / `vsl start` never call this for a profile take, and fast.py /
;   eth-listen refuse it from /ps. Without a demo URL this script does nothing to windows. Moonlight is NEVER minimized
;   (OBS captures that window: a minimized one records black) and OBS goes full screen unless a box is given.
; 1. every browser window is closed (WM_CLOSE) and every other window minimized (never closed: nothing is lost), except
;    OBS, Vizier and the shell; Moonlight is left alone (never minimized);
; 2. the demo opens as ONE chromeless Chrome app window (--app: no tab strip, no address bar) in its own profile
;    C:\vsl\chrome, and is placed in its box;
; 3. OBS (shown from the tray if hidden) is placed in its box, small, top-right;
; 4. Vizier ("Utopia Vizier") is shown, placed in its box, topmost;
; 5. the visible windows are written to <result.json>: vsl reads that file and decides PASS/FAIL, this script never does.
#Requires AutoHotkey v2.0
#SingleInstance Force
#NoTrayIcon
DllCall("SetThreadDpiAwarenessContext", "ptr", -4, "ptr")   ; per-monitor aware: pixels 1:1 with fast.py shot
SetTitleMatchMode("RegEx")
SetWinDelay(50)

if A_Args.Length < 1 || Trim(A_Args[1]) = "" {
    FileAppend("no demo url: nothing to lay out, no window touched`n", "*")
    ExitApp(0)
}
if A_Args.Length < 5 {
    FileAppend("usage: layout.ahk <demo-url> <obs-box> <vizier-box> <demo-box> <result.json>`n", "*")
    ExitApp(2)
}
url := A_Args[1], boxObs := A_Args[2], boxViz := A_Args[3], boxDemo := A_Args[4], resultPath := A_Args[5]
fixMode := A_Args.Length >= 6 && A_Args[6] = "fix"
CHROME := "C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE := "C:\vsl\chrome"
BROWSERS := "i)^(chrome|msedge|firefox|brave|opera|iexplore)\.exe$"
SHELL_CLS := "^(Shell_TrayWnd|Shell_SecondaryTrayWnd|Progman|WorkerW|NotifyIconOverflowWindow|Windows\.UI\.Core\.CoreWindow|XamlExplorerHostIslandWindow|TopLevelWindowForOverflowXamlIsland|Shell_InputSwitchTopLevelWindow|ForegroundStaging|Xaml_WindowedPopupClass|tooltips_class32|IME|MSCTFIME UI)$"
KEEP_EXE := "i)^(obs64|vizier|Moonlight|explorer|ShellExperienceHost|StartMenuExperienceHost|SearchHost|TextInputHost|LockApp|AutoHotkey64)\.exe$"
notes := []

; A window of the demo's own Chrome (profile PROFILE): its browser process carries --user-data-dir on its command line.
IsDemoProc(h) {
    static wmi := ComObjGet("winmgmts:"), seen := Map()
    global PROFILE
    p := WinGetPID(h)
    if !seen.Has(p) {
        cmd := ""
        for proc in wmi.ExecQuery("Select CommandLine from Win32_Process where ProcessId=" p)
            cmd := proc.CommandLine
        seen[p] := InStr(cmd, PROFILE) > 0
    }
    return seen[p]
}

MonitorGetWorkArea(MonitorGetPrimary(), &waL, &waT, &waR, &waB)
waW := waR - waL, waH := waB - waT

Box(spec) {
    global waL, waT, waW, waH
    p := StrSplit(spec, ",")
    return [Round(waL + p[1] * waW), Round(waT + p[2] * waH), Round(p[3] * waW), Round(p[4] * waH)]
}

; A real window on screen: visible, titled, not a tool window, not cloaked (hidden UWP frames report visible).
IsReal(h) {
    if !DllCall("IsWindowVisible", "ptr", h)
        return false
    if WinGetTitle(h) = ""
        return false
    if WinGetExStyle(h) & 0x80          ; WS_EX_TOOLWINDOW
        return false
    cloaked := 0
    DllCall("dwmapi\DwmGetWindowAttribute", "ptr", h, "uint", 14, "int*", &cloaked, "uint", 4)
    return !cloaked
}

; 1. strays (fix mode: the first demo-profile window from the top is kept as the demo)
DetectHiddenWindows(false)
demo := 0
for h in WinGetList() {
    try {
        if !IsReal(h) || WinGetMinMax(h) = -1
            continue
        cls := WinGetClass(h), exe := WinGetProcessName(h), title := WinGetTitle(h)
        if cls ~= SHELL_CLS || (exe ~= KEEP_EXE && cls != "CabinetWClass")   ; a File Explorer window is a stray
            continue
        if fixMode && !demo && exe = "chrome.exe" && IsDemoProc(h) {
            demo := h
            notes.Push("kept demo window '" title "'")
            continue
        }
        if exe ~= BROWSERS {
            WinClose(h)
            notes.Push("closed " exe " '" title "'")
        } else {
            WinMinimize(h)
            notes.Push("minimized " exe " '" title "'")
        }
    }
}
; a browser that ignored WM_CLOSE (a beforeunload prompt) is minimized instead, so it is not on screen either
Sleep(800)
for h in WinGetList() {
    try {
        if h != demo && IsReal(h) && WinGetMinMax(h) != -1 && WinGetProcessName(h) ~= BROWSERS {
            WinMinimize(h)
            notes.Push("minimized (did not close) " WinGetProcessName(h) " '" WinGetTitle(h) "'")
        }
    }
}

; 2. the demo: one chromeless app window in its own profile
b := Box(boxDemo)
DirCreate(PROFILE)
if !demo
    Run('"' CHROME '" --user-data-dir="' PROFILE '" --no-first-run --no-default-browser-check --new-window --app="' url '" --window-position=' b[1] ',' b[2] ' --window-size=' b[3] ',' b[4])
loop (demo ? 0 : 80) {                      ; up to 20 s for the window
    for h in WinGetList("ahk_exe chrome.exe ahk_class Chrome_WidgetWin_1") {
        try {
            if IsReal(h) && WinGetMinMax(h) != -1 {
                demo := h
                break
            }
        }
    }
    if demo
        break
    Sleep(250)
}
if demo {
    WinRestore(demo), WinMove(b[1], b[2], b[3], b[4], demo)
    notes.Push("demo window '" WinGetTitle(demo) "' placed")
} else
    notes.Push("demo window did not appear in 20 s")

; 3. OBS (in the tray when obs-keep started it: shown first)
DetectHiddenWindows(true)
b := Box(boxObs)
obs := WinExist("^OBS \d ahk_exe obs64.exe")
if obs {
    WinShow(obs), WinRestore(obs), WinMove(b[1], b[2], b[3], b[4], obs)
    notes.Push("OBS placed")
} else
    notes.Push("OBS window not found")

; 4. Vizier, topmost
b := Box(boxViz)
viz := WinExist("^Utopia Vizier$ ahk_exe vizier.exe")
if viz {
    WinShow(viz), WinRestore(viz), WinMove(b[1], b[2], b[3], b[4], viz), WinSetAlwaysOnTop(1, viz)
    notes.Push("Vizier placed, topmost")
} else
    notes.Push("Vizier window not found")
DetectHiddenWindows(false)
if demo
    try WinActivate(demo)
; Moonlight is the picture `vsl start` needs: restored and raised if a previous prep or a person left it minimized
DetectHiddenWindows(false)
moon := WinExist("ahk_exe Moonlight.exe ahk_class SDL_app")
if moon {
    try {
        WinRestore(moon)
        WinActivate(moon)
        notes.Push("Moonlight raised")
    }
}
Sleep(600)

; 5. what is on screen now -> JSON
Esc(s) {
    s := StrReplace(s, "\", "\\"), s := StrReplace(s, '"', '\"')
    s := StrReplace(s, "`n", " "), s := StrReplace(s, "`r", " "), s := StrReplace(s, "`t", " ")
    return s
}
vis := ""
for h in WinGetList() {
    try {
        if !IsReal(h) || WinGetMinMax(h) = -1
            continue
        cls := WinGetClass(h)
        if cls ~= SHELL_CLS
            continue
        WinGetPos(&x, &y, &w, &hh, h)
        vis .= (vis = "" ? "" : ",") '{"exe":"' Esc(WinGetProcessName(h)) '","title":"' Esc(WinGetTitle(h)) '","class":"' Esc(cls)
            . '","x":' x ',"y":' y ',"w":' w ',"h":' hh ',"demo":' (h = demo ? "true" : "false") '}'
    }
}
logs := ""
for l in notes
    logs .= (logs = "" ? "" : ",") '"' Esc(l) '"'
out := '{"work_area":[' waL ',' waT ',' waW ',' waH '],"demo_title":"' (demo ? Esc(WinGetTitle(demo)) : "") '","visible":[' vis '],"notes":[' logs ']}'
try FileDelete(resultPath)
FileAppend(out, resultPath, "UTF-8-RAW")
ExitApp(0)
