#!/usr/bin/env python3
"""Helper for the sync-gpx skill. Keeps gpx/ in step with the Google Drive folder.

Run from the repo root with `python3 -I .claude/skills/sync-gpx/gpxsync.py <command>`.

  diff LISTING      LISTING has one Drive file per line: "<fileId> <title>".
                    Prints files missing locally (as "<fileId> <title>") and
                    local files that are not on Drive.
  save RESULT...    RESULT is a saved Drive download (JSON with title + base64
                    content). Validates it as GPX and writes it into gpx/.
  save-b64 TITLE B64FILE
                    Same, for a small download that came back inline: put the
                    base64 content string in B64FILE.
  manifest          Rewrites gpx/index.json (the list the map loads).
  status            Counts files and reports byte-identical duplicates.
"""
import base64
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

GPX_DIR = Path("gpx")


def safe_name(title):
    name = Path(title).name
    if name != title or not name.lower().endswith(".gpx") or name.startswith("."):
        raise SystemExit(f"refusing unsafe file name: {title!r}")
    return name


def track_points(data):
    root = ET.fromstring(data)
    if not root.tag.endswith("gpx"):
        raise ValueError("root element is not <gpx>")
    return sum(1 for e in root.iter() if e.tag.endswith(("trkpt", "rtept")))


def write_gpx(title, data):
    name = safe_name(title)
    target = GPX_DIR / name
    if target.exists():
        print(f"skip (exists): {name}")
        return
    try:
        points = track_points(data)
    except (ET.ParseError, ValueError) as err:
        print(f"INVALID, not saved: {name}: {err}")
        return
    GPX_DIR.mkdir(exist_ok=True)
    target.write_bytes(data)
    print(f"saved: {name} ({len(data)} bytes, {points} points)")


def local_files():
    return sorted(p.name for p in GPX_DIR.glob("*.gpx")) if GPX_DIR.exists() else []


def cmd_diff(listing):
    drive = {}
    for line in Path(listing).read_text().splitlines():
        line = line.strip()
        if line:
            file_id, _, title = line.partition(" ")
            drive[title.strip()] = file_id
    local = set(local_files())
    missing = sorted(t for t in drive if t not in local)
    orphans = sorted(local - drive.keys())
    print(f"drive: {len(drive)}  local: {len(local)}")
    print(f"missing locally: {len(missing)}")
    for t in missing:
        print(f"  {drive[t]} {t}")
    print(f"local only (not on Drive): {len(orphans)}")
    for t in orphans:
        print(f"  {t}")


def cmd_save(paths):
    for p in paths:
        d = json.loads(Path(p).read_text())
        write_gpx(d["title"], base64.b64decode(d["content"]))
    cmd_manifest()


def cmd_save_b64(title, b64file):
    write_gpx(title, base64.b64decode(Path(b64file).read_text().strip()))
    cmd_manifest()


def cmd_manifest():
    files = local_files()
    GPX_DIR.mkdir(exist_ok=True)
    (GPX_DIR / "index.json").write_text(json.dumps(files, indent=1, ensure_ascii=False) + "\n")
    print(f"manifest: {len(files)} files in gpx/index.json")


def cmd_status():
    files = local_files()
    by_hash = {}
    for name in files:
        by_hash.setdefault(hashlib.sha256((GPX_DIR / name).read_bytes()).hexdigest(), []).append(name)
    dupes = [names for names in by_hash.values() if len(names) > 1]
    print(f"{len(files)} GPX files, {len(dupes)} duplicate group(s)")
    for names in dupes:
        print("  identical: " + ", ".join(names))


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    cmd, args = argv[0], argv[1:]
    if cmd == "diff" and len(args) == 1:
        cmd_diff(args[0])
    elif cmd == "save" and args:
        cmd_save(args)
    elif cmd == "save-b64" and len(args) == 2:
        cmd_save_b64(*args)
    elif cmd == "manifest" and not args:
        cmd_manifest()
    elif cmd == "status" and not args:
        cmd_status()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
