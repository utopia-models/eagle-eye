#!/usr/bin/env python3
"""No Eagle Eye page shows an "updated" / "measured ... ago" stamp (knowledge#14539, Tyler 2026-11-14: "I don't like this
whole updated 12:27 a.m. Could we just like not?"). Staleness is the board's alarm, never a page stamp.

    python3 packages/core/test_no_updated_stamp.py [extra-file ...]      # extra files: e.g. the live page, saved
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BAD = [r"Measured \$\{", r"Measured ' \+", r"Feed updated", r"refreshed every 30 seconds", r"Read from the upwork agent's ledger and proposals\.db \$\{",
       r"`feed \$\{ago\(D\.updated\)\}`", r'"Measured "']


def test_no_stamp(paths):
    for p in paths:
        s = open(p).read()
        for b in BAD:
            assert not re.search(b, s), f"{p}: still has {b}"


if __name__ == "__main__":
    test_no_stamp([os.path.join(HERE, f) for f in ("lane.html", "lane_pages.py", "apps.html", "jobs-app/src/AppsPage.tsx")] + sys.argv[1:])
    print("ok")
