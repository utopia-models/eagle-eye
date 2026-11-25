#!/usr/bin/env python3
"""Per-job MVP stack decision (knowledge#18941): classify the post, pick stack/template/screens by the rubric,
write decision.json ('why this stack for this job') next to the MVP.
  vsl_stack_decide.py POST.md OUT_DIR   |   --selftest
Classification is keyword-scored against the post text; the agent may override with --type after reasoning."""
import json, os, re, sys, argparse
KIT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mvp-kit")
KW = {
 "dashboard-analytics": r"dashboard|analytics|report|metric|kpi|chart|insight",
 "crm-pipeline": r"crm|pipeline|lead|sales|deal|contact|follow.?up",
 "ai-chat-agent": r"chatbot|\bchat\b|assistant|\bllm\b|\bgpt\b|ai agent|copilot|rag",
 "marketplace": r"marketplace|listing|vendor|seller|buyer|storefront",
 "internal-tool": r"internal|admin|back.?office|ops|inventory|scheduling|portal",
 "mobile-app": r"mobile app|ios|android|react native|flutter",
 "voice-agent": r"voice|call|phone agent|speech|transcri",
 "data-pipeline": r"pipeline|etl|scrap|ingest|sync|integration|webhook",
}
SCREENS = {"dashboard-analytics": ["Overview KPIs", "Trend charts", "Breakdown table", "Detail drawer"],
 "crm-pipeline": ["Pipeline board", "Contact list", "Contact detail", "Activity feed"],
 "ai-chat-agent": ["Chat with streaming", "Sources panel", "History", "Settings"],
 "marketplace": ["Browse grid", "Listing detail", "Seller dashboard", "Orders"],
 "internal-tool": ["Queue table", "Record detail", "Cmd+K search", "Reports"],
 "mobile-app": ["Home", "Detail", "Activity", "Profile"],
 "voice-agent": ["Live call", "Transcript", "Call log", "Analytics"],
 "data-pipeline": ["Runs table", "Run detail", "Throughput chart", "Alerts"]}
def classify(text):
    t = text.lower(); s = {k: len(re.findall(p, t)) for k, p in KW.items()}
    best = max(s, key=lambda k: s[k]); return (best if s[best] else "internal-tool"), s
def decide(text, typ=None):
    rub = json.load(open(os.path.join(KIT, "rubric.json")))
    c, scores = classify(text); c = typ or c; r = rub[c]
    pats = json.load(open(os.path.join(KIT, "motion", "patterns.json")))
    motion = ["stagger_rows", "kpi_countup", "skeleton_swap", "toast_per_action", "live_status"]
    if c in ("dashboard-analytics", "data-pipeline"): motion.append("chart_draw")
    if c == "ai-chat-agent": motion.append("ai_stream")
    if "cmdk" in r["extra"]: motion.append("cmdk_palette")
    motion = [m for m in dict.fromkeys(motion) if m in pats]
    return {"product_type": c, "scores": scores, "stack": r["stack"], "template": r["template"], "extra": r["extra"],
            "screens": SCREENS[c], "motion_patterns": motion,
            "why": f"Post reads as '{c}' (keyword score {scores[c]}); rubric maps that to {r['stack']} on {r['template']}."}
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("post", nargs="?"); ap.add_argument("out", nargs="?")
    ap.add_argument("--type"); ap.add_argument("--selftest", action="store_true"); a = ap.parse_args()
    if a.selftest:
        d1 = decide("Need a dashboard with charts and KPI reports"); d2 = decide("Build an AI chatbot assistant using GPT")
        assert d1["stack"] != d2["stack"] and len(d1["screens"]) in range(3, 6) and len(d1["motion_patterns"]) >= 4
        assert decide("x")["product_type"] == "internal-tool"; print("selftest ok"); return
    d = decide(open(a.post).read(), a.type); os.makedirs(a.out, exist_ok=True)
    json.dump(d, open(os.path.join(a.out, "decision.json"), "w"), indent=2); print(json.dumps(d, indent=2))
if __name__ == "__main__": main()
