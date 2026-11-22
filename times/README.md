# المواقيت الرسمية · Official prayer times

What وَاصْطَبِرْ downloads to show each country's prayer times exactly as its own authority
publishes them, to the minute. The times belong to the authorities named in each pack; this
folder only carries them to the app. The app sends nothing: it downloads `v1/index.json` and the
pack of the country it is in.

- `v1/index.json`: the countries, each pack's file, its short hash and the days it covers.
- `v1/<CC>-<YEAR>.json`: one country's year. Each zone: its name, the points it covers, its days
  from `from` as six `HHMM` a day (Fajr, sunrise, Dhuhr, Asr, Maghrib, Isha; dashes for a day not
  yet published), and `fit`: the zone's method fitted to its days, for the days after its table.
- `sources/<cc>.py`: how each authority's table is pulled. `build.py <CC>…` merges and rebuilds.
- `.github/workflows/times.yml`: the scheduled pull.

| Country | Authority | Source |
|---|---|---|
| JO الأردن | وزارة الأوقاف والشؤون والمقدسات الإسلامية | awqaf.gov.jo/ar/Pages/PrayerTime |
