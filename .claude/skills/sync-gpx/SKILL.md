---
name: sync-gpx
description: Sync hike GPX files from the owner's Google Drive folder "Vandreture gpx" into gpx/ for the hike map, via the Google Drive connector, then serve the map locally. Use when asked to sync, update, refresh or pull hikes/GPX/tracks, or before running the map on a fresh clone.
---

# Sync hikes from Google Drive

GPX tracks contain home locations and timestamps, so they are **never committed**.
Google Drive is the source of truth; `gpx/` is a local, git-ignored copy.
Access comes from the session's Google Drive connector. No keys or tokens anywhere.

**File content must never pass through your context.** This repo's `.claude/settings.json` sets
`MAX_MCP_OUTPUT_TOKENS=1000`, so Claude Code saves every Drive result to a file and only tells you
the path. You pass paths to the helper; you never read, print or retype the content.

Drive folder: **Vandreture gpx**, id `1986o0uX2Dzm1krxZ7UpDhcTWI5Kztmyw`.

Run everything from the repo root. `gpxsync` below means
`python3 -I .claude/skills/sync-gpx/gpxsync.py`.

## 1. Preflight

    gpxsync preflight

If it fails, **stop**: tell the user to start a new Claude Code session from the repo root
(the setting is read at startup). Do not continue without it.

You need the Google Drive tools (search files, download file content); load them if deferred.
If none exist, stop and tell the user to connect Google Drive in their claude.ai connector settings.

## 2. List the folder

Search with query `parentId = '1986o0uX2Dzm1krxZ7UpDhcTWI5Kztmyw'`, `excludeContentSnippets: true`,
`pageSize: 200`. Each result is saved to a file. Do not open it; note its path.
Drive often returns far fewer results than `pageSize` (e.g. 5, then the rest), so always check for
more pages with `jq -r '.nextPageToken // empty' <path>`; while that prints a token, search again
with that `pageToken`. Until every page is fetched, the diff's "local only" list is meaningless.

## 3. Diff

    gpxsync diff <listing-path> [<listing-path> ...]

Prints the missing files as `<fileId> <title>`, and local files no longer on Drive. It also stores
each file's Drive size (in the system temp dir) so `save` can verify downloads, so run `diff` first.

## 4. Download missing files

Call **`download_file_content`** (not `read_file_content`, which returns text for the model) for each
missing `fileId`, in parallel. Each result is saved to a file.
Then:

    gpxsync save <path> [<path> ...]

It checks each file against its Drive size and as GPX, never overwrites, and rebuilds `gpx/index.json`.

**If a download ever comes back inline** (you can see base64 content), stop. Do not copy it. The cap
isn't working; tell the user.

## 5. Report

    gpxsync status

Tell the user how many files were added, any failures, duplicate groups (byte-identical files)
and local-only files.

- **Never delete anything on Drive or locally without asking.** For duplicates, offer to trash the
  extra copy on Drive (trash is recoverable) and remove it locally, then run `gpxsync manifest`.
- For local-only files, ask before deleting; the user may have removed them from Drive on purpose.

## 6. Serve the map (if asked, or on a fresh clone)

    python3 -m http.server 8000 --bind 127.0.0.1

Run it in the background, then tell the user to open http://127.0.0.1:8000 and tap **Load all**.

## Never

- Commit or push anything under `gpx/` (it is git-ignored; keep it that way).
- Publish the map with real tracks (GitHub Pages, artifacts, gists).
- Put tokens, cookies or credentials in this repo.
