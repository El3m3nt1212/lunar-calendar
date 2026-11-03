# Независимая сверка: фазы и знак Луны из PyEphem (XEphem) против site/data.json (Astronomy Engine).
import datetime as dt, json, math, sys
import ephem
data = json.load(open(sys.argv[1], encoding="utf-8"))
fns = {0: ephem.next_new_moon, 1: ephem.next_first_quarter_moon, 2: ephem.next_full_moon, 3: ephem.next_last_quarter_moon}
worst = 0
for q, iso in data["events"]:
    t = dt.datetime.fromisoformat(iso)
    start = (t - dt.timedelta(days=2)).astimezone(dt.timezone.utc).replace(tzinfo=None)
    e = fns[q](start).datetime().replace(tzinfo=dt.timezone.utc)
    diff = abs((e - t).total_seconds()) / 60
    worst = max(worst, diff)
print(f"phase events: {len(data['events'])}, max diff vs PyEphem: {worst:.1f} min")
# знак Луны в 00:00 МСК каждого дня: тропическая эклиптическая долгота на дату
bad = 0
for day, rec in data["days"].items():
    t = dt.datetime.fromisoformat(day + "T00:00+03:00").astimezone(dt.timezone.utc).replace(tzinfo=None)
    m = ephem.Moon(t)
    lon = math.degrees(ephem.Ecliptic(m, epoch=t).lon)
    if int(lon // 30) != rec["sign_start"]:
        bad += 1
        print("sign mismatch", day, lon, rec["sign_start"])
print(f"days: {len(data['days'])}, sign mismatches at 00:00 MSK: {bad}")
