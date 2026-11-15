# The feed

Eagle Eye polls one JSON document every 5 seconds (`feed` in `config.js`). Anything that can write this shape can
drive the screen: a cron job, a serverless function, a database view. `adapters/csv_feed.py` is the reference adapter.

```jsonc
{
  "updated": "2026-11-15T09:00:00Z",          // when your adapter measured it
  // the live lane's funnel: every key named in config.js `stages` and `key4`, as top-level numbers
  "applied": 214, "replied": 31, "interviews": 7, "offers": 2,
  "hunts": {                                   // one entry per ring-0 lane, keyed by the lane's `hk`
    "job_boards": {
      "sent": 214,                             // what you sent out (outer glyph ring)
      "answered": 31,                          // what came back (inner glyph ring)
      "status": "live",                        // live | partial | empty
      "reason": "...",                         // shown instead of numbers when status is empty (say WHY)
      "window": "last 30 days", "what": "...", "source": "...",   // shown in the lane's sheet
      "last_action": {"ts": "2026-11-15T08:41:00Z", "event": "applied"}   // freshness line
    }
  },
  "roosts": {                                  // one entry per ring-1 lane, keyed by the lane's `rk`
    "clients": {
      "rows": [{"name": "Northwind Labs", "hunt": "referrals", "stage": "contract", "contracts": 1, "paid": "$4,800"}],
      "reason": "..."                          // shown when rows is empty
    }
  }
}
```

Rules the UI keeps, so your adapter should too:

- **Never send a zero you did not count.** A lane you cannot measure gets `"sent": null, "status": "empty"` and a
  `reason`; the screen shows the reason, dimmed, instead of a fake 0.
- **A failed measurement writes nothing.** Keep the last good document rather than replacing it with an empty one.
