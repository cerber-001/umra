#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборка v3/index.html — единая оболочка гида «Сейчас · Знания · Карта · Я»
из живого index.html (живой файл не трогается).

Запуск:  python3 tools/build_v3.py
Выход:   v3/index.html, v3/manifest.webmanifest
"""
import os, re, sys, json, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'index.html')
OUT_DIR = os.path.join(ROOT, 'v3')
OUT = os.path.join(OUT_DIR, 'index.html')

src = open(SRC, encoding='utf-8').read()

# ---------------------------------------------------------------- сканер тегов
VOID = {'img','br','input','meta','link','hr','source','use','path','circle','line','stop',
        'polyline','polygon','rect','ellipse','wbr','area','col','embed','param','track'}

def scan_tag(s, i):
    """s[i]=='<'. Возвращает (end_index_after_gt, name, closing, selfclosing)."""
    j = i + 1
    closing = s[j] == '/'
    if closing: j += 1
    k = j
    while k < len(s) and (s[k].isalnum() or s[k] in '-_:'): k += 1
    name = s[j:k].lower()
    q = None
    while k < len(s):
        c = s[k]
        if q:
            if c == q: q = None
        elif c in '"\'': q = c
        elif c == '>': break
        k += 1
    selfclosing = s[k-1] == '/'
    return k + 1, name, closing, selfclosing

def outer(id_, s=None):
    """Полный элемент с id=… (баланс тегов)."""
    s = s if s is not None else src
    m = re.search(r'<[a-zA-Z][^<>]*?\sid="%s"[^<>]*>' % re.escape(id_), s)
    if not m: raise SystemExit('нет id ' + id_)
    start = m.start()
    i = start; depth = 0
    while i < len(s):
        if s[i] == '<' and (s[i+1].isalpha() or s[i+1] == '/'):
            if s.startswith('<!--', i):
                i = s.find('-->', i) + 3; continue
            j, name, closing, selfc = scan_tag(s, i)
            if name in ('script','style') and not closing:
                e = s.find('</'+name, j); j, _, _, _ = scan_tag(s, e);
                if depth == 0: return s[start:j]
                i = j; continue
            if closing:
                if name in VOID: i = j; continue   # <circle …></circle>: открывающий не считали — закрывающий тоже
                depth -= 1
                if depth == 0: return s[start:j]
            elif not selfc and name not in VOID:
                depth += 1
            i = j
        else:
            i += 1
    raise SystemExit('не закрыт ' + id_)

def inner(id_, s=None):
    o = outer(id_, s)
    a = o.find('>') + 1
    b = o.rfind('<')
    return o[a:b]

def between(a_re, b_re, s=None, inclusive=False):
    s = s if s is not None else src
    a = re.search(a_re, s); b = re.search(b_re, s[a.end():])
    if not a or not b: raise SystemExit('between: ' + a_re)
    return s[a.start():a.end()+b.end()] if inclusive else s[a.start():a.end()+b.start()]

# ---------------------------------------------------------------- части живого файла
head = src[:src.find('<style>')]
style = src[src.find('<style>'):src.find('</style>')+len('</style>')]
body_start = src.find('<body')
body_open = src[body_start:src.find('>', body_start)+1]
defs1 = re.search(r'<svg width="0" height="0" style="position:absolute"><defs><linearGradient.*?</svg>', src, re.S).group(0)
defs2 = re.search(r'<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>.*?</defs></svg>', src, re.S).group(0)
defs0 = re.search(r'<svg width="0" height="0" style="position:absolute">\n <defs>\n  <symbol id="i-drop".*?</svg>', src, re.S).group(0)
script_pre = re.search(r'<script src="prayer\.js"></script>', src).group(0)
js_m = re.search(r'<script>\s*\(function\(\)\{.*\}\)\(\);\s*</script>', src, re.S)
if not js_m:
    js_m = re.search(r'(<script>(?!\s*src)[\s\S]*?</script>)\s*</body>', src)
js = js_m.group(0)

# блоки по id
v_home = outer('v-home'); v_umra = outer('v-umra'); v_dua = outer('v-dua'); v_prog = outer('v-prog'); v_more = outer('v-more')
overlays = ''.join(outer(i) for i in ['updBar','amanah','toast','lost','lostBig','cele','printArea','dlg','remSheet','wxSheet','prSheet','qbSheet','phBig'])
# элементы без id между overlays (например .ar — арабская подсказка?) — проверим, что ничего важного не потеряли
tail_region = src[src.find(outer('toast'))+len(outer('toast')):src.find('<nav class="tabs">')]
ids_in_tail = set(re.findall(r'\sid="([^"]+)"', tail_region))
known = set(re.findall(r'\sid="([^"]+)"', overlays + defs2 + defs0))
missed = ids_in_tail - known

# ---------------------------------------------------------------- куски «Сейчас»
annBox = outer('annBox'); nowCard = outer('nowCard'); pollBox = outer('pollBox'); regBox = outer('regBox')
installBanner = outer('installBanner'); tripCard = outer('tripCard'); packCard = outer('packCard')
wxCard = outer('wxCard'); prCard = outer('prCard'); homeChatBox = outer('homeChatBox'); swStatus = outer('swStatus')
tiles = re.search(r'<div class="tiles reveal">[\s\S]*?</div>\s*(?=<div[^>]*id="homeChatBox")', v_home)
tiles = tiles.group(0) if tiles else re.search(r'<div class="tiles[^"]*">[\s\S]*?</div>\s*</div>', v_home).group(0)

# ---------------------------------------------------------------- куски «Ещё» → Знания / Я
medina_h2 = re.search(r'<h2 class="sec" id="medina"[^>]*>.*?</h2>\s*<p class="sub"[^>]*>.*?</p>', v_more, re.S).group(0)
medina_cards = v_more[v_more.find(medina_h2)+len(medina_h2):v_more.find('<h2 class="sec" id="pack">')]
pack_h2 = re.search(r'<h2 class="sec" id="pack"[^>]*>.*?</h2>\s*<p class="sub"[^>]*>.*?</p>', v_more, re.S).group(0)
pack_block = v_more[v_more.find(pack_h2)+len(pack_h2):v_more.find(outer('packReset'))+len(outer('packReset'))]
myCard = outer('myCard')
rest_after_my = v_more[v_more.find(myCard)+len(myCard):]
# карточки после «Мои данные»: О гиде, Документы и деньги, Связь и безопасность, Контакты, Настройки, foot
cards_after = re.findall(r'<(?:div|section) class="card[^"]*"[^>]*>[\s\S]*?(?=<(?:div|section) class="card|<p class="foot|\Z)', rest_after_my)
def find_card(txt):
    for c in cards_after:
        if txt in c: return c
    raise SystemExit('нет карточки ' + txt)
about_card = find_card('Чем гид лучше')
docs_card = find_card('Документы и деньги')
safety_card = find_card('Связь и безопасность')
contacts_card = find_card('Контакты')
settings_card = find_card('data-fs="0"')
foot = re.search(r'<p class="foot"[\s\S]*?</p>', rest_after_my).group(0)
# «Памятка» заголовок
memo_h2 = re.search(r'<h2 class="sec"[^>]*>\s*Памятка\s*</h2>(\s*<p class="sub"[^>]*>.*?</p>)?', v_more, re.S)
memo_h2 = memo_h2.group(0) if memo_h2 else '<h2 class="sec">Памятка</h2>'

# ---------------------------------------------------------------- «Умра» → Шаги
umra_in = inner('v-umra')
# убираем ссылку «Харам в 3D» со страницы шагов (3D — только из «Карты», по нажатию)
umra_in = re.sub(r'<a class="mygo h3d"[\s\S]*?</a>', '', umra_in)

# ---------------------------------------------------------------- «Дуа»
dua_in = inner('v-dua')
dua_in = re.sub(r'<h2 class="sec"[^>]*>\s*Дуа\s*</h2>', '', dua_in, count=1)
duaZikr = outer('duaZikr')
dua_wo_zikr = dua_in.replace(duaZikr, '')

# ---------------------------------------------------------------- пути к ресурсам: v3/ лежит на уровень ниже
def repath(h):
    h = re.sub(r'(src|href)="(?!https?:|//|#|mailto:|tel:|sms:|whatsapp:|javascript:|data:|blob:|\.\./|/)(?=[a-zA-Z0-9_])', r'\1="../', h)
    return h

# ---------------------------------------------------------------- новая разметка
NAV = '''<nav class="tabs v3nav">
 <span class="pill" id="pill"></span>
 <button data-tab="home"><svg><use href="#i-star"/></svg><span>Сейчас</span></button>
 <button data-tab="know"><svg><use href="#i-dome"/></svg><span>Знания</span></button>
 <button data-tab="map"><svg><use href="#i-pin"/></svg><span>Карта</span></button>
 <button data-tab="me"><svg><use href="#v3-i-me"/></svg><span>Я</span></button>
</nav>
<div class="v3senior-bar" id="v3seniorBar" hidden>
 <button type="button" id="v3srHome">Сейчас</button>
 <button type="button" class="sos" data-lost>Я потерялся</button>
</div>'''

HEADER = '''<header class="app v3hdr">
 <img class="logo" src="../logo-white.svg" alt="JURT">
 <div class="t"><b id="v3hdrT">Сейчас</b><span id="v3hdrS">Гид паломника</span></div>
 <button class="fs" id="v3mode" aria-label="День или ночь" title="День / ночь">☾</button>
 <button class="fs" id="fsBtn" aria-label="Размер шрифта">Aa</button>
</header>'''

HOME = '''<section class="view on" id="v-home">
 <div class="hero v3greet">
  <div class="hi">Ассаляму алейкум</div>
  <div class="nm" id="heroName">Дорогой паломник</div>
  <div class="phase"><i></i><span id="heroPhase"></span></div>
  <div class="cd" id="heroCd" hidden></div>
  <div class="chips" id="heroChips" hidden></div>
 </div>
 ''' + annBox + '''
 ''' + pollBox + '''
 ''' + nowCard + '''
 <button type="button" class="v3btn v3main" id="v3stepBtn" hidden></button>
 <button type="button" class="v3line" id="v3pw" aria-label="Намаз и погода">
  <span id="v3pwPr">Намаз: время считается…</span><span class="sep">·</span><span id="v3pwWx">погода</span>
 </button>
 <div class="v3line v3mine" id="v3mine">
  <span class="v3mine-t" id="v3mineT">Моё: напоминаний нет</span>
  <button type="button" class="v3mini" id="v3mineAdd">+ добавить</button>
 </div>
 ''' + regBox + '''
 ''' + installBanner + '''
 <div class="card v3ios" id="v3ios" hidden>
  <b>Установить на iPhone — 3 шага</b>
  <ol class="v3steps">
   <li><span>1</span>Внизу Safari нажмите «Поделиться» <i class="v3ico">⎙</i></li>
   <li><span>2</span>Выберите «На экран „Домой“»</li>
   <li><span>3</span>Нажмите «Добавить». Значок «Умра JURT» появится на экране</li>
  </ol>
  <p class="small">Қазақша: «Бөлісу» → «Негізгі экранға» → «Қосу». Гид работает и без установки, из браузера.</p>
  <button type="button" class="v3mini" id="v3iosHide">Понятно, скрыть</button>
 </div>
 ''' + tripCard + '''
 ''' + packCard + '''
 <button type="button" class="v3btn v3sos" data-lost>Я потерялся</button>
 <button type="button" class="v3link" id="v3seniorOn">Режим для старшего</button>
 <div class="tiles reveal v3hidden" hidden>''' + re.sub(r'^<div class="tiles reveal">', '', tiles).rsplit('</div>',1)[0] + '''</div>
 <div class="v3hidden" hidden>''' + homeChatBox + '''</div>
</section>'''

KNOW = '''<section class="view" id="v-know">
 <div class="v3seg" id="v3knowSeg">
  <button type="button" data-kseg="steps" class="on">Шаги</button>
  <button type="button" data-kseg="dua">Дуа</button>
  <button type="button" data-kseg="zikr">Зикр</button>
  <button type="button" data-kseg="pack">Сборы</button>
  <button type="button" data-kseg="medina">Медина</button>
  <button type="button" data-kseg="memo">Памятка</button>
 </div>
 <div class="v3kpane" data-kpane="steps">''' + umra_in + '''</div>
 <div class="v3kpane" data-kpane="dua" hidden>''' + dua_wo_zikr + '''</div>
 <div class="v3kpane" data-kpane="zikr" hidden>''' + duaZikr + '''</div>
 <div class="v3kpane" data-kpane="pack" hidden>''' + pack_h2 + pack_block + '''</div>
 <div class="v3kpane" data-kpane="medina" hidden>''' + medina_h2 + medina_cards + '''</div>
 <div class="v3kpane" data-kpane="memo" hidden>''' + memo_h2 + docs_card + safety_card + '''</div>
</section>'''

MAP = '''<section class="view" id="v-map">
 <div class="card v3where">
  <b class="v3h">Где группа</b>
  <p class="small">Карта показывает своих и точку сбора, пока открыта. Нужен интернет.</p>
  <div class="v3consent" id="v3consent">
   <p>Показывать моё положение группе?</p>
   <div class="v3two">
    <button type="button" data-consent="1">Показывать</button>
    <button type="button" data-consent="0">Не показывать</button>
   </div>
   <p class="small" id="v3consentNote">Выбор хранится в телефоне. Без показа руководитель вас на карте не видит, «Я потерялся» работает.</p>
  </div>
  <a class="v3btn v3main" id="v3whereBtn" href="../where/">Открыть карту группы</a>
 </div>
 <button type="button" class="v3btn v3sos" data-lost>Я потерялся</button>
 <div class="card" id="v3near">
  <b class="v3h">Рядом со мной</b>
  <p class="small" id="v3nearNote">Нажмите «Где я» — покажу ближайшие туалет, аптеку, медпункт и воду с расстоянием. Ворота и Замзам — на карте группы.</p>
  <div class="v3nearList" id="v3nearList"></div>
  <button type="button" class="btn ghost" id="v3nearBtn">Где я</button>
 </div>
 ''' + prCard + '''
 ''' + wxCard + '''
 <div class="card" id="v3d3">
  <b class="v3h">Харам в 3D</b>
  <p class="small">Объёмная модель Харама: Кааба, Макам, Сафа — Марва, ворота. Размер 1,3 МБ, нагревает телефон. Лучше открыть дома по Wi-Fi.</p>
  <a class="btn ghost" href="../haram3d/?from=medina" data-3d>Открыть 3D</a>
 </div>
</section>'''

ME = '''<section class="view" id="v-me">
 ''' + myCard + '''
 <div class="card" id="v3set">
  <b class="v3h">Как показывать</b>
  <div class="v3row"><span>Шрифт</span><div class="v3two3">
   <button type="button" data-fs="0">Обычный</button><button type="button" data-fs="1">Крупный</button><button type="button" data-fs="2">Очень</button></div></div>
  <div class="v3row"><span>Свет</span><div class="v3two3">
   <button type="button" data-theme-set="">Как в телефоне</button><button type="button" data-theme-set="light">День</button><button type="button" data-theme-set="dark">Ночь</button></div></div>
  <div class="v3row"><span>Шаги умры</span><div class="v3two3">
   <button type="button" data-brief-set="1">Кратко</button><button type="button" data-brief-set="0">Подробно</button></div></div>
  <div class="v3row"><span>Язык</span><div class="v3two3">
   <button type="button" class="sel" disabled>Русский</button><button type="button" disabled>Қазақша — после сверки</button></div></div>
  <p class="small">Казахский текст читает носитель, срок — до 05.12.2026. До этого гид на русском.</p>
  <div class="v3row"><span>Режим для старшего</span><div class="v3two3">
   <button type="button" id="v3seniorSet">Включить</button></div></div>
  <p class="small">Самый простой вид: крупно, только «Сейчас» и «Я потерялся». Родственник включает один раз, дальше старший открывает сам.</p>
  <div class="v3hidden" hidden>''' + settings_card + '''</div>
 </div>
 <div class="card" id="v3remind">
  <b class="v3h">Мои напоминания</b>
  <p class="small">Лекарство, еда, звонок домой. Хранится только в телефоне. Звук — на Android; на iPhone только пока гид открыт.</p>
  <div id="v3remList"></div>
  <form class="v3remForm" id="v3remForm">
   <input type="time" id="v3remTime" required aria-label="Время">
   <input type="text" id="v3remText" maxlength="40" placeholder="Что напомнить" required>
   <button type="submit" class="btn">Добавить</button>
  </form>
 </div>
 <div class="card" id="v3prog">
  <b class="v3h">Мой путь</b>
  <div id="v3progTxt"></div>
 </div>
 ''' + contacts_card + '''
 ''' + about_card + '''
 <div class="card" id="v3upd">
  <b class="v3h">Обновление</b>
  <p class="small">Новая версия встаёт сама при следующем открытии. Если что-то выглядит странно — нажмите.</p>
  <button type="button" class="btn ghost" id="v3reload">Обновить гид</button>
  ''' + swStatus + '''
 </div>
 ''' + foot + '''
</section>'''

PROG = v_prog

QUIET = '''<div class="v3quiet" id="v3quiet" hidden>
 <button type="button" class="v3qExit" id="v3qExit">Выйти</button>
 <div class="v3qTop">
  <div class="v3qLab" id="v3qLab">Таваф</div>
  <div class="v3qN" id="v3qN">Круг 0 из 7</div>
  <div class="v3qHint" id="v3qHint">Нажмите внизу, когда круг пройден</div>
 </div>
 <button type="button" class="v3qUndo" id="v3qUndo">Отменить последний</button>
 <button type="button" class="v3qZone" id="v3qZone" aria-label="Круг пройден"><span>Круг пройден</span></button>
</div>
<div class="v3sheet" id="v3d3Sheet" hidden>
 <div class="v3sheet-box">
  <b>Открыть 3D-модель?</b>
  <p>Загрузка 1,3 МБ. Телефон может греться. Лучше дома по Wi-Fi.</p>
  <div class="v3two"><a class="v3btn v3main" id="v3d3Go" href="../haram3d/?from=medina">Открыть</a><button type="button" class="v3btn ghost" id="v3d3No">Не сейчас</button></div>
 </div>
</div>'''

# ---------------------------------------------------------------- CSS v3 (поверх живого)
CSS = r'''
<style id="v3css">
/* ===== v3: единая оболочка — ничего не мигает и не прыгает ===== */
*,*::before,*::after{animation:none!important}
.reveal{opacity:1!important;transform:none!important}
html{font-size:19px}
html[data-fs="1"]{font-size:21.5px}
html[data-fs="2"]{font-size:24px}
body{line-height:1.5}
main{padding:.9rem 1rem 1.2rem;max-width:34rem}
header.app{background:#00292C;padding:calc(.5rem + env(safe-area-inset-top)) .9rem .5rem}
header.app::after{display:none}
header.app .t{border-left:2px solid rgba(255,255,255,.3);padding-left:.6rem;line-height:1.15}
header.app .t b{font-size:1.25rem;display:block}
header.app .t span{font-size:.75rem;opacity:.85}
header.app .fs{min-width:2.6rem;min-height:2.6rem;font-size:1rem;display:flex;align-items:center;justify-content:center;padding:0 .4rem}
header.app #v3mode{font-size:1.2rem}
.view{gap:.8rem}
.view.on{animation:none}
.card{border-radius:1rem}
.v3h{font-size:1.05rem;font-weight:800;color:var(--teal-d)}
.hero.v3greet{animation:none;transition:none}
.hero.v3greet .nm{font-size:1.7rem;line-height:1.15}
.hero.v3greet .phase{font-size:1rem}
.hero.v3greet .cd .u b{font-size:1.6rem}
.hero.v3greet .cd .u{min-width:3.6rem;padding:.3rem .5rem}
.hero.v3greet .cd .when{font-size:.95rem}
.hero.v3greet .cd a{font-size:1rem;padding:.55rem .9rem;min-height:3rem;display:inline-flex;align-items:center}
/* карточка «Сейчас» — главная */
.now{border:2px solid var(--line);padding:1rem 1rem 1rem}
.now.live{border-color:var(--orange)}
.now-w{font-size:1.45rem;line-height:1.2}
.now-t{font-size:1.05rem}
.now-p{font-size:.95rem}
.now-next{font-size:.95rem}
.now-acts{display:flex;flex-direction:column;gap:.5rem}
.now-acts .btn{min-height:3.2rem;font-size:1.05rem;min-width:0;width:100%}
.now-acts #nowDay{background:var(--teal);color:#fff}
.now-acts #nowMore{background:transparent;border:0;color:var(--teal-d);text-decoration:underline;min-height:2.4rem;font-weight:700}
/* кнопки v3 */
.v3btn{display:flex;align-items:center;justify-content:center;gap:.4rem;min-height:3.2rem;border-radius:1rem;font-weight:800;font-size:1.05rem;padding:.6rem 1rem;text-decoration:none;width:100%;box-sizing:border-box;border:0;font-family:inherit;cursor:pointer}
.v3btn.v3main{background:var(--teal);color:#fff}
.v3btn.ghost{background:var(--card);color:var(--teal-d);border:2px solid var(--teal)}
.v3btn.v3sos{background:var(--redbg);color:var(--red);border:2px solid var(--red)}
.v3link{background:none;border:0;color:var(--muted);font-weight:700;font-size:.95rem;text-decoration:underline;min-height:2.8rem;font-family:inherit}
.v3mini{background:none;border:1.5px solid var(--line);border-radius:.7rem;color:var(--teal-d);font-weight:700;font-size:.9rem;min-height:2.4rem;padding:0 .7rem;font-family:inherit}
/* строка «намаз · погода» и «Моё» */
.v3line{display:flex;align-items:center;gap:.5rem;min-height:3.2rem;background:var(--card);border-radius:1rem;box-shadow:var(--shadow);padding:.6rem .9rem;font-size:1rem;color:var(--ink);text-align:left;border:0;width:100%;font-family:inherit;flex-wrap:wrap;box-sizing:border-box}
.v3line .sep{color:var(--muted)}
.v3line b{color:var(--teal-d)}
.v3mine .v3mine-t{flex:1}
/* плитки — один столбец */
.tiles{grid-template-columns:1fr}
/* iPhone установка */
.v3steps{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:.5rem}
.v3steps li{display:flex;gap:.6rem;align-items:center}
.v3steps li span{flex:none;width:1.9rem;height:1.9rem;border-radius:50%;background:var(--teal);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:800}
.v3ico{font-style:normal;color:var(--teal-d)}
/* «Знания» — сегменты */
.v3seg{display:flex;gap:.35rem;overflow-x:auto;padding:.1rem .1rem .35rem;scrollbar-width:none;-webkit-overflow-scrolling:touch}
.v3seg::-webkit-scrollbar{display:none}
.v3seg button{flex:none;min-height:2.9rem;padding:0 1rem;border-radius:1rem;border:2px solid var(--line);background:var(--card);color:var(--teal-d);font-weight:800;font-size:1rem;font-family:inherit}
.v3seg button.on{background:var(--teal);border-color:var(--teal);color:#fff}
.v3kpane{display:flex;flex-direction:column;gap:.85rem}
.v3kpane .back{display:none}
.dseg button[data-dseg="zikr"]{display:none}
.v3kpane h2.sec{font-size:1.3rem}
/* «Карта» */
.v3consent p{margin:0 0 .5rem;font-weight:700}
.v3two{display:flex;gap:.5rem}
.v3two>*{flex:1;min-height:3.2rem;border-radius:1rem;border:2px solid var(--teal);background:var(--card);color:var(--teal-d);font-weight:800;font-size:1rem;font-family:inherit;display:flex;align-items:center;justify-content:center;text-decoration:none}
.v3two>.sel{background:var(--teal);color:#fff}
.v3nearList{display:flex;flex-direction:column;gap:.4rem}
.v3nearList div{display:flex;justify-content:space-between;gap:.6rem;padding:.45rem 0;border-bottom:1px solid var(--line);font-size:1rem}
.v3nearList div b{color:var(--teal-d);white-space:nowrap}
/* «Я» */
.v3row{display:flex;flex-direction:column;gap:.35rem;padding:.35rem 0}
.v3row>span{font-weight:700;color:var(--muted);font-size:.9rem}
.v3two3{display:flex;gap:.4rem;flex-wrap:wrap}
.v3two3 button{flex:1;min-height:2.9rem;border-radius:.9rem;border:2px solid var(--line);background:var(--card);color:var(--teal-d);font-weight:800;font-size:.95rem;font-family:inherit;padding:0 .6rem}
.v3two3 button.sel,.v3two3 button.on{background:var(--teal);border-color:var(--teal);color:#fff}
.v3two3 button:disabled{opacity:.55}
.v3remForm{display:flex;gap:.4rem;flex-wrap:wrap}
.v3remForm input{min-height:2.9rem;border:2px solid var(--line);border-radius:.8rem;padding:0 .6rem;font:inherit;background:var(--card);color:var(--ink)}
.v3remForm input[type=text]{flex:1;min-width:9rem}
.v3remForm .btn{flex:none;min-width:0;min-height:2.9rem}
#v3remList div{display:flex;justify-content:space-between;align-items:center;gap:.5rem;padding:.4rem 0;border-bottom:1px solid var(--line)}
#v3remList button{background:none;border:0;color:var(--red);font-weight:700;font-family:inherit;min-height:2.4rem}
.v3hidden{display:none!important}
/* завершённое голосование — свёрнуто */
#pollBox.v3done:not(.v3open){max-height:4.2rem;overflow:hidden;position:relative;cursor:pointer;opacity:.9}
#pollBox.v3done:not(.v3open)::after{content:'Итоги голосования — нажмите';position:absolute;left:0;right:0;bottom:0;padding:.5rem 1rem;background:var(--card);color:var(--muted);font-size:.95rem;font-weight:700}
/* нижние вкладки — 4 */
nav.tabs{grid-template-columns:repeat(4,1fr)}
nav.tabs .pill{width:calc((100% - .6rem)/4)}
nav.tabs button{font-size:.78rem;min-height:3.7rem}
nav.tabs button svg{transform:none!important}
nav.tabs button.on svg{transform:none!important}
/* режим «для старшего» */
.v3senior-bar{position:fixed;left:0;right:0;bottom:0;z-index:30;display:flex;gap:.5rem;padding:.5rem .7rem calc(.5rem + env(safe-area-inset-bottom));background:var(--card);box-shadow:0 -4px 20px rgba(0,0,0,.08)}
.v3senior-bar button{flex:1;min-height:3.6rem;border-radius:1rem;border:0;background:var(--teal);color:#fff;font-weight:800;font-size:1.15rem;font-family:inherit}
.v3senior-bar button.sos{background:var(--redbg);color:var(--red);border:2px solid var(--red)}
html.v3senior nav.tabs{display:none}
html.v3senior .v3senior-bar{display:flex}
html.v3senior #v-home>*:not(.v3greet):not(#nowCard):not(#annBox):not(#v3pw):not(#v3mine):not(#v3stepBtn):not(#v3seniorOn):not(.v3sos){display:none!important}
html.v3senior #v3seniorOn{font-size:1rem}
html.v3senior header.app .fs#v3mode{display:none}
/* режим «тишина» */
.v3quiet{position:fixed;inset:0;z-index:70;background:#050807;color:#d9d4c7;display:flex;flex-direction:column}
.v3quiet[hidden]{display:none}
.v3qExit{position:absolute;top:calc(.6rem + env(safe-area-inset-top));right:.8rem;background:none;border:1px solid #444;color:#aaa;border-radius:.7rem;min-height:2.6rem;padding:0 .9rem;font-family:inherit;font-weight:700}
.v3qTop{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.5rem;padding:1rem}
.v3qLab{font-size:1rem;color:#8a9a9c}
.v3qN{font-size:2.4rem;font-weight:800;color:#f4ede1}
.v3qHint{font-size:.95rem;color:#8a9a9c;text-align:center}
.v3qUndo{margin:0 1rem .8rem;min-height:3.4rem;border-radius:1rem;border:2px solid #555;background:#111;color:#ddd;font-size:1.1rem;font-weight:800;font-family:inherit}
.v3qZone{height:46vh;margin:0 .6rem calc(.6rem + env(safe-area-inset-bottom));border-radius:1.3rem;border:2px dashed #2b3b3a;background:#0b1413;color:#9fb5b3;font-size:1.3rem;font-weight:800;font-family:inherit}
.v3qZone:active{background:#123}
/* лист «3D?» */
.v3sheet{position:fixed;inset:0;z-index:60;background:rgba(0,20,22,.55);display:flex;align-items:flex-end;justify-content:center}
.v3sheet[hidden]{display:none}
.v3sheet-box{background:var(--card);color:var(--ink);border-radius:1.3rem 1.3rem 0 0;padding:1.2rem 1rem calc(1rem + env(safe-area-inset-bottom));width:100%;max-width:34rem;display:flex;flex-direction:column;gap:.7rem}
/* кнопка «режим тишины» внутри счётчика */
.v3qBtn{width:100%;min-height:3rem;border-radius:.9rem;border:2px solid var(--line);background:var(--card);color:var(--teal-d);font-weight:800;font-family:inherit;font-size:1rem;margin-top:.4rem}
/* «весь путь» — страница */
#v-prog .back{display:flex}
</style>
'''

# ---------------------------------------------------------------- JS: правки живого скрипта
def patch(js, old, new, cnt=1, label=''):
    if old not in js: raise SystemExit('патч не найден: ' + (label or old[:60]))
    return js.replace(old, new, cnt)

js = patch(js, "TABS=['home','umra','dua','map','more'], VIEWS=['home','umra','dua','prog','more'];",
           "TABS=['home','know','map','me'], VIEWS=['home','know','map','me','prog'];", label='TABS')
js = patch(js, "if(tab==='map'){ location.href='where/'; return; }", "", label='map redirect')
js = patch(js, "  reveal();\n}\n$$('nav.tabs button')", "  reveal();\n  if(window.v3onShow) window.v3onShow(tab, anchor);\n}\nwindow.v3={show:show};\n$$('nav.tabs button')", label='show hook')
js = patch(js, "show('more','myCard')", "show('me','myCard')", cnt=0 if "show('more','myCard')" not in js else js.count("show('more','myCard')"), label='polls go code') if "show('more','myCard')" in js else js
js = js.replace("'program/program.json'", "'../program/program.json'")
js = js.replace('"program/program.json"', '"../program/program.json"')
js = js.replace("haram3d/?from=medina", "../haram3d/?from=medina")
js = js.replace("navigator.serviceWorker.register('/sw.js')", "Promise.reject(new Error('v3: без service worker'))")
# экспорт нужных функций наружу (в конец IIFE)
EXPORT = """
  window.v3api={get:get,set:set,openLost:openLost,applyFs:applyFs,applyTheme:applyTheme,dayIdx:dayIdx,segTo:segTo,toast:toast,today:today,nowMin:nowMin,progRows:progRows,wxLoad:wxLoad,WXC:WXC,wxDaily:wxDaily,wxDay:wxDay,wxToday:wxToday,wxI:wxI,buzz:buzz,renderData:renderData,PRN:typeof PRN!=='undefined'?PRN:null};
})();"""
idx = js.rfind('})();')
js = js[:idx] + EXPORT + js[idx+5:]

# data-go в разметке: umra/dua/more → know/me
def remap_go(h):
    h = h.replace('data-go="umra"', 'data-go="know" data-kseg="steps"')
    h = re.sub(r'data-go="dua"( data-seg="(\w+)")?', lambda m: 'data-go="know" data-kseg="%s"' % ('zikr' if m.group(2)=='zikr' else 'dua') + (' data-seg="%s"' % m.group(2) if m.group(2) and m.group(2)!='zikr' else ''), h)
    h = h.replace('data-go="more" data-anchor="pack"', 'data-go="know" data-kseg="pack" data-anchor="pack"')
    h = h.replace('data-go="more" data-anchor="medina"', 'data-go="know" data-kseg="medina" data-anchor="medina"')
    h = h.replace('data-go="more"', 'data-go="me"')
    return h

# ---------------------------------------------------------------- JS v3
V3JS = r'''
<script>
(function(){
  var A=window.v3api, $=function(s,r){return (r||document).querySelector(s);}, $$=function(s,r){return Array.prototype.slice.call((r||document).querySelectorAll(s));};
  var root=document.documentElement;
  var TITLES={home:'Сейчас',know:'Знания',map:'Карта',me:'Я',prog:'Весь путь'};
  function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }

  /* ---- шапка: заголовок = вкладка, подзаголовок = день · город ---- */
  function hdr(tab){
    $('#v3hdrT').textContent=TITLES[tab]||'Сейчас';
    var ph=$('#heroPhase').textContent||''; $('#v3hdrS').textContent = ph ? ph : 'Гид паломника';
  }
  /* ---- «Знания»: сегменты ---- */
  function kseg(w, anchor){
    if(!w) w=A.get('v3kseg','steps');
    $$('#v3knowSeg button').forEach(function(b){ b.classList.toggle('on', b.getAttribute('data-kseg')===w); });
    $$('.v3kpane').forEach(function(p){ p.hidden = p.getAttribute('data-kpane')!==w; });
    A.set('v3kseg',w);
    if(w==='dua'){ var s=A.get('duaSeg','guide'); A.segTo(s==='mine'?'mine':'guide'); }
    if(w==='zikr'){ A.segTo('zikr'); }
    if(anchor){ var a=document.getElementById(anchor); if(a) setTimeout(function(){ a.scrollIntoView({behavior:'smooth',block:'start'}); },60); }
  }
  $$('#v3knowSeg button').forEach(function(b){ b.onclick=function(){ A.buzz(6); kseg(b.getAttribute('data-kseg')); window.scrollTo(0,0); }; });
  $$('[data-kseg][data-go]').forEach(function(b){ b.addEventListener('click',function(){ setTimeout(function(){ kseg(b.getAttribute('data-kseg'), b.getAttribute('data-anchor')); },0); }); });
  /* ---- слова старого интерфейса в текстах программы ---- */
  var WORDS=[[/«Ещё»\s*→\s*«Сборы»/g,'«Знания» → «Сборы»'],[/вкладка «Ещё»/g,'вкладка «Знания»'],[/вкладке «Ещё»/g,'вкладке «Знания»'],[/«Ещё»/g,'«Я»']];
  function words(){
    ['#v-prog','#nowCard','#tripCard','#v-know','#v-me'].forEach(function(sel){
      var root=$(sel); if(!root) return;
      var w=document.createTreeWalker(root, NodeFilter.SHOW_TEXT), n, list=[];
      while((n=w.nextNode())) if(n.nodeValue.indexOf('«Ещё»')>=0) list.push(n);
      list.forEach(function(t){ var v=t.nodeValue; WORDS.forEach(function(p){ v=v.replace(p[0],p[1]); }); t.nodeValue=v; });
    });
  }
  window.v3onShow=function(tab, anchor){
    hdr(tab); setTimeout(words, 50);
    if(tab==='know'){ kseg(A.get('v3kseg','steps'), null); }
    if(tab==='home'){ stepBtn(); pw(); mine(); }
    if(tab==='me'){ progTxt(); remList(); setSel(); }
    if(tab==='map'){ consent(); }
  };

  /* ---- «Сейчас»: одна главная кнопка — текущий шаг умры в дни Мекки ---- */
  var STEPS=$$('#v-know .acc.step[data-id]').map(function(s){ return {id:s.getAttribute('data-id'), el:s, name:($('.acc-h b',s)||$('.acc-h',s)||{}).textContent||''}; });
  function stepBtn(){
    var b=$('#v3stepBtn'); if(!b) return;
    var di=A.dayIdx(), done=A.get('done',{})||{};
    var next=null; for(var i=0;i<STEPS.length;i++){ if(!done[STEPS[i].id]){ next=STEPS[i]; break; } }
    /* дни умры: 01.11 = индекс 4 (28,29,30,31 → 0..3); в Мекке 01–04.11 → 4..7 */
    var inMecca = di>=3 && di<=7;
    if(!inMecca || !next){ b.hidden=true; return; }
    b.hidden=false; b.textContent = 'Шаг '+(STEPS.indexOf(next)+1)+' из '+STEPS.length+': '+next.name.replace(/\s+/g,' ').trim();
    b.onclick=function(){ A.buzz(8); A.set('v3kseg','steps'); window.v3.show('know', null); setTimeout(function(){ kseg('steps', null); next.el.scrollIntoView({behavior:'smooth',block:'start'}); var h=$('.acc-h',next.el); if(h && !next.el.classList.contains('open')) h.click(); },80); };
  }
  /* ---- строка «намаз · погода» ---- */
  function pw(){
    var pr=$('#prNext'), wx=$('#wxBox button.now b'), wxi=$('#wxBox button.now .ic');
    var t=pr?Array.prototype.map.call(pr.childNodes,function(n){ return n.textContent.trim(); }).filter(Boolean).join(' · ').replace(/\s+/g,' '):'';
    $('#v3pwPr').textContent = t || 'Намаз: откройте «Карта»';
    $('#v3pwWx').textContent = wx ? (wxi?wxi.textContent+' ':'')+wx.textContent+' сегодня' : 'погода — в «Карте»';
  }
  $('#v3pw').onclick=function(){ A.buzz(6); window.v3.show('map','prCard'); };
  setInterval(pw, 60000);

  /* ---- «Моё»: напоминания в телефоне ---- */
  function rems(){ return A.get('v3rem',[])||[]; }
  function mine(){
    var r=rems().slice().sort(function(a,b){ return a.t<b.t?-1:1; }), now=A.nowMin(), nxt=null;
    for(var i=0;i<r.length;i++){ var m=+r[i].t.slice(0,2)*60 + +r[i].t.slice(3,5); if(m>=now){ nxt=r[i]; break; } }
    if(!nxt && r.length) nxt=r[0];
    $('#v3mineT').innerHTML = nxt ? 'Моё: <b>'+esc(nxt.t)+'</b> — '+esc(nxt.x) : 'Моё: напоминаний нет';
  }
  $('#v3mineAdd').onclick=function(){ A.buzz(6); window.v3.show('me','v3remind'); setTimeout(function(){ $('#v3remTime').focus(); },300); };
  function remList(){
    var box=$('#v3remList'), r=rems().slice().sort(function(a,b){ return a.t<b.t?-1:1; });
    box.innerHTML = r.length ? r.map(function(x,i){ return '<div><span><b>'+esc(x.t)+'</b> — '+esc(x.x)+'</span><button type="button" data-rem-del="'+i+'">Убрать</button></div>'; }).join('') : '<p class="small">Пока пусто. Например: 14:00 — лекарство.</p>';
    $$('[data-rem-del]',box).forEach(function(b){ b.onclick=function(){ var all=rems().slice().sort(function(a,c){ return a.t<c.t?-1:1; }); all.splice(+b.getAttribute('data-rem-del'),1); A.set('v3rem',all); remList(); mine(); }; });
  }
  $('#v3remForm').onsubmit=function(e){ e.preventDefault(); var t=$('#v3remTime').value, x=$('#v3remText').value.trim(); if(!t||!x) return; var all=rems(); all.push({t:t,x:x,fired:''}); A.set('v3rem',all); $('#v3remText').value=''; remList(); mine(); A.toast('Напоминание добавлено'); };
  /* сработка, пока гид открыт: вибрация + уведомление, если разрешено (Android) */
  function remTick(){
    var all=rems(), now=A.nowMin(), d=A.today(), ch=false;
    all.forEach(function(x){ var m=+x.t.slice(0,2)*60 + +x.t.slice(3,5); if(m===now && x.fired!==d){ x.fired=d; ch=true; A.buzz([200,100,200]); A.toast(x.t+' — '+x.x); if(window.Notification && Notification.permission==='granted'){ try{ new Notification('Гид JURT · '+x.t, {body:x.x}); }catch(e){} } } });
    if(ch) A.set('v3rem',all);
  }
  setInterval(remTick, 30000);
  if(window.Notification && Notification.permission==='default' && rems().length && !/iPhone|iPad/.test(navigator.userAgent)){ try{ Notification.requestPermission(); }catch(e){} }

  /* ---- установка на iPhone: 3 шага (только Safari iOS, не установлено) ---- */
  (function(){ var ios=/iPhone|iPad|iPod/.test(navigator.userAgent), sa=window.navigator.standalone===true || matchMedia('(display-mode: standalone)').matches;
    var c=$('#v3ios'); if(ios && !sa && !A.get('v3iosHide',0)) c.hidden=false;
    $('#v3iosHide').onclick=function(){ A.set('v3iosHide',1); c.hidden=true; }; })();

  /* ---- день / ночь в шапке ---- */
  function modeIcon(){ var t=A.get('theme',''); var dark = t==='dark' || (!t && matchMedia('(prefers-color-scheme: dark)').matches); $('#v3mode').textContent = dark ? '☀' : '☾'; }
  $('#v3mode').onclick=function(){ A.buzz(6); var t=A.get('theme',''); var dark = t==='dark' || (!t && matchMedia('(prefers-color-scheme: dark)').matches); A.applyTheme(dark?'light':'dark'); modeIcon(); setSel(); };
  modeIcon();
  function setSel(){
    var fs=String(A.get('fs',0)), th=A.get('theme',''), br=String(A.get('brief',0)?1:0);
    $$('#v3set [data-fs]').forEach(function(b){ b.classList.toggle('sel', b.getAttribute('data-fs')===fs); });
    $$('#v3set [data-theme-set]').forEach(function(b){ b.classList.toggle('sel', b.getAttribute('data-theme-set')===th); });
    $$('#v3set [data-brief-set]').forEach(function(b){ b.classList.toggle('sel', b.getAttribute('data-brief-set')===br); });
    $('#v3seniorSet').textContent = root.classList.contains('v3senior') ? 'Выключить' : 'Включить';
    $('#v3seniorSet').classList.toggle('sel', root.classList.contains('v3senior'));
  }
  $$('#v3set [data-fs]').forEach(function(b){ b.onclick=function(){ A.buzz(6); A.applyFs(+b.getAttribute('data-fs')); setSel(); }; });
  $$('#v3set [data-theme-set]').forEach(function(b){ b.onclick=function(){ A.buzz(6); A.applyTheme(b.getAttribute('data-theme-set')); modeIcon(); setSel(); }; });
  $$('#v3set [data-brief-set]').forEach(function(b){ b.onclick=function(){ A.buzz(6); var src=$('.v3hidden [data-brief-set="'+b.getAttribute('data-brief-set')+'"]'); if(src) src.click(); setSel(); }; });

  /* ---- режим «для старшего» ---- */
  function senior(on){
    root.classList.toggle('v3senior', !!on); A.set('v3senior', on?1:0);
    $('#v3seniorBar').hidden=!on;
    $('#v3seniorOn').textContent = on ? 'Обычный вид' : 'Режим для старшего';
    if(on){ if(A.get('fs',0)<2){ A.set('v3fsPrev',A.get('fs',0)); A.applyFs(2); } window.v3.show('home'); }
    else { var p=A.get('v3fsPrev',null); if(p!==null){ A.applyFs(p); A.set('v3fsPrev',null); } }
    setSel();
  }
  $('#v3seniorOn').onclick=function(){ A.buzz(8); senior(!root.classList.contains('v3senior')); };
  $('#v3seniorSet').onclick=function(){ A.buzz(8); senior(!root.classList.contains('v3senior')); };
  $('#v3srHome').onclick=function(){ A.buzz(6); window.v3.show('home'); };
  if(A.get('v3senior',0)) senior(true);

  /* ---- «Карта»: согласие двумя кнопками, ничего не выбрано заранее ---- */
  function consent(){
    var c=A.get('v3consent',null);
    $$('#v3consent [data-consent]').forEach(function(b){ b.classList.toggle('sel', c!==null && String(c)===b.getAttribute('data-consent')); });
    $('#v3whereBtn').classList.toggle('ghost', c===null); $('#v3whereBtn').classList.toggle('v3main', c!==null);
    $('#v3consentNote').textContent = c===null ? 'Сначала выберите. Выбор хранится в телефоне, менять можно в любой момент.' : (c==='1' ? 'Положение видно группе, пока карта открыта. Выбор хранится в телефоне.' : 'Группа ваше положение не видит. «Я потерялся» работает.');
  }
  $$('#v3consent [data-consent]').forEach(function(b){ b.onclick=function(){ A.buzz(6); var v=b.getAttribute('data-consent'); A.set('v3consent',v); try{ localStorage.setItem('where.share', v==='1'?'true':'false'); }catch(e){} consent(); }; });
  $('#v3whereBtn').onclick=function(e){ if(A.get('v3consent',null)===null){ e.preventDefault(); A.toast('Сначала выберите: показывать или нет'); $('#v3consent').scrollIntoView({behavior:'smooth'}); } };

  /* ---- «Рядом со мной»: ближайшие точки из OSM (без ворот — их координат пока нет) ---- */
  var KIND={wc:'Туалет',wc_m:'Туалет (муж.)',wc_f:'Туалет (жен.)',pharm:'Аптека',med:'Медпункт',water:'Вода',salon:'Парикмахер (бритьё)'};
  function km(a,b,c,d){ var R=6371000, p=Math.PI/180, x=(c-a)*p, y=(d-b)*p, s=Math.sin(x/2)*Math.sin(x/2)+Math.cos(a*p)*Math.cos(c*p)*Math.sin(y/2)*Math.sin(y/2); return 2*R*Math.asin(Math.sqrt(s)); }
  $('#v3nearBtn').onclick=function(){
    var btn=this, note=$('#v3nearNote'), list=$('#v3nearList'); A.buzz(6);
    if(!navigator.geolocation){ note.textContent='Телефон не даёт положение.'; return; }
    btn.disabled=true; note.textContent='Определяю, где вы…';
    navigator.geolocation.getCurrentPosition(function(pos){
      var la=pos.coords.latitude, lo=pos.coords.longitude;
      var city = km(la,lo,24.46726,39.61113) < km(la,lo,21.42251716,39.82619418) ? 'medina' : 'mecca';
      fetch('../where/osm/poi_'+city+'.json').then(function(r){ return r.json(); }).then(function(pts){
        var best={};
        pts.forEach(function(p){ var d=km(la,lo,p.lat,p.lon); var g=p.k==='wc_m'||p.k==='wc_f'?p.k:p.k; if(!best[g]||d<best[g].d) best[g]={d:d,p:p}; });
        var order=['wc','wc_m','wc_f','water','pharm','med','salon'];
        list.innerHTML=order.filter(function(k){ return best[k]; }).map(function(k){ var b=best[k]; return '<div><span>'+KIND[k]+(b.p.n?' · '+esc(b.p.n):'')+'</span><b>'+(b.d<1000?Math.round(b.d)+' м':(b.d/1000).toFixed(1)+' км')+'</b></div>'; }).join('') || '<p class="small">Рядом точек нет.</p>';
        note.textContent=(city==='medina'?'Медина':'Мекка')+' · точность ±'+Math.round(pos.coords.accuracy)+' м. Ворота и Замзам — на карте группы.'; btn.disabled=false; btn.textContent='Обновить';
      }).catch(function(){ note.textContent='Список точек не загрузился — нужен интернет один раз.'; btn.disabled=false; });
    }, function(){ note.textContent='Положение не получено. Разрешите доступ к геопозиции в настройках телефона.'; btn.disabled=false; }, {enableHighAccuracy:true, timeout:15000, maximumAge:30000});
  };

  /* ---- 3D только по нажатию, с предупреждением ---- */
  function d3Ask(href){ $('#v3d3Go').setAttribute('href', href); $('#v3d3Sheet').hidden=false; }
  $('#v3d3No').onclick=function(){ $('#v3d3Sheet').hidden=true; };
  $('#v3d3Sheet').onclick=function(e){ if(e.target===this) this.hidden=true; };
  document.addEventListener('click', function(e){ var a=e.target.closest && e.target.closest('a[href*="haram3d"]'); if(a && a.id!=='v3d3Go'){ e.preventDefault(); d3Ask(a.getAttribute('href')); } }, true);

  /* ---- режим «тишина» в тавафе и саи ---- */
  var qc=null, qObs=null;
  try{ qObs=new MutationObserver(function(){ qPaint(); }); }catch(e){}
  function qWatch(c){ if(!qObs) return; qObs.disconnect(); if(c) qObs.observe(c,{subtree:true,childList:true,characterData:true,attributes:true}); }
  function qPaint(){ if(!qc) return; var n=($('.n',qc)||{}).textContent||'0'; n=parseInt(n,10)||0; var tot=qc.getAttribute('data-id')==='sai'?7:7; $('#v3qN').textContent='Круг '+n+' из '+tot; if(n>=tot){ $('#v3qHint').textContent='Все круги пройдены. Можно выйти.'; } else $('#v3qHint').textContent='Нажмите внизу, когда круг пройден'; }
  $$('.counter').forEach(function(c){
    var b=document.createElement('button'); b.type='button'; b.className='v3qBtn'; b.textContent='Режим тишины: тёмный экран, счёт кругов';
    b.onclick=function(){ qc=c; qWatch(c); $('#v3qLab').textContent = c.getAttribute('data-id')==='sai' ? 'Саи · Сафа — Марва' : 'Таваф'; $('#v3quiet').hidden=false; qPaint(); try{ if(screen.orientation&&screen.orientation.lock) screen.orientation.lock('portrait').catch(function(){}); }catch(e){} };
    c.appendChild(b);
  });
  $('#v3qZone').onclick=function(){ if(!qc) return; var r=$('.ringbtn',qc); if(r) r.click(); A.buzz(30); setTimeout(qPaint,30); };
  $('#v3qUndo').onclick=function(){ if(!qc) return; var m=$('.minus',qc); if(m) m.click(); A.buzz(10); setTimeout(qPaint,30); };
  $('#v3qExit').onclick=function(){ $('#v3quiet').hidden=true; qc=null; qWatch(null); };

  /* ---- «Я»: мой путь ---- */
  function progTxt(){
    var done=A.get('done',{})||{}, n=STEPS.filter(function(s){ return done[s.id]; }).length;
    var tw=A.get('cnt-tawaf',0)||0, sa=A.get('cnt-sai',0)||0, pk=0; for(var i=1;i<=59;i++) if(A.get('pk-'+i,0)) pk++;
    $('#v3progTxt').innerHTML='<p>Шаги умры: <b>'+n+' из '+STEPS.length+'</b></p><p>Таваф: <b>'+tw+' из 7</b> · Саи: <b>'+sa+' из 7</b></p><p>Сборы: <b>'+pk+' из 59</b></p><p class="small">Хранится в телефоне. Новый телефон — прогресс заново.</p>';
  }
  $('#v3reload').onclick=function(){ A.buzz(6); location.reload(); };

  /* ---- старт ---- */
  var tab=A.get('tab','home'); if(['home','know','map','me','prog'].indexOf(tab)<0) tab='home';
  window.v3.show(tab);
  if(A.get('v3senior',0)) window.v3.show('home');
  setTimeout(function(){ pw(); mine(); stepBtn(); hdr(A.get('tab','home')); }, 400);
  setTimeout(function(){ pw(); hdr(A.get('tab','home')); words(); }, 2500);
  setTimeout(words, 800); setTimeout(words, 6000);
  (function(){ var t=null; var mo=new MutationObserver(function(){ clearTimeout(t); t=setTimeout(function(){ words(); pollDone(); },60); });
    ['#v-prog','#nowCard','#tripCard','#pollBox'].forEach(function(sel){ var el=$(sel); if(el) mo.observe(el,{childList:true,subtree:true,characterData:true}); }); })();
  /* завершённое голосование на «Сейчас» — одной строкой, раскрывается по нажатию */
  function pollDone(){
    var box=$('#pollBox'); if(!box) return;
    var done=/завершено/i.test(box.textContent||'') && !/голосуйте|ваш голос|выберите/i.test(box.textContent||'');
    box.classList.toggle('v3done', done);
    if(done && !box.v3bound){ box.v3bound=true; box.addEventListener('click', function(e){ if(box.classList.contains('v3done') && !box.classList.contains('v3open')){ box.classList.add('v3open'); e.preventDefault(); e.stopPropagation(); } }, true); }
  }
  pollDone(); setTimeout(pollDone, 3000);
})();
</script>
'''

# ---------------------------------------------------------------- сборка
head_v3 = head
head_v3 = head_v3.replace('<title>Гид паломника JURT</title>', '<title>Гид паломника JURT · v3</title>')
head_v3 = head_v3.replace('href="manifest.webmanifest"', 'href="manifest.webmanifest"')  # свой манифест в v3/
head_v3 = re.sub(r'href="(favicon\.png|icon-192\.png|apple-touch-icon\.png)"', r'href="../\1"', head_v3)
head_v3 = head_v3.replace('content="https://umra.jurt.kz/"', 'content="https://umra.jurt.kz/v3/"')
head_v3 = head_v3.replace('<meta name="robots" content="noai, noimageai">', '<meta name="robots" content="noindex, noai, noimageai">')
style_v3 = re.sub(r'url\((["\']?)(?!https?:|data:|\.\./|/)([a-zA-Z0-9_-]+\.woff2)', r'url(\1../\2', style)

body = '\n'.join([
    defs1,
    defs0,
    HEADER,
    '<main>',
    remap_go(repath(HOME)),
    remap_go(repath(KNOW)),
    remap_go(repath(MAP)),
    remap_go(repath(ME)),
    remap_go(repath(PROG)),
    '</main>',
    remap_go(repath(overlays)),
    defs2.replace('</defs></svg>', '<symbol id="v3-i-me" viewBox="0 0 48 48"><circle cx="24" cy="17" r="8" fill="none" stroke="currentColor" stroke-width="2.6"/><path d="M8 42c2-9 8-13 16-13s14 4 16 13" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"/></symbol></defs></svg>'),
    QUIET,
    NAV,
    '<script src="../prayer.js"></script>',
    js,
    V3JS,
    '</body>\n</html>\n'])

out = head_v3 + style_v3 + CSS + '\n</head>\n' + body_open + '\n' + body

# ---------------------------------------------------------------- проверка: все id, на которые ссылается скрипт, есть
ids_have = set(re.findall(r'\sid="([^"]+)"', out))
ids_js = set(re.findall(r"\$\('#([A-Za-z0-9_-]+)'\)", js)) | set(re.findall(r"getElementById\('([^']+)'\)", js)) | set(re.findall(r"\$\('#([A-Za-z0-9_-]+)[ ,]", js))
missing = sorted(i for i in ids_js if i not in ids_have)
stubs = ''.join('<div id="%s" hidden></div>' % i for i in missing)
if stubs:
    out = out.replace('</main>', '<div class="v3hidden" hidden>' + stubs + '</div>\n</main>', 1)
dups = [i for i in ids_have if out.count(' id="%s"' % i) > 1]

os.makedirs(OUT_DIR, exist_ok=True)
open(OUT, 'w', encoding='utf-8').write(out)
man = {"name":"Гид паломника JURT (v3)","short_name":"Умра v3","start_url":"./","scope":"./","id":"./v3/","display":"standalone","orientation":"portrait","background_color":"#F4EDE1","theme_color":"#005A5C","lang":"ru",
       "icons":[{"src":"../icon-192.png","sizes":"192x192","type":"image/png"},{"src":"../icon-512.png","sizes":"512x512","type":"image/png"},{"src":"../icon-maskable-512.png","sizes":"512x512","type":"image/png","purpose":"maskable"}]}
open(os.path.join(OUT_DIR,'manifest.webmanifest'),'w',encoding='utf-8').write(json.dumps(man, ensure_ascii=False, indent=1))
print('v3/index.html: %d КБ, заглушек id: %d %s, дубликатов id: %d %s, потерянных в хвосте: %s' % (len(out.encode())//1024, len(missing), missing[:12], len(dups), dups[:8], sorted(missed)[:10]))
