---
name: sync-gpx
description: Sync hike GPX files from the owner's Google Drive folder "Vandreture gpx" into gpx/ for the hike map, then serve the map locally. Use when asked to sync, update, refresh or pull hikes/GPX/tracks, or before running the map on a fresh clone.
---

# Sync hikes from Google Drive

GPX tracks contain home locations and timestamps, so they are **never committed**.
Google Drive is the only source of truth; `gpx/` is a local, git-ignored cache.
Access comes from the session's Google Drive connector — there are no keys or tokens in this repo.

Drive folder: **Vandreture gpx**, id `1986o0uX2Dzm1krxZ7UpDhcTWI5Kztmyw`.

All commands run from the repo root. Helper: `python3 -I .claude/skills/sync-gpx/gpxsync.py`
(called `gpxsync` below). Put scratch files in the session scratchpad or a temp dir, not in the repo.

## 1. Check the Drive connector

You need Google Drive tools (search files, download file content). If they are deferred, load them.
If no Google Drive tool exists, **stop** and tell the user to connect Google Drive in their
claude.ai connector settings. Do not try other auth methods or ask for credentials.

## 2. List the Drive folder

Search with query `parentId = '1986o0uX2Dzm1krxZ7UpDhcTWI5Kztmyw'`, `excludeContentSnippets: true`.
Results may come back only a few per page: **keep passing `nextPageToken` until a response has none.**
If the id returns nothing, search for a folder titled `Vandreture gpx` and use its id (tell the user it changed).

Write every `.gpx` result to a listing file, one per line: `<fileId> <title>`. Copy titles exactly.

## 3. Diff

    gpxsync diff <listing-file>

This prints files missing locally (with their ids) and local files no longer on Drive.

## 4. Download missing files

For each missing file, call the Drive download tool with its `fileId`.

- Large files: the tool says the result was saved to a file (JSON with `title` and base64 `content`).
  Pass those paths straight in: `gpxsync save <path> [<path> ...]`
- Small files that come back inline: write the base64 `content` string to a temp file, then
  `gpxsync save-b64 '<title>' <temp-file>`

`save` validates each file as GPX, never overwrites, and rebuilds `gpx/index.json`.
Downloads are independent, so issue several in parallel.

## 5. Check and report

    gpxsync status

Report to the user: how many files were added, any invalid downloads, any duplicate groups
(byte-identical files), and any local-only files.

- **Never delete anything on Drive or locally without asking.** For duplicates, offer to trash the
  extra copy on Drive (trash is recoverable) and remove it locally, then run `gpxsync manifest`.
- For local-only files, ask whether to delete them locally; the user may have removed them from Drive on purpose.

## 6. Serve the map (if asked, or on a fresh clone)

    python3 -m http.server 8000 --bind 127.0.0.1

Run it in the background, then tell the user to open http://127.0.0.1:8000 and tap **Load all**.

## Never

- Commit or push anything under `gpx/` (it is git-ignored; keep it that way).
- Publish the map with real tracks (GitHub Pages, artifacts, gists).
- Put tokens, cookies or OAuth credentials in this repo.
