#!/usr/bin/env python3
"""Eagle Eye hunt page, Tyler 2026-11-24 (asks 3577, 3578; knowledge#18662, shipped in #18653):
  3577 "when a proposal is sent I want a link to the proposal" -> the Sent stage and the sent rows carry the Upwork proposal link.
  3578 "remove this record component" -> the Record button is gone (markup + css); the stage track's "Recorded" step stays.

    python3 packages/core/test_proposal_link_no_record_button.py
"""
import os
import re

UI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hunt-page", "ui")


def read(p):
    return open(os.path.join(UI, p)).read()


def test_proposal_link():
    d = read("opt/detail.js")
    assert "https://www.upwork.com/nx/proposals/" in d, "no proposal URL"
    assert 'x.k === "sent" ? propLink(' in d, "Sent stage lost its proposal link"
    assert "propLink(s.proposal_id)" in d, "sent rows lost their proposal link"


def test_no_record_button():
    for p in ("index.html", "opt/detail.js", "opt/shared.js"):
        s = read(p)
        assert not re.search(r"<button[^>]*>\s*Record\s*</button>", s), f"{p}: Record button is back"
        assert not re.search(r"data-(vsl-)?record\b", s), f"{p}: record hook is back"


if __name__ == "__main__":
    test_proposal_link()
    test_no_record_button()
    print("ok")
