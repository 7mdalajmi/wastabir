"""Jordan — وزارة الأوقاف والشؤون والمقدسات الإسلامية (awqaf.gov.jo/ar/Pages/PrayerTime).

The page's dated search fails on the server, but its table pager works: with empty dates the
grid lists the chosen zone from today to 31 December, ten days a page. Paging once to page 2
switches the grid to the zone. The clock is 12-hour without AM/PM.
"""
import http.cookiejar, re, urllib.parse, urllib.request

URL = "https://www.awqaf.gov.jo/ar/Pages/PrayerTime"
GRID = "ctl00$MainContent$gvWebparts"
AUTHORITY = {"ar": "وزارة الأوقاف والشؤون والمقدسات الإسلامية", "en": "Ministry of Awqaf, Islamic Affairs and Holy Places"}
TZ = "Asia/Amman"
# id: (Arabic, English, representative points (lat, lng): each governorate or town the zone covers)
ZONES = {
    "1": ("عمان، البلقاء، الزرقاء، مادبا", "Amman, Balqa, Zarqa, Madaba",
          [(31.9539, 35.9106), (32.0392, 35.7272), (32.0728, 36.0880), (31.7160, 35.7939), (31.7300, 35.9800)]),
    "2": ("اربد", "Irbid", [(32.5556, 35.8500), (32.6500, 35.6900), (32.4500, 35.9700)]),
    "3": ("الكرك", "Karak", [(31.1853, 35.7048), (31.2600, 35.5600), (31.0500, 35.7000)]),
    "4": ("الطفيلة", "Tafilah", [(30.8375, 35.6044)]),
    "5": ("معان", "Ma'an", [(30.1962, 35.7341), (29.9500, 35.8300)]),
    "6": ("العقبة", "Aqaba", [(29.5321, 35.0063), (29.6000, 35.4200)]),
    "7": ("الأغوار الشمالية", "Northern Jordan Valley", [(32.4300, 35.6100), (32.3200, 35.5900)]),
    "8": ("جرش وعجلون", "Jerash & Ajloun", [(32.2808, 35.8993), (32.3326, 35.7517)]),
    "9": ("المفرق", "Mafraq", [(32.3429, 36.2080), (32.3500, 36.6000), (32.1800, 37.1000)]),
    "11": ("ذيبان", "Dhiban", [(31.4990, 35.7810)]),
    "12": ("الأزرق", "Azraq", [(31.8336, 36.8164)]),
    "13": ("الأغوار الوسطى", "Central Jordan Valley", [(32.0500, 35.5700), (31.9000, 35.5900), (31.7600, 35.5900)]),
    "14": ("الشوبك والبتراء", "Shoubak & Petra", [(30.5208, 35.5592), (30.3285, 35.4444)]),
    "15": ("الظليل والهاشمية", "Dhulail & Hashemiya", [(32.1200, 36.2700), (32.1400, 36.1300)]),
    "19": ("الرويشد", "Ruwaished", [(32.5000, 38.2000)]),
}

def to_24h(cells):
    """Fajr and sunrise are morning; Dhuhr is noon (12 or a small hour); the rest are afternoon."""
    out = []
    for i, t in enumerate(cells):
        h, m = int(t[:2]), int(t[3:5])
        if (i == 2 and h < 10) or (i > 2 and h < 12):
            h += 12
        out.append(h * 60 + m)
    if out != sorted(out):
        raise ValueError(f"out of order: {cells}")
    return out

def parse(html):
    rows = {}
    for i, d in re.findall(r'lbldate_(\d+)">(\d\d/\d\d/\d{4})', html):
        cells = [re.search(rf'Labpayr{k}_{i}">([\d:]+)', html)[1] for k in range(1, 7)]
        dd, mm, yyyy = d.split("/")
        rows[f"{yyyy}-{mm}-{dd}"] = to_24h(cells)
    return rows

def pages(html):
    return {int(p) for p in re.findall(r"Page\$(\d+)&#39;", html)}

def fetch_zone(zone):
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    op.addheaders = [("User-Agent", "Mozilla/5.0 (Wastabir prayer-times sync)")]
    html = op.open(URL, timeout=60).read().decode()
    if 2 not in pages(html):                       # the last days of December: one page, zone 1 only
        return parse(html) if zone == "1" else {}
    def go(page):
        form = dict(re.findall(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"', html))
        form.update({"ctl00$MainContent$DropCompany": zone, "ctl00$MainContent$txtFromDate": "",
                     "ctl00$MainContent$txtToDate": "", "__EVENTTARGET": GRID, "__EVENTARGUMENT": f"Page${page}"})
        return op.open(URL, urllib.parse.urlencode(form).encode(), timeout=120).read().decode()
    html = go(2)
    html = go(1)
    rows, page = parse(html), 1
    while page + 1 in pages(html):
        page += 1
        html = go(page)
        rows.update(parse(html))
    return rows

def fetch():
    """{zone id: {"YYYY-MM-DD": [six minutes since midnight]}}. The site drops connections at
    times: each zone is tried three times, and a zone that still fails keeps its days."""
    import time
    out, failed = {}, []
    for z in ZONES:
        for attempt in range(3):
            try:
                out[z] = fetch_zone(z)
                break
            except (OSError, ValueError) as e:
                if attempt == 2:
                    failed.append(f"{z}: {e}")
                else:
                    time.sleep(15 * (attempt + 1))
    if not out:
        raise RuntimeError("every zone failed: " + "; ".join(failed))
    for f in failed:
        print("  zone failed:", f)
    return out

ANGLES = {"fajr": 18.0, "isha": 18.0}

def history(zone):
    """Older official days kept beside the scraper (not published), to fit the zone's method."""
    import glob, json, os, datetime as dt
    out = {}
    ar = ZONES[zone][0]
    for f in sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "history", "jo", f"*_{ar}.json"))):
        for r in json.load(open(f, encoding="utf-8"))["prayerData"]:
            d = dt.date(*map(int, reversed(r["date"].split("/")))).isoformat()
            mins = []
            for i, k in enumerate(["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"]):
                h, m = map(int, r[k].split(":"))
                if (i == 2 and h < 10) or (i > 2 and h < 12):
                    h += 12
                mins.append(h * 60 + m)
            out[d] = mins
    return out
