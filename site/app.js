// Главная: фаза Луны на выбранную дату из заранее посчитанных данных (data.json).
(async function () {
  const MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря"];
  const res = await fetch("data.json");
  const data = await res.json();
  const input = document.getElementById("date");
  const $ = (id) => document.getElementById(id);

  // Та же формула, что в build.py: освещённый полукруг плюс эллипс терминатора.
  function moonSvg(angle, size) {
    const r = size / 2 - 1, c = size / 2;
    const k = Math.cos(angle * Math.PI / 180);
    const rx = Math.abs(k) * r;
    const waxing = angle < 180;
    const outer = waxing ? 1 : 0;
    const inner = waxing ? (k > 0 ? 0 : 1) : (k > 0 ? 1 : 0);
    const d = `M${c},${c - r} A${r},${r} 0 0 ${outer} ${c},${c + r} A${rx.toFixed(2)},${r} 0 0 ${inner} ${c},${c - r} Z`;
    return `<svg class="moon" viewBox="0 0 ${size} ${size}" aria-hidden="true">` +
      `<circle cx="${c}" cy="${c}" r="${r}" class="moon-dark"/><path d="${d}" class="moon-lit"/></svg>`;
  }

  function mskToday() {
    const now = new Date(Date.now() + 3 * 3600 * 1000);
    return now.toISOString().slice(0, 10);
  }

  function fmt(iso) {
    const [date, time] = iso.split("T");
    const [, m, d] = date.split("-").map(Number);
    return `${d} ${MONTHS_GEN[m - 1]} в ${time.slice(0, 5)}`;
  }

  function show(day) {
    const rec = data.days[day];
    if (!rec) { $("name").textContent = "Нет данных на эту дату"; return; }
    $("moon").innerHTML = moonSvg(rec.angle, 160);
    $("name").textContent = rec.quarter ? `${rec.name} в ${rec.quarter[1]}` : rec.name;
    $("illum").textContent = `Освещённость ${rec.illum}% · возраст ${rec.age.toFixed(1)} сут. (в полдень по Москве)`;
    let sign = `Луна ${data.signs_in[rec.sign_start]} ${data.glyphs[rec.sign_start]}`;
    for (const [s, hm] of rec.ingress) sign += `, с ${hm} — ${data.signs_in[s]} ${data.glyphs[s]}`;
    $("sign").textContent = sign;
    const after = data.events.filter(([q, t]) => t.slice(0, 10) > day);
    const nextNew = after.find(([q]) => q === 0);
    const nextFull = after.find(([q]) => q === 2);
    const parts = [];
    if (nextNew) parts.push(`новолуние — ${fmt(nextNew[1])}`);
    if (nextFull) parts.push(`полнолуние — ${fmt(nextFull[1])}`);
    $("next").textContent = parts.length ? "Ближайшие: " + parts.join(", ") : "";
    $("month-link").href = `${day.slice(0, 7)}/#d${Number(day.slice(8, 10))}`;
  }

  let day = mskToday();
  if (!data.days[day]) day = input.min;
  input.value = day;
  show(day);
  input.addEventListener("change", () => input.value && show(input.value));
})();
