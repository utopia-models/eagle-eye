#!/usr/bin/env python3
"""Tests for network_here.py (company matching + the people join). Offline, stdlib only.

    python3 packages/core/test_network_here.py      # or: python3 -m pytest test_network_here.py
"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def load():
    """feed.py's definitions + network_here.py in one namespace, the way apps-push.py concatenates them."""
    feed = open(os.path.join(HERE, "feed.py")).read()
    feed = feed[:feed.rindex('if __name__ == "__main__":')]
    ns = {"__name__": "network_here_test"}
    exec(compile(feed + "\n" + open(os.path.join(HERE, "network_here.py")).read(), "network_here", "exec"), ns)  # noqa: S102
    return ns


N = load()


class CompanyKeys(unittest.TestCase):
    def same(self, a, b):
        self.assertTrue(N["company_keys"](a) & N["company_keys"](b), f"{a!r} and {b!r} should be one company")

    def test_legal_suffixes_are_one_company(self):
        self.same("Spotnana", "Spotnana Inc.")
        self.same("Spotnana", "Spotnana, Inc")
        self.same("Spotnana Technology", "spotnana")
        self.same("SalesBlaster.ai", "SalesBlaster")
        self.same("Anduril Industries", "Anduril")
        self.same("The Voleon Group", "Voleon")
        self.same("Kratos Defense & Security Solutions", "Kratos")

    def test_different_companies_stay_apart(self):
        k = N["company_keys"]
        self.assertFalse(k("Meta") & k("Metabase"))
        self.assertFalse(k("Scale AI") & k("Scaleway"))
        self.assertFalse(k("Ramp") & k("Rampart"))
        self.assertFalse(k("Capital One") & k("Capital Group"))
        self.assertFalse(k("General Motors") & k("General Dynamics"))

    def test_domain_and_board_slugs(self):
        ds = N["domain_stem"]
        self.assertEqual(ds("max@salesblaster.example"), "salesblaster")
        self.assertEqual(ds("https://careers.spotnana.com/jobs/123"), "spotnana")
        self.assertEqual(ds("https://spotnana.wd1.myworkdayjobs.com/en-US/careers/job/x"), "spotnana")
        self.assertEqual(ds("https://boards.greenhouse.io/spotnana/jobs/4012"), "spotnana")
        self.assertEqual(ds("https://job-boards.greenhouse.io/spotnana/jobs/4012"), "spotnana")
        self.assertEqual(ds("https://jobs.lever.co/anduril/abc"), "anduril")
        self.assertEqual(ds("https://jobs.ashbyhq.com/ramp/xyz"), "ramp")
        self.assertEqual(ds("https://www.example.co.uk/about"), "example")

    def test_freemail_and_aggregators_name_no_company(self):
        ds = N["domain_stem"]
        for v in ("someone@gmail.example", "a@yahoo.example", "x@icloud.example", "https://www.linkedin.com/jobs/view/1",
                  "https://www.indeed.com/viewjob?jk=1", "https://boards.greenhouse.io/", ""):
            self.assertIsNone(ds(v), v)

    def test_name_and_domain_join(self):
        k = N["company_keys"]
        self.assertTrue(k("Spotnana") & k(None, "https://spotnana.wd5.myworkdayjobs.com/x"))
        self.assertTrue(k("Spotnana Inc.", "https://boards.greenhouse.io/spotnana") & k("", "jane@spotnana.example"))

    def test_placeholders_are_not_employers(self):
        self.assertEqual(N["company_keys"]("Personal network"), set())
        self.assertEqual(N["company_keys"]("Test fixtures"), set())

    def test_split_company_past(self):
        sc = N["split_company"]
        self.assertEqual(sc("PNC (previous)"), ("PNC", True))
        self.assertEqual(sc("Transurban (previous)"), ("Transurban", True))
        self.assertEqual(sc("Ex-Google"), ("Google", True))
        self.assertEqual(sc("Kratos"), ("Kratos", False))


class Headlines(unittest.TestCase):
    def test_headline_names_the_company(self):
        h = N["headline_names"]
        keys = N["company_keys"]("Spotnana")
        self.assertEqual(h("Backend Engineer at Spotnana | Columbia University", "Spotnana", keys), "current")
        self.assertEqual(h("Product @ Spotnana", "Spotnana", keys), "current")
        self.assertEqual(h("SWE @Spotnana | Ex-HFT | Backend Systems", "Spotnana", keys), "current")
        self.assertEqual(h("Ex-Spotnana | Staff Engineer at Stripe", "Spotnana", keys), "past")
        self.assertEqual(h("formerly at Spotnana, now building", "Spotnana", keys), "past")
        self.assertIsNone(h("Software Engineer x Former Financial Consultant", "Spotnana", keys))
        self.assertIsNone(h("Helping to build great software and companies", "Spotnana", keys))

    def test_short_keys_need_a_whole_word(self):
        h = N["headline_names"]
        keys = N["company_keys"]("F5")
        self.assertIsNone(h("Head of Fintech F500 sales", "F5", keys))


class Join(unittest.TestCase):
    ROSTER = [
        {"name": "Ada Park", "company": "Spotnana Inc.", "title": "Staff Engineer", "emails": []},
        {"name": "Bo Lee", "company": "", "title": "", "emails": ["bo@spotnana.example"]},
        {"name": "Cy Old", "company": "Spotnana (previous)", "title": "PM", "emails": []},
        {"name": "Di Other", "company": "Stripe", "title": "EM", "emails": ["di@gmail.example"]},
        {"name": "Personal Contact", "company": "Personal network", "title": "Contact · Tyler handles himself", "emails": []},
    ]
    CRM = [{"name": "Ada Park", "title": "", "company": "Spotnana", "domain": "https://spotnana.com", "emails": [], "owner": "tyler"}]
    LI = {"at": "2026-11-16T19:00:00Z", "state": "ok",
          "first": [{"name": "Ada Park", "headline": "Staff Engineer at Spotnana"},
                    {"name": "Eve New", "headline": "Recruiter @ Spotnana"},
                    {"name": "Fay Elsewhere", "headline": "Defense Tech & Intelligence"}],
          "second": [{"name": "Sanjay Sharma", "headline": "Backend Engineer at Spotnana | Columbia University",
                      "mutual": ["Jacob James"], "mutual_more": 0},
                     {"name": "Gus Gone", "headline": "Ex-Spotnana | now at Ramp", "mutual": ["Hal"], "mutual_more": 0},
                     {"name": "Mark Nelson", "headline": "Helping to build great software", "mutual": ["Daisy Vo"]},
                     {"name": "Ivy Many", "headline": "Product @ Spotnana", "mutual": ["Tom A", "Liz B"], "mutual_more": 7}]}

    def run_join(self, li=None):
        people = N["network_people"](self.ROSTER, self.CRM)
        return N["match_people"]("Spotnana", N["company_keys"]("Spotnana"), people, li)

    def test_works_there_from_crm(self):
        d = self.run_join()
        names = [w["n"] for w in d["works"]]
        self.assertEqual(names, ["Ada Park", "Bo Lee", "Cy Old"])   # current first, the past one last
        self.assertEqual(d["works"][0]["t"], "Staff Engineer")
        self.assertEqual(d["works"][2].get("past"), 1)
        self.assertEqual(d["wn"], 3)
        self.assertEqual(d["kn"], 0)

    def test_one_person_in_both_stores_is_one_row(self):
        people = N["network_people"](self.ROSTER, self.CRM)
        self.assertEqual(sum(p["name"] == "Ada Park" for p in people), 1)

    def test_linkedin_first_and_second_degree(self):
        d = self.run_join(self.LI)
        by = {w["n"]: w for w in d["works"]}
        self.assertEqual(by["Ada Park"]["via"], "CRM · LinkedIn")
        self.assertEqual(by["Eve New"]["via"], "LinkedIn")
        self.assertNotIn("Fay Elsewhere", by)                       # headline never names the company
        self.assertEqual([k["n"] for k in d["knows"]], ["Sanjay Sharma", "Ivy Many"])
        self.assertEqual(d["knows"][0]["c"], ["Jacob James"])
        self.assertEqual(d["knows"][1]["cm"], 7)
        self.assertEqual(d["kn"], 2)
        self.assertEqual(d["knows"][0]["t"], "Backend Engineer at Spotnana")   # the job part of the headline

    def test_summary_line_names_the_company(self):
        li = {"at": "x", "state": "ok", "first": [], "second": [
            {"name": "Yizhou Zhang", "headline": "Software Engineer x Former Financial Consultant",
             "summary": "Software Engineer at Spotnana since June 2025, with full-stack engineering", "mutual": ["Ethan Chung"]},
            {"name": "Mark T. Nelson [fi", "headline": "Helping to build great software and companies",
             "summary": "Board Member at Spotnana since September 2024, supporting the travel industry", "mutual": ["Daisy Vo"]},
            {"name": "Old Hand", "headline": "CTO at Ramp", "summary": "Previously at Spotnana for three years", "mutual": ["X Y"]}]}
        d = N["match_people"]("Spotnana", N["company_keys"]("Spotnana"), [], li)
        self.assertEqual([(k["n"], k["t"], k["c"]) for k in d["knows"]],
                         [("Yizhou Zhang", "Software Engineer at Spotnana", ["Ethan Chung"]),
                          ("Mark T. Nelson", "Board Member at Spotnana", ["Daisy Vo"])])

    def test_unread_connector_still_counts(self):
        li = {"at": "x", "state": "ok", "first": [], "second": [
            {"name": "Tessa Crimmel", "headline": "Senior Talent Acquisition Specialist at Vultr", "mutual": [], "mutual_more": 1},
            {"name": "No Path", "headline": "Engineer at Vultr", "mutual": [], "mutual_more": 0}]}
        d = N["match_people"]("Vultr", N["company_keys"]("Vultr"), [], li)
        self.assertEqual([(k["n"], k["c"], k["cm"]) for k in d["knows"]], [("Tessa Crimmel", [], 1)])

    def test_a_different_company_gets_nobody(self):
        people = N["network_people"](self.ROSTER, self.CRM)
        d = N["match_people"]("Rampart", N["company_keys"]("Rampart"), people, None)
        self.assertEqual((d["wn"], d["kn"]), (0, 0))

    def test_network_at_caches_per_company(self):
        with tempfile.TemporaryDirectory() as t:
            N["NET_DIR"] = t
            N["_NET_INDEX"].clear()
            N["_NET_INDEX"]["people"] = N["network_people"](self.ROSTER, self.CRM)
            N["_NET_INDEX"]["status"] = "test"
            d = N["network_at"]("Spotnana Inc.")
            self.assertEqual(d["wn"], 3)
            self.assertTrue(os.path.exists(os.path.join(t, "at", "spotnana.json")))
            N["_NET_INDEX"]["people"] = []                          # cached: the index is not re-read within the day
            self.assertEqual(N["network_at"]("Spotnana")["wn"], 3)
            os.makedirs(os.path.join(t, "li"))
            import json
            with open(os.path.join(t, "li", "spotnana.json"), "w") as f:
                json.dump(self.LI, f)
            self.assertEqual(N["network_at"]("Spotnana")["kn"], 2)  # a newer LinkedIn lookup rebuilds the cache
            q = N["write_queue"]([("Spotnana", "spotnana", "2026-11-16T18:00:00Z", []),
                                  ("Ramp", "ramp", "2026-11-16T19:00:00Z", []), ("Company", "company", "2026-11-16", [])])
            with open(q) as f:
                self.assertEqual([r["k"] for r in json.load(f)["companies"]], ["ramp", "spotnana"])


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False).result.wasSuccessful() else 1)
