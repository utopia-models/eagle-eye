# packages/toolkit

What every System shares. Python standard library only.

| file | does |
|---|---|
| `kit.py` | resolves `kit:` and `lib:` citation ids; honours `EE_KIT` and `EE_KIT_OVERLAY` |
| `systems.py` | loads and checks `systems/<id>/system.json` |
| `quote_check.py` | fails the build when a quoted line is not in its cited file |
| `onboard.py` | zero-touch onboarding: read the business, pick the System and basis, run it |
| `rails.py` | the hook outward stages pass through (which rails are fixed is still open) |

```bash
python3 packages/toolkit/quote_check.py
python3 packages/toolkit/onboard.py --dir ~/my-business                    # the AI picks system and basis
python3 packages/toolkit/onboard.py --dir ~/my-business --basis hormozi    # "run it like Hormozi"
python3 -m pytest packages/toolkit/tests
```
