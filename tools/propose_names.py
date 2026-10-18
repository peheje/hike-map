"""Propose specific names for hike GPX files. Renames nothing.

Usage (from gpx/):  python3 -I ../tools/propose_names.py OUT.tsv FILE.gpx...
Writes OUT.tsv with columns: old, new, source, flags.

Name format: <date>_<area>_<place>[_<place2>]_<km>km[_<alltrailsId>].gpx
- Older AllTrails names ("vandretur – eftermiddag kl. Hald Sø") already hold the place.
- Generic ones ("Aarhus Vandring") get the place from OpenStreetMap: the named forests,
  parks, lakes and reserves the route passes through.
Only points from the middle 60% of a track are sent to Overpass, so start/end points
(often home) never leave the device.
"""
import json
import math
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
UA = "hike-map-names/0.2 (personal project)"
SAMPLES = 12
MAX_LABEL = 36
DROP_PREFIXES = re.compile(r"^(Nationalpark|Naturpark|Naturnationalpark)\s+", re.I)
INTERESTING = re.compile(
    r"^(natural=(wood|water|heath|wetland|beach|peak|valley)|landuse=forest|leisure=(park|nature_reserve)|"
    r"boundary=(protected_area|national_park)|place=(island|islet))$"
)


def read_gpx(path):
    root = ET.parse(path).getroot()
    pts, meta_name = [], ""
    for e in root.iter():
        if e.tag.endswith("trkpt"):
            pts.append((float(e.get("lat")), float(e.get("lon"))))
        elif e.tag.endswith("name") and not meta_name:
            meta_name = (e.text or "").strip()
    return pts, meta_name


def hav(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def km(pts):
    return sum(hav(pts[i - 1], pts[i]) for i in range(1, len(pts))) / 1000


def interior_samples(pts):
    mid = pts[int(len(pts) * 0.2):int(len(pts) * 0.8)] or pts
    step = max(1, len(mid) // SAMPLES)
    return mid[::step][:SAMPLES]


def overpass(query):
    # Public servers are often overloaded: try each, backing off between rounds
    data = urllib.parse.urlencode({"data": query}).encode()
    last = None
    for attempt in range(4):
        for url in OVERPASS_SERVERS:
            try:
                req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=90) as r:
                    return json.load(r)["elements"]
            except Exception as err:
                last = err
        time.sleep(5 * (attempt + 1))
    raise last


def osm_places(samples):
    parts = "".join(
        f"is_in({la:.5f},{lo:.5f})->.a{i};area.a{i}[name]->.n{i};.n{i} out tags;" for i, (la, lo) in enumerate(samples)
    )
    hits = Counter()
    for el in overpass(f"[out:json][timeout:60];{parts}"):
        t = el.get("tags", {})
        kinds = [f"{k}={t[k]}" for k in ("natural", "landuse", "leisure", "boundary", "place") if k in t]
        if any(INTERESTING.match(k) for k in kinds):
            hits[t["name"]] += 1
    return hits


def nearby_village(lat, lon):
    q = (f'[out:json][timeout:30];node(around:2000,{lat:.5f},{lon:.5f})'
         f'[place~"^(village|hamlet|suburb|neighbourhood|locality)$"][name];out tags 1;')
    els = overpass(q)
    return els[0]["tags"]["name"] if els else None


def slug(s):
    for a, b in (("ø", "oe"), ("Ø", "Oe"), ("æ", "ae"), ("Æ", "Ae"), ("å", "aa"), ("Å", "Aa")):
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")


def label_from(places):
    """Join up to two places; drop the second if the label gets too long."""
    names = [DROP_PREFIXES.sub("", p) for p in places][:2]
    label = "_".join(slug(n) for n in names)
    if len(label) > MAX_LABEL and len(names) > 1:
        label = slug(names[0])
    return label


def meta_place(meta_name):
    """(area, places) from the GPX name. places=None means: look it up."""
    m = re.match(r"^(.*?)\s+(Vandring|Hiking)$", meta_name)
    if m:
        return m.group(1), None
    # "vandretur – eftermiddag kl. Hald Sø" -> "Hald Sø"; strip the time-of-day boilerplate
    # AllTrails sometimes dropped the dash ("vandretur  eftermiddag"), so it is optional
    rest = re.sub(r"^vandretur\s*[–-]?\s*\w+(\s+kl\.?)?\s*", "", meta_name, flags=re.I).strip()
    if not rest:
        return "", None
    return "", [p.strip() for p in re.split(r"\s+-\s+", rest) if p.strip()]


def propose(path):
    name = path.name
    m = re.match(r"^(\d{4}-\d{2}-\d{2})[_-].*?(?:_(\d{6,}))?\.gpx$", name)
    date, aid = (m.group(1), m.group(2)) if m else ("", None)
    # No AllTrails id and not the generic "..._Vandring.gpx": the owner named it, keep it
    if not aid and not re.search(r"_(Vandring|Hiking)\.gpx$", name):
        return name, name, "owner-named", ["kept"]
    pts, meta_name = read_gpx(path)
    area, places = meta_place(meta_name)
    flags, source = [], "gpx-name"
    if places is None:
        samples = interior_samples(pts)
        hits = osm_places(samples)
        places = [n for n, _ in hits.most_common(2)]
        source = "osm: " + ", ".join(f"{n} ({c}/12)" for n, c in hits.most_common(3))
        if hits and hits.most_common(1)[0][1] < 3:
            flags.append("weak-match")
        if not places:
            time.sleep(1)
            v = nearby_village(*samples[len(samples) // 2])
            places = [v] if v else []
            source = f"nearest village: {v}" if v else "nothing found"
            flags.append("village-fallback" if v else "no-place")
    label = label_from(places)
    dist = km(pts)
    if dist < 1 or dist > 25:
        flags.append("check-distance")
    new = "_".join(x for x in (date, slug(area), label, f"{dist:.0f}km", aid) if x) + ".gpx"
    return name, new, source, flags


if __name__ == "__main__":
    out, files = Path(sys.argv[1]), sys.argv[2:]
    rows = []
    for f in files:
        try:
            old, new, source, flags = propose(Path(f))
        except Exception as e:
            old, new, source, flags = Path(f).name, "", f"ERROR {e}", ["error"]
        rows.append([old, new, source, flags])
        print(f"{old} -> {new or '(none)'}  [{source}] {' '.join(flags)}", flush=True)
        if not source.startswith("gpx-name"):
            time.sleep(2)  # be polite to the public Overpass servers
    news = Counter(r[1] for r in rows if r[1])
    for r in rows:
        if r[1] and news[r[1]] > 1:
            r[3].append("duplicate-new-name")
    out.write_text("".join(f"{o}\t{n}\t{s}\t{','.join(fl)}\n" for o, n, s, fl in rows))
    print(f"wrote {len(rows)} rows to {out}")
