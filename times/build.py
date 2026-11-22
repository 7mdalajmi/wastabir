"""Builds the official prayer-time packs the app downloads (times/v1).

    python3 build.py JO SA ...      fetch these countries from their authorities and merge
    python3 build.py --index        rewrite index.json from the packs on disk

A pack holds one country's year: each zone's representative points and its days, each day six
times (Fajr, sunrise, Dhuhr, Asr, Maghrib, Isha) as «HHMM» in the zone's civil time, 24 digits a
day from the zone's «from» date; «------------------------» for a day the authority has not
published. A day once published stays: a run that sees fewer days (the source lists only today
onward) merges into what is there; a changed day is replaced (the authority corrected it).
"""
import datetime as dt, hashlib, importlib, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "v1")
sys.path.insert(0, os.path.join(HERE, "sources"))
BLANK = "-" * 24

def hhmm(m):
    return f"{m // 60 % 24:02d}{m % 60:02d}"

def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None

def unpack(zone):
    start = dt.date.fromisoformat(zone["from"])
    t = zone["t"]
    days = {}
    for i in range(len(t) // 24):
        chunk = t[i * 24:(i + 1) * 24]
        if chunk != BLANK:
            days[(start + dt.timedelta(days=i)).isoformat()] = chunk
    return days

def pack_days(days):
    keys = sorted(days)
    start, end = dt.date.fromisoformat(keys[0]), dt.date.fromisoformat(keys[-1])
    out, d = [], start
    while d <= end:
        out.append(days.get(d.isoformat(), BLANK))
        d += dt.timedelta(days=1)
    return start.isoformat(), "".join(out)

ROUND = {"d": math.floor, "u": math.ceil, "n": lambda x: math.floor(x + 0.5)}

def fit_zone(days, lat, lng, tz, angles):
    """The zone's method fitted to its published days: per time, the whole minutes added to the
    sea-level astronomy and how they are rounded, chosen for the most exact days. The app uses it
    for the days the table does not cover yet."""
    from sun import events
    fajr, isha, interval = angles.get("fajr", 18.0), angles.get("isha"), angles.get("interval")
    ev = {}
    for day in days:
        e = events(lat, lng, dt.date.fromisoformat(day), tz, fajr=fajr, isha=isha or 18.0, isha_interval=interval)
        if None not in e:
            ev[day] = e
    if len(ev) < 20:
        return None
    off, rnd, hits = [], "", 0
    for p in range(6):
        best = max(((sum(1 for d, e in ev.items() if ROUND[r](e[p] + o) == days[d][p]), o, r)
                    for o in range(-12, 13) for r in "dun"), key=lambda x: x[0])
        hits += best[0]; off.append(best[1]); rnd += best[2]
    return {"fajr": fajr, "isha": isha if interval is None else None, "interval": interval,
            "off": off, "round": rnd, "exact": round(hits / (6 * len(ev)), 3), "days": len(ev)}

def build(cc):
    src = importlib.import_module(cc.lower())
    fetched = src.fetch()                       # {zone: {date: [6 minutes]}}
    by_year = {}
    for zone, days in fetched.items():
        for day, mins in days.items():
            assert len(mins) == 6, (cc, zone, day, mins)
            by_year.setdefault(int(day[:4]), {}).setdefault(zone, {})[day] = "".join(hhmm(m) for m in mins)
    changed = []
    for year, zones in sorted(by_year.items()):
        path = os.path.join(OUT, f"{cc}-{year}.json")
        old = load(path) or {}
        old_days = {z["id"]: unpack(z) for z in old.get("zones", [])}
        old_fits = {z["id"]: z["fit"] for z in old.get("zones", []) if z.get("fit")}
        out_zones = []
        for zid, meta in src.ZONES.items():
            days = dict(old_days.get(zid, {}))
            days.update(zones.get(zid, {}))
            if not days:
                continue
            start, t = pack_days(days)
            ar, en, points = meta[0], meta[1], meta[2]
            z = {"id": zid, "ar": ar, "en": en, "points": [[round(a, 4), round(b, 4)] for a, b in points], "from": start, "t": t}
            ztz = meta[3] if len(meta) > 3 and meta[3] else None
            if ztz:
                z["tz"] = ztz
            minutes = {d: [int(v[i:i + 2]) * 60 + int(v[i + 2:i + 4]) for i in range(0, 24, 4)] for d, v in days.items()}
            history = getattr(src, "history", lambda zone: {})(zid)          # older official days, for the fit only
            f = fit_zone({**history, **minutes}, points[0][0], points[0][1], ztz or src.TZ, getattr(src, "ANGLES", {}))
            # A fit from fewer days never replaces one from more (the runner has no history folder).
            prev = old_fits.get(zid)
            if prev and (not f or prev.get("days", 0) > f["days"]):
                f = prev
            if f:
                z["fit"] = f
            out_zones.append(z)
        pack = {"v": 1, "country": cc, "year": year, "tz": src.TZ, "authority": src.AUTHORITY,
                "source": src.URL, "radiusKm": getattr(src, "RADIUS_KM", 60), "zones": out_zones}
        text = json.dumps(pack, ensure_ascii=False, separators=(",", ":"))
        if json.dumps(old, ensure_ascii=False, separators=(",", ":")) != text:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            changed.append(path)
        print(f"{cc} {year}: {len(out_zones)} zones, " + ", ".join(f"{z['id']}:{len(z['t']) // 24}d" for z in out_zones[:4]) + (" …" if len(out_zones) > 4 else ""))
    return changed

def index():
    countries = {}
    for name in sorted(os.listdir(OUT)):
        if not name.endswith(".json") or name == "index.json":
            continue
        pack = load(os.path.join(OUT, name))
        raw = open(os.path.join(OUT, name), "rb").read()
        c = countries.setdefault(pack["country"], {"authority": pack["authority"], "source": pack["source"], "files": {}})
        firsts = [z["from"] for z in pack["zones"]]
        lasts = [(dt.date.fromisoformat(z["from"]) + dt.timedelta(days=len(z["t"]) // 24 - 1)).isoformat() for z in pack["zones"]]
        c["files"][str(pack["year"])] = {"file": name, "sha": hashlib.sha256(raw).hexdigest()[:16], "bytes": len(raw),
                                         "from": min(firsts), "to": max(lasts), "zones": len(pack["zones"])}
    doc = {"v": 1, "updated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "countries": countries}
    old = load(os.path.join(OUT, "index.json"))
    if old and {k: v for k, v in old.items() if k != "updated"} == {k: v for k, v in doc.items() if k != "updated"}:
        return False
    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    return True

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    failed = []
    for cc in [a for a in sys.argv[1:] if not a.startswith("--")]:
        try:
            build(cc.upper())
        except Exception as e:                  # one authority down never stops the others
            print(f"{cc}: FAILED {type(e).__name__}: {e}", file=sys.stderr)
            failed.append(cc)
    print("index changed" if index() else "index unchanged")
    sys.exit(1 if failed and len(failed) == len([a for a in sys.argv[1:] if not a.startswith('--')]) else 0)
