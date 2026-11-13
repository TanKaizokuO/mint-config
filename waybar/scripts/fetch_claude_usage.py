#!/usr/bin/env python3
# Refresh ~/.cache/usage/claude.json from Anthropic's OAuth usage endpoint, so the Claude pill updates with no session open.
# Run by claude-usage-fetch.timer. Read-only on credentials: never refreshes the token (Claude Code owns that).
# Same schema as statusline-command.sh writes; any failure leaves the last cache untouched.
import json
import os
import time
import urllib.request
from datetime import datetime

CACHE = os.path.expanduser("~/.cache/usage/claude.json")
CREDS = os.path.expanduser("~/.claude/.credentials.json")


def window(w):
    if not w or w.get("utilization") is None or not w.get("resets_at"):
        return None
    return {"used_percentage": w["utilization"], "resets_at": round(datetime.fromisoformat(w["resets_at"]).timestamp())}


def main():
    tok = json.load(open(CREDS))["claudeAiOauth"]
    if tok["expiresAt"] / 1000 < time.time():
        return
    req = urllib.request.Request(
        "https://api.anthropic.com/api/oauth/usage",
        headers={"Authorization": "Bearer " + tok["accessToken"], "anthropic-beta": "oauth-2025-04-20", "User-Agent": "claude-code/2.0"},
    )
    body = json.load(urllib.request.urlopen(req, timeout=15))
    five, seven = window(body.get("five_hour")), window(body.get("seven_day"))
    if not five or not seven:
        return
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    tmp = CACHE + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"updated": int(time.time()), "five_hour": five, "seven_day": seven}, f)
    os.replace(tmp, CACHE)


if __name__ == "__main__":
    main()
