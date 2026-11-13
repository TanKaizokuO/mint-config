#!/usr/bin/env python3
# Refresh ~/.cache/usage/omp.json from `omp usage --json` (Codex and agy quotas, account level).
# Run by usage-fetch.timer; usage.py only reads the cache so the bar never waits on the network.
import json
import os
import subprocess
import time

CACHE = os.path.expanduser("~/.cache/usage/omp.json")
KEY = {"5h": "five", "7d": "seven", "weekly": "seven"}


def pick(limits, label=None):
    out = {}
    for lim in limits:
        key = KEY.get(lim["window"]["id"])
        if not key or (label and lim["label"] != label):
            continue
        amt = lim["amount"]
        if amt.get("remaining") is None:
            continue
        out.setdefault(key, {"left": amt["remaining"], "resets_at": lim["window"].get("resetsAt", 0) / 1000})
    return out


def main():
    res = subprocess.run(["omp", "usage", "--json"], capture_output=True, text=True, timeout=90)
    reports = {r["provider"]: r for r in json.loads(res.stdout)["reports"]}
    data = {"updated": time.time()}
    if "openai-codex" in reports:
        data["codex"] = pick(reports["openai-codex"]["limits"])
        data["codex_at"] = reports["openai-codex"]["fetchedAt"] / 1000
    if "google-antigravity" in reports:
        data["agy"] = pick(reports["google-antigravity"]["limits"], "Gemini")
        data["agy_at"] = reports["google-antigravity"]["fetchedAt"] / 1000
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    tmp = CACHE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, CACHE)


if __name__ == "__main__":
    main()
