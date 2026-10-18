# Hike Map

A single-page Leaflet map that overlays all my hikes (GPX tracks) in distinct colours.
Tap a track to see its name, date and length.

## Where the data is

The GPX files live only on Google Drive. They contain home locations and timestamps, so
they are **never committed**: `gpx/` is git-ignored.

To fetch them, open this repo in Claude Code (with the Google Drive connector enabled)
and say **"sync my hikes"**. That runs the [`sync-gpx` skill](.claude/skills/sync-gpx/SKILL.md),
which downloads new tracks into `gpx/`, writes `gpx/index.json`, and starts the server.
No keys or tokens are stored here.

## Run it

    python3 -m http.server 8000 --bind 127.0.0.1

Open http://127.0.0.1:8000 and tap **Load all**. You can also add GPX files from the
phone with **Add** (works without the server-side files).
