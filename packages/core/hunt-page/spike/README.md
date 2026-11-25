# eagle-eye-spike

Agents: after ANY UI change, run `~/.local/share/fleet-playwright/bin/python tools/layout-check.py` (feed + detail at 1440/1280/390; exit 1 on any overlapping chip/text box, row spill or console error) and do not ship until it prints PASS.
