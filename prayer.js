// Время намаза. По умолчанию — метод Умм аль-Кура: официальный календарь Саудовской Аравии, по нему звучит азан в Хараме.
// Фаджр — солнце на 18,5° под горизонтом, иша — через 90 мин после магриба (в Рамадан — через 120),
// аср — когда тень равна предмету (так считает календарь Умм аль-Кура). Расчёт астрономический: расхождение
// с печатным календарём — до 1–2 минут. Общий файл для гида, «Где группа» и «Харам в 3D».
// Другие источники (5-й параметр method) подобраны по их опубликованным расписаниям, сверено 24.10.2026:
//   dumk    — ДУМК (muftyat.kz): фаджр и иша 15°, аср по Абу Ханифе (тень = 2 предмета), поправки +3 мин;
//             совпадает с расписанием Алматы на весь 2026 год до 1 мин.
//   diyanet — Диянет (Турция): фаджр 18°, иша 17°, аср — 1 тень, поправки «темкин»; сверено со Стамбулом.
//   dubai   — Дубай (ОАЭ): фаджр и иша 18,2°, аср — 1 тень, зухр и магриб +3 мин.
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

  // fajr/isha — угол солнца под горизонтом; ishaMin — иша через N минут после магриба; asr — длина тени (1 или 2);
  // adj — поправки в минутах (ихтият), добавляются к расчёту до округления.
  const METHODS = {
    mkk:     { fajr: 18.5, ishaMin: 90, asr: 1 },
    dumk:    { fajr: 15, isha: 15, asr: 2, adj: { sunrise: -3, dhuhr: 3, asr: 3, maghrib: 3 } },
    diyanet: { fajr: 18, isha: 17, asr: 1, adj: { fajr: -0.06, sunrise: -7.1, dhuhr: 5.07, asr: 4.53, maghrib: 7.73, isha: 0.68 } },
    dubai:   { fajr: 18.2, isha: 18.2, asr: 1, adj: { dhuhr: 3, asr: 0.6, maghrib: 3 } }
  };

  // date — любой момент дня; lat/lon — место; tz — часовой пояс (Мекка и Медина: +3);
  // method — ключ из METHODS или свой объект, по умолчанию Умм аль-Кура.
  // Ответ — минуты от полуночи местного времени; asr1 и asr2 — аср по одной и по двум теням.
  function times(date, lat, lon, tz, method) {
    if (tz === undefined) tz = 3;
    const M = (typeof method === "object" && method) || METHODS[method] || METHODS.mkk, adj = M.adj || {};
    const loc = new Date(date.getTime() + tz * 3600000);
    const jd = julian(loc.getUTCFullYear(), loc.getUTCMonth() + 1, loc.getUTCDate()) - lon / (15 * 24);
    const noon = (t) => fix(12 - sun(jd + t / 24).eqt, 24);
    const angleTime = (angle, t, ccw) => {
      const s = sun(jd + t / 24);
      const h = acos((-sin(angle) - sin(s.decl) * sin(lat)) / (cos(s.decl) * cos(lat))) / 15;
      return noon(t) + (ccw ? -h : h);
    };
    const asrTime = (t, f) => { const s = sun(jd + t / 24); return angleTime(-acot(f + tan(Math.abs(lat - s.decl))), t); };
    let T = { fajr: 5, sunrise: 6, dhuhr: 12, asr1: 13, asr2: 14, maghrib: 18, isha: 19 };
    for (let i = 0; i < 2; i++) {   // два прохода: каждое время уточняется по положению солнца в этот самый час
      T = { fajr: angleTime(M.fajr, T.fajr, true), sunrise: angleTime(0.833, T.sunrise, true), dhuhr: noon(T.dhuhr),
            asr1: asrTime(T.asr1, 1), asr2: asrTime(T.asr2, 2), maghrib: angleTime(0.833, T.maghrib),
            isha: M.isha ? angleTime(M.isha, T.isha) : 0 };
    }
    const out = {}, m = (k, a) => Math.round((T[k] + tz - lon / 15) * 60 + (adj[a || k] || 0));
    for (const k of ["fajr", "sunrise", "dhuhr", "maghrib"]) out[k] = m(k);
    out.asr1 = m("asr1", "asr"); out.asr2 = m("asr2", "asr"); out.asr = M.asr === 2 ? out.asr2 : out.asr1;
    out.isha = M.isha ? m("isha") : out.maghrib + (hijriMonth(date, tz) === 9 ? M.ishaMin + 30 : M.ishaMin);
    return out;
  }

  const ORDER = ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"];
  // ближайший намаз после момента now: { key, min (минуты от полуночи), at (Date), left (минут осталось) }
  function next(now, lat, lon, tz, method) {
    if (tz === undefined) tz = 3;
    const nowMin = fix((now.getTime() / 60000) + tz * 60, 1440);
    for (let day = 0; day < 2; day++) {
      const d = new Date(now.getTime() + day * 86400000), t = times(d, lat, lon, tz, method);
      for (const k of ORDER) {
        if (k === "sunrise") continue;
        const left = t[k] + day * 1440 - nowMin;
        if (left > 0) return { key: k, min: t[k], left: Math.round(left), at: new Date(now.getTime() + left * 60000), friday: new Date(d.getTime() + tz * 3600000).getUTCDay() === 5 };
      }
    }
    return null;
  }
  const hhmm = (m) => { const r = fix(Math.round(m), 1440);   // сначала целая минута, иначе 10:59,6 → «10:60»
    return String(Math.floor(r / 60)).padStart(2, "0") + ":" + String(r % 60).padStart(2, "0"); };

  const MAKKAH = [21.42251716, 39.82619418];
  // кибла: направление на Каабу по большому кругу, градусы от истинного севера по часовой стрелке
  function qibla(lat, lon) {
    const dl = MAKKAH[1] - lon;
    return fix(atan2(sin(dl), cos(lat) * tan(MAKKAH[0]) - sin(lat) * cos(dl)), 360);
  }
  // расстояние по поверхности Земли, км
  function km(lat1, lon1, lat2, lon2) {
    if (lat2 === undefined) { lat2 = MAKKAH[0]; lon2 = MAKKAH[1]; }
    const a = Math.pow(sin((lat2 - lat1) / 2), 2) + cos(lat1) * cos(lat2) * Math.pow(sin((lon2 - lon1) / 2), 2);
    return 2 * 6371 * Math.asin(Math.min(1, Math.sqrt(a)));
  }

  window.JurtPrayer = { times, next, hhmm, ORDER, METHODS, qibla, km, MAKKAH, MADINAH: [24.46726, 39.61113] };
})();
