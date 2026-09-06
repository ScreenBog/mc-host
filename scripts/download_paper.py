"""Download the latest stable Paper build into runtime/paper-server.jar."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "runtime" / "paper-server.jar"
UA = "shnenepepe-hosting/1.0.0 (https://shnenepepe.online)"


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def main() -> None:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    if DEST.exists() and DEST.stat().st_size > 1_000_000:
        print(f"already have {DEST} ({DEST.stat().st_size} bytes)")
        return
    versions = json.loads(get("https://fill.papermc.io/v3/projects/paper"))
    # versions["versions"] is { "26.2": [...], "1.21.11": [...] } — pick first family
    family = next(iter(versions.get("versions") or {"26.2": []}))
    builds = json.loads(
        get(f"https://fill.papermc.io/v3/projects/paper/versions/{family}/builds")
    )
    if isinstance(builds, dict) and "builds" in builds:
        items = builds["builds"]
    elif isinstance(builds, list):
        items = builds
    else:
        raise SystemExit(f"unexpected builds payload: {str(builds)[:400]}")
    stable = None
    for item in reversed(items):
        channel = (item.get("channel") or item.get("build_channel") or "").upper()
        downloads = item.get("downloads") or {}
        default = downloads.get("server:default") or downloads.get("application") or {}
        url = default.get("url")
        if url and (channel in {"", "STABLE", "RECOMMENDED"} or stable is None):
            stable = url
            if channel == "STABLE":
                break
    if not stable:
        raise SystemExit("no paper download url")
    print(f"version family {family}")
    print(f"downloading {stable}")
    req = urllib.request.Request(stable, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as resp, DEST.open("wb") as fh:
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            fh.write(chunk)
    print(f"saved {DEST} ({DEST.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
