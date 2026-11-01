# Vandrekort

A one-page map of all my hikes on OpenStreetMap. It shows how much of each hike was new
ground, and lets me drop in a new GPX file to see how much of it I have already walked.

## Where the data is

The GPX files live only in my Google Drive folder "Vandreture gpx". They contain home
locations and timestamps, so they are **never committed** (`gpx/` and `*.gpx` are git-ignored).

The page reads them straight from Drive after I log in with Google. Nothing is sent anywhere
else: the access token stays in the browser tab for at most an hour, and parsed tracks are
cached in that browser's IndexedDB so the map shows up fast next time.

Who can see the hikes: only someone who logs in with the Google account that owns the folder.
The OAuth client stays in "Testing" mode with that account as the only test user, so Google
refuses every other account at the login step. A visitor without login sees an empty map.

## Google setup (once)

1. Open https://console.cloud.google.com, create a project (e.g. "Vandrekort").
2. **APIs & Services → Library**: enable **Google Drive API**.
3. **APIs & Services → OAuth consent screen** (Google Auth Platform):
   - User type **External**, app name "Vandrekort", your email as support and developer contact.
   - **Audience**: leave publishing status at **Testing**, add your own Google account under **Test users**.
   - **Data access**: add the scopes `.../auth/drive.readonly` and `.../auth/drive`
     (the last one is only requested when you press "Gem i Drive").
4. **Clients → Create client → Web application**. Under **Authorized JavaScript origins** add:
   - `http://localhost:8765` (local testing)
   - the GitHub Pages origin, e.g. `https://peheje.github.io`
5. Copy the client ID into `config.js`.

## Run locally

    python -m http.server 8765 --bind 127.0.0.1

Open http://localhost:8765 (use `localhost`, not `127.0.0.1`, so it matches the origin above).

## Other tools

- `tools/propose_names.py` suggests descriptive file names for GPX files.
- `.claude/skills/sync-gpx` copies the GPX files from Drive into `gpx/` via Claude Code,
  for working on the files locally. The map itself does not need it.
