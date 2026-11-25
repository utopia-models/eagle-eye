"""eeconf.py: per-deployment config, read from the private overlay (utopia-models/eagle-eye-utopia).

The overlay is checked out at $EE_CONFIG (default /srv/eagle-eye/config); `config.json` there holds every value that
names a person, an address or a mailbox. Core never carries them: `get("sender_email", "you@example.com")`.
"""
import json
import os

CONFIG_DIR = os.environ.get("EE_CONFIG", "/srv/eagle-eye/config")
_cache = None


def load() -> dict:
    global _cache
    if _cache is None:
        try:
            with open(os.path.join(CONFIG_DIR, "config.json")) as f:
                _cache = json.load(f)
        except (OSError, ValueError):
            _cache = {}
    return _cache


def get(key: str, default=None):
    return os.environ.get("EE_" + key.upper(), load().get(key, default))
