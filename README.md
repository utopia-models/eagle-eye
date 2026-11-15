# Eagle Eye

One screen for every outreach pipeline you run. Your **hunts** (what you send out: applications, proposals, cold
email, LinkedIn, events) sit on the eye's outer ring. Your **roosts** (what comes back: clients, your network) sit
on the inner ring. The busiest lane gets a live funnel card. It reads one JSON feed and redraws every 5 seconds.

It fits whatever screen it is on, with no scroll bar: a phone, a laptop, a 1080p wall, an ultrawide, or half of a
desk. Wide screens put HUNTS and ROOSTS in large side panels with the eye between them. Narrow ones stack the lanes,
the eye, then the card.

![Eagle Eye at 1920x1080 on the demo feed](docs/eagle-eye-1920.png)

## Run it on the demo feed

No build, no dependencies, no account:

```bash
git clone https://github.com/utopia-models/eagle-eye && cd eagle-eye
python3 -m http.server 8000      # or: npx serve .
# open http://localhost:8000
```

Everything you see comes from `demo/data.json`, which is made-up sample data.

## Plug in your own pipeline

1. Write a feed in the shape in [`docs/FEED.md`](docs/FEED.md). The reference adapter turns a CSV ledger (one row per
   application or status change) into a feed:
   ```bash
   python3 adapters/csv_feed.py my-ledger.csv > data.json
   ```
2. Point `feed` in [`config.js`](config.js) at it, and name your lanes in `pipes`.
3. Re-run the adapter on a schedule (cron, a systemd timer, a serverless function). The page picks up changes
   within 5 seconds, with no reload.

Any adapter that writes the same JSON works: a CRM export, an ATS API, an inbox count.

## Check the layout

```bash
npm i && npx playwright install chromium webkit firefox
python3 -m http.server 8000 &
npm run check     # 6 sizes x 3 browsers: fails on any overlap, anything off screen, or a scroll bar
```

## Where it comes from

Eagle Eye is the outreach cockpit Utopia Models runs for its own job search and agency work, released with the
UI and a demo feed only. No real data and no credentials ship in this repository.

Licensed under the [Apache License 2.0](LICENSE). Made by [Utopia Models, Inc.](https://utopiamodels.ai)
