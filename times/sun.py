"""Precise sun events (NOAA/Meeus-level) returning fractional local minutes, for fitting official methods."""
import math, datetime as dt
from zoneinfo import ZoneInfo
def jd(y, m, d):
    if m <= 2: y -= 1; m += 12
    a = y // 100; b = 2 - a + a // 4
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + b - 1524.5
def sunpos(j):
    t = (j - 2451545.0) / 36525
    l0 = (280.46646 + t * (36000.76983 + 0.0003032 * t)) % 360
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    mr = math.radians(m)
    c = math.sin(mr) * (1.914602 - t * (0.004817 + 0.000014 * t)) + math.sin(2 * mr) * (0.019993 - 0.000101 * t) + math.sin(3 * mr) * 0.000289
    tl = l0 + c
    om = 125.04 - 1934.136 * t
    lam = tl - 0.00569 - 0.00478 * math.sin(math.radians(om))
    eps0 = 23 + (26 + ((21.448 - t * (46.815 + t * (0.00059 - t * 0.001813)))) / 60) / 60
    eps = eps0 + 0.00256 * math.cos(math.radians(om))
    decl = math.degrees(math.asin(math.sin(math.radians(eps)) * math.sin(math.radians(lam))))
    y = math.tan(math.radians(eps / 2)) ** 2
    l0r = math.radians(l0)
    eqt = 4 * math.degrees(y * math.sin(2 * l0r) - 2 * e * math.sin(mr) + 4 * e * y * math.sin(mr) * math.cos(2 * l0r) - 0.5 * y * y * math.sin(4 * l0r) - 1.25 * e * e * math.sin(2 * mr))
    return decl, eqt
def events(lat, lng, date, tzname, fajr=18.0, isha=18.0, isha_interval=None, asr_factor=1, elev=0.0, horizon=0.833):
    """Fractional local minutes since midnight: fajr, sunrise, dhuhr, asr, sunset, isha (no offsets, no rounding)."""
    tz = ZoneInfo(tzname)
    off = dt.datetime(date.year, date.month, date.day, 12, tzinfo=tz).utcoffset().total_seconds() / 60
    j0 = jd(date.year, date.month, date.day)
    def at(angle, after, guess):
        # iterate: hour angle for the sun's altitude = -angle at the time of the event
        tmin = guess
        for _ in range(3):
            j = j0 + (tmin - off) / 1440.0
            decl, eqt = sunpos(j)
            noon = 720 - 4 * lng - eqt + off
            cosH = (math.sin(math.radians(-angle)) - math.sin(math.radians(lat)) * math.sin(math.radians(decl))) / (math.cos(math.radians(lat)) * math.cos(math.radians(decl)))
            if abs(cosH) > 1: return None
            H = math.degrees(math.acos(cosH)) * 4
            tmin = noon + H if after else noon - H
        return tmin
    j = j0 + (720 - off) / 1440.0
    decl, eqt = sunpos(j)
    noon = 720 - 4 * lng - eqt + off
    for _ in range(2):
        decl, eqt = sunpos(j0 + (noon - off) / 1440.0); noon = 720 - 4 * lng - eqt + off
    h = horizon + 0.0347 * math.sqrt(elev) if elev > 0 else horizon
    sr = at(h, False, noon - 360); ss = at(h, True, noon + 360)
    decl_n, _ = sunpos(j0 + (noon - off) / 1440.0)
    asr_alt = -math.degrees(math.atan(1 / (asr_factor + math.tan(math.radians(abs(lat - decl_n))))))
    asr = at(asr_alt, True, noon + 200)
    fj = at(fajr, False, noon - 420)
    ish = ss + isha_interval if isha_interval else at(isha, True, noon + 420)
    return [fj, sr, noon, asr, ss, ish]
