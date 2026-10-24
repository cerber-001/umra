// Время намаза по методу Умм аль-Кура — официальный календарь Саудовской Аравии, по нему звучит азан в Хараме.
// Фаджр — солнце на 18,5° под горизонтом, иша — через 90 мин после магриба (в Рамадан — через 120),
// аср — когда тень равна предмету (так считает календарь Умм аль-Кура). Расчёт астрономический: расхождение
// с печатным календарём — до 1–2 минут. Общий файл для «Где группа» и «Харам в 3D».
(function () {
  "use strict";
  const R = Math.PI / 180;
  const sin = (d) => Math.sin(d * R), cos = (d) => Math.cos(d * R), tan = (d) => Math.tan(d * R);
  const asin = (x) => Math.asin(x) / R, acos = (x) => Math.acos(Math.max(-1, Math.min(1, x))) / R;
  const atan2 = (y, x) => Math.atan2(y, x) / R, acot = (x) => Math.atan(1 / x) / R;
  const fix = (a, b) => a - b * Math.floor(a / b);

  function sun(jd) {   // склонение солнца и уравнение времени
    const D = jd - 2451545.0, g = fix(357.529 + 0.98560028 * D, 360), q = fix(280.459 + 0.98564736 * D, 360);
    const L = fix(q + 1.915 * sin(g) + 0.020 * sin(2 * g), 360), e = 23.439 - 0.00000036 * D;
    const RA = atan2(cos(e) * sin(L), cos(L)) / 15;
    return { decl: asin(sin(e) * sin(L)), eqt: q / 15 - fix(RA, 24) };
  }
  function julian(y, m, d) {
    if (m <= 2) { y -= 1; m += 12; }
    const A = Math.floor(y / 100), B = 2 - A + Math.floor(A / 4);
    return Math.floor(365.25 * (y + 4716)) + Math.floor(30.6001 * (m + 1)) + d + B - 1524.5;
  }
  // день по календарю Умм аль-Кура: месяц 9 — Рамадан
  function hijriMonth(date, tz) {
    try {
      const d = new Date(date.getTime() + tz * 3600000);
      const s = new Intl.DateTimeFormat("en-u-ca-islamic-umalqura-nu-latn", { month: "numeric", timeZone: "UTC" }).format(d);
      return parseInt(s, 10) || 0;
    } catch (e) { return 0; }
  }

  // date — любой момент дня; lat/lon — место; tz — часовой пояс (Мекка и Медина: +3).
  // Ответ — минуты от полуночи местного времени.
  function times(date, lat, lon, tz) {
    if (tz === undefined) tz = 3;
    const loc = new Date(date.getTime() + tz * 3600000);
    const jd = julian(loc.getUTCFullYear(), loc.getUTCMonth() + 1, loc.getUTCDate()) - lon / (15 * 24);
    const noon = (t) => fix(12 - sun(jd + t / 24).eqt, 24);
    const angleTime = (angle, t, ccw) => {
      const s = sun(jd + t / 24);
      const h = acos((-sin(angle) - sin(s.decl) * sin(lat)) / (cos(s.decl) * cos(lat))) / 15;
      return noon(t) + (ccw ? -h : h);
    };
    const asrTime = (t) => { const s = sun(jd + t / 24); return angleTime(-acot(1 + tan(Math.abs(lat - s.decl))), t); };
    let T = { fajr: 5, sunrise: 6, dhuhr: 12, asr: 13, maghrib: 18 };
    for (let i = 0; i < 2; i++) {   // два прохода: каждое время уточняется по положению солнца в этот самый час
      T = { fajr: angleTime(18.5, T.fajr, true), sunrise: angleTime(0.833, T.sunrise, true), dhuhr: noon(T.dhuhr),
            asr: asrTime(T.asr), maghrib: angleTime(0.833, T.maghrib) };
    }
    const out = {};
    for (const k in T) out[k] = Math.round((T[k] + tz - lon / 15) * 60);
    out.isha = out.maghrib + (hijriMonth(date, tz) === 9 ? 120 : 90);
    return out;
  }

  const ORDER = ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"];
  // ближайший намаз после момента now: { key, min (минуты от полуночи), at (Date), left (минут осталось) }
  function next(now, lat, lon, tz) {
    if (tz === undefined) tz = 3;
    const nowMin = fix((now.getTime() / 60000) + tz * 60, 1440);
    for (let day = 0; day < 2; day++) {
      const d = new Date(now.getTime() + day * 86400000), t = times(d, lat, lon, tz);
      for (const k of ORDER) {
        if (k === "sunrise") continue;
        const left = t[k] + day * 1440 - nowMin;
        if (left > 0) return { key: k, min: t[k], left: Math.round(left), at: new Date(now.getTime() + left * 60000), friday: new Date(d.getTime() + tz * 3600000).getUTCDay() === 5 };
      }
    }
    return null;
  }
  const hhmm = (m) => String(Math.floor(fix(m, 1440) / 60)).padStart(2, "0") + ":" + String(Math.round(fix(m, 60))).padStart(2, "0");

  window.JurtPrayer = { times, next, hhmm, ORDER, MAKKAH: [21.42251716, 39.82619418], MADINAH: [24.46726, 39.61113] };
})();
