#!/usr/bin/env python3
"""Helper for the sync-gpx skill. Keeps gpx/ in step with the Google Drive folder.

File content never passes through the model: the repo's .claude/settings.json caps MCP
results at 1000 tokens, so Claude Code saves every Drive result (listings and downloads)
to a file, and this script reads those files.

Run from the repo root: `python3 -I .claude/skills/sync-gpx/gpxsync.py <command>`

  preflight         Exit 1 unless the low MCP output cap is active in this session.
  diff LISTING...   LISTING = saved Drive search results (JSON with "files").
                    Prints missing files as "<fileId> <title>", plus local-only files.
                    Remembers Drive file sizes for `save` to verify against.
  save RESULT...    RESULT = saved Drive download (JSON with title + base64 content).
                    Verifies size and GPX validity, never overwrites, rebuilds the manifest.
  manifest          Rewrites gpx/index.json (the list the map loads).
  status            Counts files and reports byte-identical duplicates.
"""
import base64
import hashlib
import json
import os
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

GPX_DIR = Path("gpx")
SIZES = Path(tempfile.gettempdir()) / "sync-gpx-drive-sizes.json"
MAX_CAP = 2000


def cmd_preflight():
    cap = os.environ.get("MAX_MCP_OUTPUT_TOKENS", "")
    if cap.isdigit() and int(cap) <= MAX_CAP:
        print(f"ok: MAX_MCP_OUTPUT_TOKENS={cap}")
        return 0
    print(f"NOT ACTIVE: MAX_MCP_OUTPUT_TOKENS={cap or '(unset)'}. Downloads could come back inline.")
    print("Start a new Claude Code session from the repo root so .claude/settings.json applies.")
    return 1


def safe_name(title):
    name = Path(title).name
    if name != title or not name.lower().endswith(".gpx") or name.startswith("."):
        raise SystemExit(f"refusing unsafe file name: {title!r}")
    return name


def local_files():
    return sorted(p.name for p in GPX_DIR.glob("*.gpx")) if GPX_DIR.exists() else []


def cmd_diff(paths):
    drive = {}
    pages_with_more = 0
    for p in paths:
        page = json.loads(Path(p).read_text())
        if page.get("nextPageToken"):
            pages_with_more += 1
        for f in page.get("files", []):
            if f.get("title", "").lower().endswith(".gpx"):
                drive[f["title"]] = f
    if pages_with_more == len(paths):
        print("WARNING: every page given has a nextPageToken; the listing is incomplete.")
    SIZES.write_text(json.dumps({t: f.get("fileSize") for t, f in drive.items()}))

    local = set(local_files())
    missing = sorted(t for t in drive if t not in local)
    orphans = sorted(local - drive.keys())
    print(f"drive: {len(drive)}  local: {len(local)}")
    print(f"missing locally: {len(missing)}")
    for t in missing:
        print(f"  {drive[t]['id']} {t}")
    print(f"local only (not on Drive): {len(orphans)}")
    for t in orphans:
        print(f"  {t}")
    return 0


def cmd_save(paths):
    sizes = json.loads(SIZES.read_text()) if SIZES.exists() else {}
    failed = 0
    for p in paths:
        d = json.loads(Path(p).read_text())
        name = safe_name(d["title"])
        data = base64.b64decode(d["content"])
        target = GPX_DIR / name
        if target.exists():
            print(f"skip (exists): {name}")
            continue
        expected = sizes.get(name)
        if expected is not None and int(expected) != len(data):
            print(f"SIZE MISMATCH, not saved: {name} ({len(data)} bytes, Drive says {expected})")
            failed += 1
            continue
        try:
            root = ET.fromstring(data)
            if not root.tag.endswith("gpx"):
                raise ValueError("root element is not <gpx>")
        except (ET.ParseError, ValueError) as err:
            print(f"INVALID, not saved: {name}: {err}")
            failed += 1
            continue
        GPX_DIR.mkdir(exist_ok=True)
        target.write_bytes(data)
        print(f"saved: {name} ({len(data)} bytes)")
    cmd_manifest()
    return 1 if failed else 0


def cmd_manifest():
    files = local_files()
    GPX_DIR.mkdir(exist_ok=True)
    (GPX_DIR / "index.json").write_text(json.dumps(files, indent=1, ensure_ascii=False) + "\n")
    print(f"manifest: {len(files)} files in gpx/index.json")
    return 0


def cmd_status():
    by_hash = {}
    files = local_files()
    for name in files:
        by_hash.setdefault(hashlib.sha256((GPX_DIR / name).read_bytes()).hexdigest(), []).append(name)
    dupes = [names for names in by_hash.values() if len(names) > 1]
    print(f"{len(files)} GPX files, {len(dupes)} duplicate group(s)")
    for names in dupes:
        print("  identical: " + ", ".join(names))
    return 0


def main(argv):
    cmd, args = (argv[0], argv[1:]) if argv else ("", [])
    if cmd == "preflight" and not args:
        return cmd_preflight()
    if cmd == "diff" and args:
        return cmd_diff(args)
    if cmd == "save" and args:
        return cmd_save(args)
    if cmd == "manifest" and not args:
        return cmd_manifest()
    if cmd == "status" and not args:
        return cmd_status()
    raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
