"""Сборка статического сайта «Лунный календарь».

Считает фазы Луны и положение Луны в знаках зодиака (тропический зодиак,
геоцентрическая эклиптическая долгота на дату) библиотекой Astronomy Engine
и генерирует из одного шаблона страницу на каждый месяц, главную страницу
с интерактивным выбором даты, sitemap.xml и robots.txt.

Запуск:  python build.py            -> папка docs/
Все времена — московские (UTC+3, без перехода на летнее время).
"""
import calendar
import datetime as dt
import html
import json
import math
import shutil
from pathlib import Path

import astronomy

BASE_URL = "https://el3m3nt1212.github.io/lunar-calendar/"
MSK = dt.timezone(dt.timedelta(hours=3))
FIRST_MONTH = (2026, 1)
LAST_MONTH = (2028, 12)
ROOT = Path(__file__).parent
OUT = ROOT / "docs"  # GitHub Pages публикует из /docs

SIGNS = ["Овен", "Телец", "Близнецы", "Рак", "Лев", "Дева",
         "Весы", "Скорпион", "Стрелец", "Козерог", "Водолей", "Рыбы"]
SIGNS_IN = ["в Овне", "в Тельце", "в Близнецах", "в Раке", "во Льве", "в Деве",
            "в Весах", "в Скорпионе", "в Стрельце", "в Козероге", "в Водолее", "в Рыбах"]
# U+FE0E — текстовое начертание, иначе Windows и Android рисуют знаки как эмодзи.
SIGN_GLYPHS = [g + "︎" for g in "♈♉♊♋♌♍♎♏♐♑♒♓"]
MONTHS = ["январь", "февраль", "март", "апрель", "май", "июнь",
          "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"]
MONTHS_PREP = ["январе", "феврале", "марте", "апреле", "мае", "июне",
               "июле", "августе", "сентябре", "октябре", "ноябре", "декабре"]
MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня",
              "июля", "августа", "сентября", "октября", "ноября", "декабря"]
WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
QUARTERS = ["Новолуние", "Первая четверть", "Полнолуние", "Последняя четверть"]


# ---------- астрономия ----------

def to_astro(t: dt.datetime) -> astronomy.Time:
    u = t.astimezone(dt.timezone.utc)
    return astronomy.Time.Make(u.year, u.month, u.day, u.hour, u.minute,
                               u.second + u.microsecond / 1e6)


def to_msk(t: astronomy.Time) -> dt.datetime:
    return t.Utc().replace(tzinfo=dt.timezone.utc).astimezone(MSK)


def moon_lon(t: dt.datetime) -> float:
    return astronomy.EclipticGeoMoon(to_astro(t)).lon % 360.0


def phase_angle(t: dt.datetime) -> float:
    """0 — новолуние, 90 — первая четверть, 180 — полнолуние, 270 — последняя."""
    return astronomy.MoonPhase(to_astro(t))


def illumination(t: dt.datetime) -> float:
    return astronomy.Illumination(astronomy.Body.Moon, to_astro(t)).phase_fraction


def phase_name(angle: float) -> str:
    # Четыре главные фазы — моменты; между ними — промежуточные названия.
    if angle < 90:
        return "Растущий серп"
    if angle < 180:
        return "Растущая Луна"
    if angle < 270:
        return "Убывающая Луна"
    return "Убывающий серп"


def quarters_between(start: dt.datetime, end: dt.datetime):
    mq = astronomy.SearchMoonQuarter(to_astro(start))
    out = []
    while True:
        t = to_msk(mq.time)
        if t >= end:
            return out
        out.append((mq.quarter, t))
        mq = astronomy.NextMoonQuarter(mq)


def sign_ingresses(start: dt.datetime, end: dt.datetime):
    """Моменты входа Луны в знак: перебор по часу, затем бисекция до секунды."""
    out = []
    step = dt.timedelta(hours=1)
    t, lon = start, moon_lon(start)
    while t < end:
        t2 = t + step
        lon2 = moon_lon(t2)
        if int(lon2 // 30) != int(lon // 30):
            boundary_sign = int(lon2 // 30)
            lo, hi = t, t2
            while (hi - lo).total_seconds() > 1:
                mid = lo + (hi - lo) / 2
                if int(moon_lon(mid) // 30) == boundary_sign:
                    hi = mid
                else:
                    lo = mid
            out.append((boundary_sign, hi))
        t, lon = t2, lon2
    return out


# ---------- данные ----------

def month_range():
    y, m = FIRST_MONTH
    while (y, m) <= LAST_MONTH:
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def build_data():
    start = dt.datetime(*FIRST_MONTH, 1, tzinfo=MSK)
    ly, lm = LAST_MONTH
    end = dt.datetime(ly + 1, 1, 1, tzinfo=MSK) if lm == 12 else dt.datetime(ly, lm + 1, 1, tzinfo=MSK)
    quarters = quarters_between(start - dt.timedelta(days=32), end + dt.timedelta(days=32))
    ingresses = sign_ingresses(start - dt.timedelta(days=3), end)

    days = {}
    d = start
    while d < end:
        noon = d + dt.timedelta(hours=12)
        nxt = d + dt.timedelta(days=1)
        ang = phase_angle(noon)
        q_today = [(q, t) for q, t in quarters if d <= t < nxt]
        ing_today = [(s, t) for s, t in ingresses if d <= t < nxt]
        prev_new = max(t for q, t in quarters if q == 0 and t <= noon)
        days[d.date().isoformat()] = {
            "angle": round(ang, 2),
            "illum": round(illumination(noon) * 100),
            "age": round((noon - prev_new).total_seconds() / 86400, 1),
            "name": QUARTERS[q_today[0][0]] if q_today else phase_name(ang),
            "quarter": [q_today[0][0], q_today[0][1].strftime("%H:%M")] if q_today else None,
            "sign_start": int(moon_lon(d) // 30),
            "ingress": [[s, t.strftime("%H:%M")] for s, t in ing_today],
        }
        d = nxt
    events = [[q, t.isoformat(timespec="minutes")] for q, t in quarters]
    return days, events


# ---------- разметка ----------

def moon_svg(angle: float, size: int = 28) -> str:
    """Луна для северного полушария: растущая освещена справа."""
    r = size / 2 - 1
    c = size / 2
    k = math.cos(math.radians(angle))  # 1 — новолуние, -1 — полнолуние
    rx = abs(k) * r
    waxing = angle < 180
    # Освещённый полукруг с той стороны, где светит Солнце, плюс эллипс терминатора.
    outer_sweep = 1 if waxing else 0
    inner_sweep = (0 if k > 0 else 1) if waxing else (1 if k > 0 else 0)
    lit = (f"M{c},{c - r} A{r},{r} 0 0 {outer_sweep} {c},{c + r} "
           f"A{rx:.2f},{r} 0 0 {inner_sweep} {c},{c - r} Z")
    return (f'<svg class="moon" viewBox="0 0 {size} {size}" width="{size}" height="{size}" aria-hidden="true">'
            f'<circle cx="{c}" cy="{c}" r="{r}" class="moon-dark"/>'
            f'<path d="{lit}" class="moon-lit"/></svg>')


def page(title, description, canonical, body, rel, extra_head=""):
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(description)}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{canonical}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Ccircle cx='8' cy='8' r='7' fill='%23e8e2c8'/%3E%3C/svg%3E">
<link rel="stylesheet" href="{rel}style.css">
{extra_head}
</head>
<body>
<header class="top"><a class="brand" href="{rel or './'}">☾ Лунный календарь</a></header>
<main>
{body}
</main>
<footer>
<p>Расчёт — <a href="https://github.com/cosinekitty/astronomy">Astronomy Engine</a>. Время московское (UTC+3).
Знак Луны — тропический зодиак, геоцентрическая долгота. Положение Луны в знаке — астрологическое понятие, не астрономическое.</p>
</footer>
</body>
</html>
"""


def month_slug(y, m):
    return f"{y}-{m:02d}"


def month_page(y, m, days, events):
    start = dt.datetime(y, m, 1, tzinfo=MSK)
    ndays = calendar.monthrange(y, m)[1]
    end = start + dt.timedelta(days=ndays)
    title = f"Лунный календарь на {MONTHS[m - 1]} {y} года — фазы Луны и Луна в знаках"
    q_month = [(q, dt.datetime.fromisoformat(t)) for q, t in events
               if start <= dt.datetime.fromisoformat(t) < end]
    new = [t for q, t in q_month if q == 0]
    full = [t for q, t in q_month if q == 2]

    def when(t):
        return f"{t.day} {MONTHS_GEN[t.month - 1]} в {t:%H:%M}"

    intro = []
    if new:
        intro.append("новолуние — " + ", ".join(when(t) for t in new))
    if full:
        intro.append("полнолуние — " + ", ".join(when(t) for t in full))
    lead = (f"В {MONTHS_PREP[m - 1]} {y} года " + "; ".join(intro) + " по московскому времени."
            if intro else "")
    description = (f"Фазы Луны на {MONTHS[m - 1]} {y}: {'; '.join(intro)}. "
                   f"Луна в знаках зодиака по дням, время входа в знак, процент освещённости.")

    rows = []
    for i in range(ndays):
        d = start + dt.timedelta(days=i)
        rec = days[d.date().isoformat()]
        sign = SIGNS[rec["sign_start"]]
        sign_cell = f'{SIGN_GLYPHS[rec["sign_start"]]} {sign}'
        for s, hm in rec["ingress"]:
            sign_cell += f'<br><span class="ingress">с {hm} — {SIGN_GLYPHS[s]} {SIGNS[s]}</span>'
        name = html.escape(rec["name"])
        if rec["quarter"]:
            name = f'<strong>{name}</strong> <span class="ingress">{rec["quarter"][1]}</span>'
        weekend = " weekend" if d.weekday() >= 5 else ""
        rows.append(
            f'<tr class="day{weekend}" id="d{d.day}"><td class="date">{d.day} <span>{WEEKDAYS[d.weekday()]}</span></td>'
            f'<td class="ph">{moon_svg(rec["angle"])}</td>'
            f'<td>{name}<br><span class="ingress">{rec["illum"]}% · {rec["age"]:.1f} сут.</span></td>'
            f'<td>{sign_cell}</td></tr>')

    phases_list = "".join(
        f"<li>{moon_svg(q * 90.0, 22)} <span><b>{QUARTERS[q]}</b> — {when(t)}</span></li>" for q, t in q_month)

    prev_y, prev_m = (y - 1, 12) if m == 1 else (y, m - 1)
    next_y, next_m = (y + 1, 1) if m == 12 else (y, m + 1)
    nav = '<nav class="months">'
    if (prev_y, prev_m) >= FIRST_MONTH:
        nav += f'<a href="../{month_slug(prev_y, prev_m)}/">← {MONTHS[prev_m - 1]} {prev_y}</a>'
    nav += '<a href="../">Сегодня</a>'
    if (next_y, next_m) <= LAST_MONTH:
        nav += f'<a href="../{month_slug(next_y, next_m)}/">{MONTHS[next_m - 1]} {next_y} →</a>'
    nav += "</nav>"

    body = f"""
<h1>Лунный календарь на {MONTHS[m - 1]} {y} года</h1>
<p class="lead">{lead}</p>
<section class="card">
<h2>Главные фазы</h2>
<ul class="phases">{phases_list}</ul>
</section>
<section class="card">
<h2>По дням</h2>
<div class="table-wrap">
<table class="cal">
<thead><tr><th>Дата</th><th></th><th>Фаза в полдень</th><th>Луна в знаке</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
</div>
</section>
{nav}
"""
    url = f"{BASE_URL}{month_slug(y, m)}/"
    return page(title, description, url, body, "../"), url


def index_page():
    links = []
    for y in range(FIRST_MONTH[0], LAST_MONTH[0] + 1):
        items = "".join(f'<a href="{month_slug(y, m)}/">{MONTHS[m - 1]}</a>'
                        for yy, m in month_range() if yy == y)
        links.append(f'<div class="year"><h3>{y}</h3><div class="mgrid">{items}</div></div>')
    body = f"""
<h1>Фаза Луны сегодня</h1>
<section class="card today" id="today">
  <div class="big-moon" id="moon"></div>
  <div class="facts">
    <label class="pick">Дата <input type="date" id="date" min="{FIRST_MONTH[0]}-{FIRST_MONTH[1]:02d}-01" max="{LAST_MONTH[0]}-{LAST_MONTH[1]:02d}-{calendar.monthrange(*LAST_MONTH)[1]}"></label>
    <p class="phase-name" id="name">—</p>
    <p id="illum"></p>
    <p id="sign"></p>
    <p id="next"></p>
    <p><a id="month-link" href="#">Весь месяц →</a></p>
  </div>
</section>
<noscript><p>Для выбора даты включите JavaScript; календарь по месяцам работает и без него.</p></noscript>
<section class="card">
<h2>Календарь по месяцам</h2>
{''.join(links)}
</section>
"""
    title = "Лунный календарь — фаза Луны сегодня, Луна в знаках зодиака"
    description = ("Фаза Луны на сегодня и на любую дату: процент освещённости, возраст Луны, "
                   "Луна в знаке зодиака, ближайшие новолуние и полнолуние. Календарь по месяцам 2026–2028.")
    extra = '<script src="app.js" defer></script>'
    return page(title, description, BASE_URL, body, "", extra)


def main():
    days, events = build_data()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copy(ROOT / "static" / "style.css", OUT / "style.css")
    shutil.copy(ROOT / "static" / "app.js", OUT / "app.js")
    (OUT / "data.json").write_text(
        json.dumps({"days": days, "events": events, "signs": SIGNS, "signs_in": SIGNS_IN,
                    "glyphs": SIGN_GLYPHS, "quarters": QUARTERS},
                   ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (OUT / "index.html").write_text(index_page(), encoding="utf-8")
    urls = [BASE_URL]
    for y, m in month_range():
        text, url = month_page(y, m, days, events)
        p = OUT / month_slug(y, m)
        p.mkdir()
        (p / "index.html").write_text(text, encoding="utf-8")
        urls.append(url)
    today = dt.date.today().isoformat()
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc><lastmod>{today}</lastmod></url>\n" for u in urls)
        + "</urlset>\n", encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}sitemap.xml\n", encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    print(f"pages: {len(urls)}, days: {len(days)}, phase events: {len(events)}")


if __name__ == "__main__":
    main()
