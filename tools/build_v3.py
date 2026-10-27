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
 <div class="v3note" id="v3gNote" hidden></div>
 <div class="card v3where" id="v3where">
  <div class="v3map" id="v3map"><div class="v3mapMsg" id="v3mapMsg">Карта загружается…</div></div>
  <div class="v3gStat" id="v3gStat"></div>
  <div id="v3noGrp" hidden>
   <p><b>Вы ещё не в группе.</b></p>
   <p class="small">Руководитель пришлёт ссылку в WhatsApp — откройте её, и группа появится здесь сама. Вводить ничего не нужно.</p>
  </div>
  <div id="v3nameBox" hidden>
   <label class="small" for="v3name">Как вас подписать на карте?</label>
   <input id="v3name" maxlength="24" autocomplete="given-name" placeholder="Имя">
  </div>
  <button type="button" class="v3btn v3main v3share" id="v3shareBtn">Показывать меня группе</button>
  <button type="button" class="linkbtn v3shareNo" id="v3shareNo">Не показывать</button>
  <div class="v3people" id="v3people"></div>
  <div class="v3lead" id="v3lead" hidden>
   <button type="button" class="v3btn ghost" id="v3invite">Пригласить в группу</button>
   <a class="linkbtn" href="../where/" id="v3leadTools">Инструменты руководителя: перекличка, объявления, точки сбора</a>
  </div>
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
.v3where{display:flex;flex-direction:column;gap:.6rem}
.v3map{position:relative;height:56vh;min-height:300px;max-height:520px;margin:-.2rem -.2rem 0;border-radius:1rem;overflow:hidden;background:#dfe7e3;z-index:0}
:root[data-theme="dark"] .v3map{background:#1b2a2b}
.v3mapMsg{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;text-align:center;padding:1rem;color:var(--muted);font-weight:700}
.v3map .leaflet-control-attribution{font-size:10px}
.v3gStat{font-weight:800;font-size:1.05rem;color:var(--teal-d);display:flex;align-items:center;gap:.5rem}
.v3gStat i{width:.75rem;height:.75rem;border-radius:50%;background:var(--muted);flex:none}
.v3gStat.on i{background:#1fa463;box-shadow:0 0 0 4px rgba(31,164,99,.18)}
#v3nameBox{display:flex;flex-direction:column;gap:.3rem}
#v3name{min-height:3.2rem;border-radius:1rem;border:2px solid var(--teal);padding:0 1rem;font-size:1.1rem;font-family:inherit;background:var(--card);color:inherit}
.v3share{min-height:3.8rem;font-size:1.15rem}
.v3shareNo{align-self:center;min-height:2.6rem}
.v3people{display:flex;flex-direction:column}
.v3people button{display:flex;align-items:center;gap:.7rem;min-height:3.2rem;padding:.4rem .2rem;border:0;border-bottom:1px solid var(--line);background:none;color:inherit;font:inherit;text-align:left;width:100%}
.v3people button>i{width:2.3rem;height:2.3rem;border-radius:50%;flex:none;display:flex;align-items:center;justify-content:center;font-style:normal;font-weight:800;color:#fff;background:var(--teal)}
.v3people button>i.meet{background:var(--orange,#F07A1E)}.v3people button>i.hotel{background:#6b5b4b}.v3people button>i.old{background:#9aa5a3}.v3people button>i.sos{background:var(--red)}
.v3people button span{flex:1;min-width:0}.v3people button span b{display:block}.v3people button span small{color:var(--muted)}
.v3people button>em{font-style:normal;font-weight:800;color:var(--teal-d);white-space:nowrap}
.v3lead{display:flex;flex-direction:column;gap:.4rem;padding-top:.3rem}
.v3pin{display:flex;flex-direction:column;align-items:center;transform:translate(-50%,-100%);white-space:nowrap;pointer-events:auto}
.v3pin i{width:34px;height:34px;border-radius:50%;border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center;font-style:normal;font:800 15px/1 "Exo 2",system-ui,sans-serif;color:#fff;background:#005A5C}
.v3pin b{margin-top:2px;padding:1px 6px;border-radius:6px;background:rgba(255,255,255,.92);color:#00292C;font:700 12px/1.3 "Exo 2",system-ui,sans-serif;box-shadow:0 1px 3px rgba(0,0,0,.2)}
.v3pin.me i{background:#1a73e8;width:22px;height:22px;box-shadow:0 0 0 8px rgba(26,115,232,.2),0 2px 6px rgba(0,0,0,.3)}
.v3pin.meet i{background:#F07A1E;border-radius:50% 50% 50% 0;transform:rotate(-45deg)}.v3pin.meet i>s{transform:rotate(45deg);text-decoration:none}
.v3pin.hotel i{background:#6b5b4b;border-radius:9px}
.v3pin.old i{background:#9aa5a3}.v3pin.old b{opacity:.75}
.v3pin.sos i{background:#d93025;animation:v3pulse 1.2s infinite}
@keyframes v3pulse{0%{box-shadow:0 0 0 0 rgba(217,48,37,.6)}100%{box-shadow:0 0 0 18px rgba(217,48,37,0)}}
@media (prefers-reduced-motion:reduce){.v3pin.sos i{animation:none}}
.lost-grp{display:flex;flex-direction:column;align-items:flex-start;gap:.1rem;width:100%;min-height:3.6rem;margin:.2rem 0 .6rem;padding:.6rem 1rem;border-radius:1rem;border:0;background:#d93025;color:#fff;font:inherit;text-align:left}
.lost-grp b{font-size:1.1rem}.lost-grp small{opacity:.92}.lost-grp.done{background:#1f7a4d}
.v3map img.leaflet-tile{mix-blend-mode:normal!important}
.v3pinWrap{background:none;border:0}
.v3pin.me{transform:translate(-50%,-50%)}
.v3note{background:#fff4e8;border:2px solid #F07A1E;border-radius:1rem;padding:.7rem .9rem}
:root[data-theme="dark"] .v3note{background:#3a2a1a}
.v3note b{display:block;font-size:.85rem;color:#b5560b}.v3note p{margin:.2rem 0 0;font-size:1.05rem}
.v3ask{position:fixed;inset:0;z-index:90;background:rgba(0,20,22,.55);display:flex;align-items:flex-end;justify-content:center}
.v3ask[hidden]{display:none}
.v3askBox{background:var(--card,#fff);width:100%;max-width:520px;border-radius:1.4rem 1.4rem 0 0;padding:1.4rem 1rem calc(1.2rem + env(safe-area-inset-bottom));display:flex;flex-direction:column;gap:.7rem}
.v3askBox h3{margin:0;font-size:1.4rem}.v3askBox p{margin:0;color:var(--muted)}
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
    if(tab==='map'){ mapShow(); }
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

  /* ---- «Карта»: группа прямо здесь, как геоданные в WhatsApp — одна кнопка «Показывать меня группе».
     Протокол тот же, что у ../where/ (Supabase: канал where:<группа>, присутствие + сигналы), поэтому руководитель там видит всех. ---- */
  var W={ get:function(k,d){ try{ var v=localStorage.getItem('where.'+k); return v===null?d:JSON.parse(v); }catch(e){ return d; } },
          set:function(k,v){ try{ localStorage.setItem('where.'+k, JSON.stringify(v)); }catch(e){} } };
  var KAABA=[21.42251716,39.82619418], NABAWI=[24.46726,39.61113], CITYC={mak:KAABA, med:NABAWI};
  function fromM(x,y,c){ return [c[0]+y/110540, c[1]+x/(111320*Math.cos(c[0]*Math.PI/180))]; }
  var HOTEL={mak:{n:'Отель Address Jabal Omar', ll:fromM(-806,-40,KAABA)}, med:{n:'Отель Worth Peninsula', ll:[24.4735,39.6116]}};
  var DEFN={'d-hotel':'Отель Address — лобби','d-79':'Ворота № 79 короля Фахда','d-1':'Ворота № 1 короля Абдулазиза','d-25':'Ворота № 25 у Марвы','d-clock':'Часовая башня — вход с площади',
            'd-m1':'Ворота № 1 — Баб ас-Салям','d-m20':'Ворота № 20–22 короля Фахда','d-m5':'Ворота № 5 — Баб Куба','d-m41':'Ворота № 41 — аль-Баки','d-m34':'Ворота № 33–35 короля Абдулазиза'};
  function ptName(p){ for(var k in DEFN) if(String(p.id).indexOf(k+'-')===0) return DEFN[k]; return p.name||'Точка сбора'; }
  function normCode(s){ return String(s||'').toUpperCase().trim().replace(/\s+/g,'-').replace(/[^A-Z0-9-]/g,''); }
  function rid(n){ var a='abcdefghijkmnpqrstuvwxyz23456789', s=''; var r=new Uint8Array(n); (window.crypto||{getRandomValues:function(x){ for(var i=0;i<x.length;i++) x[i]=Math.random()*256; return x; }}).getRandomValues(r); for(var i=0;i<n;i++) s+=a[r[i]%a.length]; return s; }
  var Q=new URLSearchParams(location.search);
  var grp=normCode(Q.get('g')||W.get('group',''));
  if(!/^[A-Z0-9-]{4,40}$/.test(grp)) grp='';
  var hashLk=(location.hash.match(/(?:^#|&)lk=([A-Za-z0-9]{12,64})/)||[])[1]||null;
  var invited=!!(Q.get('g') && grp);
  if(grp){ W.set('group',grp); if(hashLk) W.set('lk.'+grp, hashLk); if(Q.get('tel')) W.set('tel.'+grp, Q.get('tel').replace(/[^\d+ ()-]/g,'').slice(0,20)); }
  if(Q.has('g')||Q.has('tel')||hashLk){ Q.delete('g'); Q.delete('tel'); history.replaceState(null,'',location.pathname+(Q.toString()?'?'+Q:'')); }
  if(invited){ A.set('tab','map'); if(A.get('senior',0)) {} }
  var me={ id:W.get('id',null)||rid(8), name:W.get('name',''), ll:null, acc:null, t:0, sos:0 };
  W.set('id',me.id);
  var people={}, gone=grp?(W.get('gone.'+grp,{})||{}):{}, points=[], notes=[], lead=false, bus=null, busP=null, city='mak';
  var gpsNo=false, map=null, mk={}, mapAsked=false, firstFix=true, watchId=null, lastSent=0, lastLL=null;
  function sharing(){ return A.get('v3consent',null)==='1' && !!grp && !tripOver(); }
  function tripOver(){ var tr=(window.WHERE_CFG||{}).trips||{}, k=Object.keys(tr).filter(function(p){ return grp.indexOf(p)===0; })[0]; return !!k && Date.now()>new Date(tr[k]+'T23:59:59+03:00').getTime(); }
  function loadJs(src){ return new Promise(function(ok,no){ var s=document.createElement('script'); s.src=src; s.onload=ok; s.onerror=function(){ no(new Error(src)); }; document.head.appendChild(s); }); }
  function loadCss(href){ if(document.querySelector('link[href="'+href+'"]')) return; var l=document.createElement('link'); l.rel='stylesheet'; l.href=href; document.head.appendChild(l); }
  function cityOf(ll){ if(!ll) return city; return km(ll[0],ll[1],NABAWI[0],NABAWI[1]) < km(ll[0],ll[1],KAABA[0],KAABA[1]) ? 'med' : 'mak'; }
  function dM(a,b){ return km(a[0],a[1],b[0],b[1]); }
  function fmtD(m){ return m<1000 ? Math.round(m/5)*5+' м' : (m/1000).toFixed(1).replace('.',',')+' км'; }
  function ago(t){ var m=Math.round((Date.now()-t)/60000); return m<1?'сейчас':m<60?m+' мин назад':Math.round(m/60)+' ч назад'; }
  function ini(n){ return String(n||'?').trim().split(/\s+/).map(function(w){ return w[0]; }).join('').slice(0,2).toUpperCase(); }
  function meetPoint(){ var c=CITYC[city]; return points.filter(function(p){ return p.meet && dM(p.ll,c)<30000; })[0]||null; }

  /* связь с группой */
  function connect(){
    if(!grp) return Promise.resolve(null);
    if(busP) return busP;
    busP=loadJs('../where/config.js').then(function(){ return window.supabase ? 0 : loadJs('../where/vendor/supabase.js'); }).then(function(){
      var CFG=window.WHERE_CFG||{}; if(!CFG.url||!CFG.key||!window.supabase) throw new Error('cfg');
      var db=window.supabase.createClient(CFG.url, CFG.key, {auth:{persistSession:false}});
      var chk=function(r){ if(r.error) throw new Error(r.error.message); return r.data; };
      var api={db:db, ch:null, st:'', last:null, tT:0, tH:null};
      api.lk=function(){ return W.get('lk.'+grp,null); };
      return db.rpc('where_join',{p_grp:grp, p_key:api.lk(), p_create:false}).then(chk).then(function(j){
        if(j && !j.ok){ api.none=true; return api; }
        lead=!!(j && j.lead); if(lead) W.set('lead.'+grp,1);
        var c=db.channel('where:'+grp,{config:{presence:{key:me.id}, broadcast:{self:false}}}); api.ch=c;
        c.on('presence',{event:'sync'},function(){ var st=c.presenceState(), nx={}; for(var id in st){ var p=st[id][st[id].length-1]; if(id!==me.id && p) nx[id]=p; } onPresence(nx); });
        ['sos','sosOff','pts','note','roll','rollEnd','ack','forget'].forEach(function(ev){ c.on('broadcast',{event:ev},function(m){ onSignal(ev, m.payload||{}); }); });
        c.subscribe(function(s){ api.st=s; status(); if(s==='SUBSCRIBED'){ flush(); loadPts(); loadNotes(); } });
        return api;
      });
    }).then(function(api){ bus=api; status(); return api; }).catch(function(e){ busP=null; status('Нет связи с группой — проверьте интернет. Попробую снова сам.'); setTimeout(function(){ if(!bus) connect(); }, 20000); return null; });
    return busP;
  }
  function flush(){ if(!bus||!bus.ch||bus.st!=='SUBSCRIBED'||!bus.last) return; bus.tT=Date.now(); bus.ch.track(bus.last).catch(function(){}); }
  function track(p){ if(!bus) return; bus.last=p; clearTimeout(bus.tH); var w=3000-(Date.now()-bus.tT); if(w<=0) flush(); else bus.tH=setTimeout(flush,w); }
  function signal(ev,p){ if(bus&&bus.ch) bus.ch.send({type:'broadcast', event:ev, payload:p||{}}).catch(function(){}); }
  function untrack(){ if(bus){ bus.last=null; clearTimeout(bus.tH); try{ bus.ch && bus.ch.untrack(); }catch(e){} } }
  function payload(){ var sh=sharing() && me.ll; var p={id:me.id, name:me.name||'Паломник', ll:sh?me.ll:null, acc:sh?Math.round(me.acc||0):null, floor:0, city:city, t:Date.now(), fx:sh?me.t:0, man:false, sh:sharing(), sos:me.sos, lead:lead, bat:null, chg:false};
    if(lead){ var tel=W.get('tel.'+grp,''); if(tel) p.tel=tel; } if(myAck && Date.now()-myAck.t<30*60000) p.ack=myAck; return p; }
  function publish(force){
    if(!bus||!bus.ch) return;
    if(!sharing() && !me.sos && !myAck){ untrack(); return; }
    var moved = me.ll && (!lastLL || dM(lastLL, me.ll)>10);
    if(!force && !moved && Date.now()-lastSent<20000) return;
    lastSent=Date.now(); lastLL=me.ll; track(payload());
  }
  setInterval(function(){ publish(true); }, 60000);
  addEventListener('pagehide', untrack);
  document.addEventListener('visibilitychange', function(){ if(!document.hidden) publish(true); });
  function loadPts(){ if(!bus||!bus.db) return; bus.db.rpc('where_list',{p_grp:grp}).then(function(r){ if(r.error) return; var old=meetPoint(); points=(r.data||[]).map(function(x){ return {id:x.id, name:x.name, ll:[x.lat,x.lon], meet:x.meet_at}; }); var m=meetPoint(); if(m && (!old || old.id!==m.id || old.meet!==m.meet) && old!==undefined && lastMeet && lastMeet!==m.id+m.meet){ A.buzz([120,60,120]); A.toast('Новая точка сбора: '+ptName(m)+(m.meet?' · '+m.meet:''), function(){ go(); fly(m.ll); }); } lastMeet=m?m.id+m.meet:''; render(); }); }
  var lastMeet='';
  function loadNotes(){ if(!bus||!bus.db) return; bus.db.rpc('where_notes_list',{p_grp:grp}).then(function(r){ if(r.error) return; notes=(r.data||[]).map(function(x){ return {id:x.id, body:x.body, by:x.by_name, t:Date.parse(x.created_at)}; }).sort(function(a,b){ return b.t-a.t; }); render(); }); }
  function onPresence(nx){
    var now=Date.now();
    for(var id in people) if(!nx[id] && people[id].ll){ gone[id]=Object.assign({}, people[id], {goneAt:now}); }
    for(var id2 in nx) delete gone[id2];
    for(var g in gone) if(now-gone[g].goneAt>3*3600000) delete gone[g];
    people=nx; W.set('gone.'+grp, gone);
    for(var i in nx){ var p=nx[i]; if(p.sos && now-p.sos<15*60000) onSos({id:i, name:p.name, ll:p.ll, t:p.sos}); if(p.lead && p.tel) W.set('tel.'+grp, p.tel); if(p.roll) onRoll(p.roll); }
    render();
  }
  function onSignal(ev,p){
    if(ev==='sos') onSos(p);
    else if(ev==='sosOff'){ if(people[p.id]) people[p.id].sos=0; A.toast((p.name||'Паломник')+' нашёлся'); render(); }
    else if(ev==='pts') loadPts();
    else if(ev==='note'){ loadNotes(); A.buzz([80,60,80]); }
    else if(ev==='roll') onRoll(p);
    else if(ev==='rollEnd'){ if(curAsk && curAsk.rid===p.rid) askClose(); }
    else if(ev==='forget'){ delete people[p.id]; delete gone[p.id]; render(); }
  }
  var sosSeen={};
  function onSos(p){
    if(!p||!p.id||p.id===me.id) return; var k=p.id+':'+p.t; if(sosSeen[k]) return; sosSeen[k]=1;
    if(Date.now()-p.t>15*60000) return;
    if(people[p.id]) people[p.id].sos=p.t;
    A.buzz([300,120,300,120,300]);
    A.toast('⚠ '+(p.name||'Паломник')+' зовёт группу'+(p.ll&&me.ll?' · '+fmtD(dM(me.ll,p.ll)):''), function(){ go(); if(p.ll) fly(p.ll); });
    var b=$('#toastBtn'); if(b) b.textContent='Показать';
    render();
  }
  /* перекличка руководителя: один вопрос, две большие кнопки */
  var curAsk=null, myAck=null;
  var ask=document.createElement('div'); ask.className='v3ask'; ask.hidden=true;
  ask.innerHTML='<div class="v3askBox" role="dialog" aria-modal="true"><h3>Вы на месте?</h3><p id="v3askBy">Спрашивает руководитель</p><button type="button" class="v3btn v3main" id="v3askOk">Я на месте</button><button type="button" class="v3btn v3sos" id="v3askHelp">Нужна помощь</button></div>';
  document.body.appendChild(ask);
  function onRoll(r){
    if(!r||!r.rid||r.from===me.id||Date.now()-r.t>30*60000) return;
    if((W.get('ans.'+grp,[])||[]).indexOf(r.rid)>=0) return;
    if(curAsk && curAsk.rid===r.rid) return;
    curAsk=r; $('#v3askBy').textContent='Спрашивает '+(r.by||'руководитель'); ask.hidden=false; A.buzz([200,100,200]);
  }
  function askClose(){ curAsk=null; ask.hidden=true; }
  function answer(ok){
    if(!curAsk) return; var r=curAsk;
    W.set('ans.'+grp, (W.get('ans.'+grp,[])||[]).concat([r.rid]).slice(-50));
    myAck={rid:r.rid, ok:ok, t:Date.now()};
    signal('ack',{rid:r.rid, id:me.id, name:me.name||'Паломник', ok:ok, ll:sharing()?me.ll:null, t:myAck.t});
    publish(true); askClose();
    if(ok) A.toast('Ответ отправлен руководителю'); else { callGroup(); A.openLost(); }
  }
  $('#v3askOk').onclick=function(){ A.buzz(10); answer(true); };
  $('#v3askHelp').onclick=function(){ A.buzz(20); answer(false); };

  /* «Позвать группу» внутри «Я потерялся» */
  function callGroup(){
    if(!grp) return;
    me.sos=Date.now(); gps();
    connect().then(function(){ publish(true); signal('sos',{id:me.id, name:me.name||'Паломник', ll:me.ll, floor:0, city:city, t:me.sos}); });
    lostBtn();
  }
  function found(){ me.sos=0; publish(true); signal('sosOff',{id:me.id, name:me.name||'Паломник'}); lostBtn(); }
  var lb=document.createElement('button'); lb.type='button'; lb.className='lost-grp'; lb.id='v3lostGrp';
  (function(){ var box=$('#lost .lost-box'), tip=$('#lost .lost-tip'); if(box && tip) tip.parentNode.insertBefore(lb, tip.nextSibling); })();
  function lostBtn(){
    lb.hidden=!grp;
    if(me.sos){ lb.classList.add('done'); lb.innerHTML='<b>Группа знает, где вы</b><small>Стойте на месте. Нажмите, когда нашлись</small>'; }
    else { lb.classList.remove('done'); lb.innerHTML='<b>Позвать группу</b><small>Все наши увидят вас на карте и получат сигнал</small>'; }
  }
  lb.onclick=function(){ A.buzz(20); if(me.sos) found(); else callGroup(); };
  lostBtn();
  /* ссылка «Карта группы» в «Я потерялся» — теперь внутри гида, без перехода на старую страницу */
  $$('#lost a[href="where/"], #lost a[href="../where/"]').forEach(function(a){ var sm=a.querySelector('small'); if(sm) sm.textContent='где все наши и точка сбора — здесь же, в гиде'; a.onclick=function(e){ e.preventDefault(); var x=$('#lostClose'); if(x) x.click(); go(); }; });
  function go(){ window.v3.show('map', null); }

  /* положение */
  function gps(){
    if(watchId!==null || !navigator.geolocation) return;
    watchId=navigator.geolocation.watchPosition(function(p){
      gpsNo=false; me.ll=[p.coords.latitude,p.coords.longitude]; me.acc=p.coords.accuracy; me.t=Date.now(); city=cityOf(me.ll);
      if(map && firstFix){ firstFix=false; map.setView(me.ll, 16); }
      render(); publish();
    }, function(e){ if(e.code===1){ navigator.geolocation.clearWatch(watchId); watchId=null; gpsNo=true; render(); } }, {enableHighAccuracy:true, maximumAge:10000, timeout:30000});
  }

  /* карта */
  function mapInit(){
    if(map) return Promise.resolve();
    loadCss('../where/vendor/leaflet.css');
    return (window.L ? Promise.resolve() : loadJs('../where/vendor/leaflet.js')).then(function(){
      var el=$('#v3map'); $('#v3mapMsg').remove && $('#v3mapMsg').remove();
      map=L.map(el,{zoomControl:false, attributionControl:true}).setView(me.ll||CITYC[city], me.ll?16:16);
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19, attribution:'© OpenStreetMap contributors (ODbL)'}).addTo(map);
      map.attributionControl.setPrefix(false);
      if(me.ll) firstFix=false;
      render();
    }).catch(function(){ var m=$('#v3mapMsg'); if(m) m.textContent='Карта не загрузилась — нужен интернет. Список ниже работает.'; });
  }
  function fly(ll){ if(map && ll) map.setView(ll, 18); var el=$('#v3map'); if(el) el.scrollIntoView({behavior:'smooth', block:'center'}); }
  function pin(key, ll, cls, ch, label){
    if(!map || !L) return; var html='<div class="v3pin '+cls+'"><i>'+ch+'</i>'+(label?'<b>'+esc(label)+'</b>':'')+'</div>';
    var m=mk[key];
    if(!m){ m=mk[key]=L.marker(ll,{icon:L.divIcon({className:'v3pinWrap', html:html, iconSize:null}), keyboard:false, zIndexOffset:cls.indexOf('sos')>=0?1000:cls==='me'?900:0}).addTo(map); m._h=html; }
    else { m.setLatLng(ll); if(m._h!==html){ m.setIcon(L.divIcon({className:'v3pinWrap', html:html, iconSize:null})); m._h=html; } }
    m._seen=1;
  }
  function status(txt){
    var s=$('#v3gStat'); if(!s) return;
    if(txt){ s.className='v3gStat'; s.innerHTML='<i></i>'+esc(txt); return; }
    if(!grp){ s.className='v3gStat'; s.innerHTML=''; return; }
    var n=Object.keys(people).length, on=sharing();
    if(bus && bus.none){ s.className='v3gStat'; s.innerHTML='<i></i>Группа '+esc(grp)+' не найдена. Попросите у руководителя новую ссылку.'; return; }
    if(tripOver()){ s.className='v3gStat'; s.innerHTML='<i></i>Поездка завершена — место больше не передаётся'; return; }
    if(gpsNo && sharing()){ s.className='v3gStat'; s.innerHTML='<i></i>Телефон не даёт место. Настройки → Конфиденциальность → Геопозиция → разрешить для браузера. Группу вы видите.'; return; }
    s.className='v3gStat'+(on?' on':'');
    s.innerHTML='<i></i>'+(on?'Вас видит группа':'Группа вас не видит')+(bus&&bus.st==='SUBSCRIBED'?' · на связи '+(n+1):(bus?' · подключаюсь…':''));
  }
  function render(){
    status();
    var c=A.get('v3consent',null), btn=$('#v3shareBtn'), no=$('#v3shareNo');
    $('#v3noGrp').hidden=!!grp; btn.hidden=!grp; no.hidden=!grp || c!==null;
    if(sharing()){ btn.textContent='Перестать показывать'; btn.className='v3btn ghost v3share'; }
    else { btn.textContent='Показывать меня группе'; btn.className='v3btn v3main v3share'; }
    $('#v3lead').hidden=!(grp && (lead || W.get('lead.'+grp,0)));
    lostBtn();
    /* объявление руководителя за последние сутки */
    var nb=$('#v3gNote'), n=notes[0];
    if(n && Date.now()-n.t<24*3600000){ nb.hidden=false; nb.innerHTML='<b>Объявление'+(n.by?' · '+esc(n.by):'')+' · '+ago(n.t)+'</b><p>'+esc(n.body)+'</p>'; } else nb.hidden=true;
    /* метки и список */
    for(var k in mk) mk[k]._seen=0;
    var rows=[], ref=me.ll;
    var h=HOTEL[city], m=meetPoint();
    if(m){ pin('meet', m.ll, 'meet', '<s>★</s>', 'Сбор'+(m.meet?' '+m.meet:'')); rows.push({k:'meet', ll:m.ll, cls:'meet', ch:'★', t:ptName(m), s:(m.meet?'Сбор в '+m.meet:'Точка сбора')+' · <a href="https://www.google.com/maps/dir/?api=1&destination='+m.ll[0]+','+m.ll[1]+'&travelmode=walking" target="_blank" rel="noopener">маршрут пешком</a>', d:ref?dM(ref,m.ll):null}); }
    pin('hotel', h.ll, 'hotel', 'H', null); rows.push({k:'hotel', ll:h.ll, cls:'hotel', ch:'H', t:h.n, s:'Наш отель', d:ref?dM(ref,h.ll):null});
    var ppl=[];
    Object.keys(people).forEach(function(id){ var p=people[id]; var sos=p.sos && Date.now()-p.sos<15*60000; var old=p.ll && Date.now()-(p.fx||p.t)>5*60000;
      if(p.ll) pin('p'+id, p.ll, sos?'sos':old?'old':'', esc(ini(p.name)), p.name);
      ppl.push({k:'p'+id, ll:p.ll, cls:sos?'sos':(!p.ll||old)?'old':'', ch:esc(ini(p.name)), t:(p.name||'Паломник')+(p.lead?' · руководитель':''), s:sos?'<b style="color:var(--red)">Зовёт группу</b> · '+ago(p.sos):(p.ll?'место '+ago(p.fx||p.t):'не показывает место'), d:ref&&p.ll?dM(ref,p.ll):null}); });
    Object.keys(gone).forEach(function(id){ var p=gone[id]; if(people[id]||!p.ll) return; pin('g'+id, p.ll, 'old', esc(ini(p.name)), p.name);
      ppl.push({k:'g'+id, ll:p.ll, cls:'old', ch:esc(ini(p.name)), t:p.name||'Паломник', s:'вышел из гида · последнее место '+ago(p.fx||p.t||p.goneAt), d:ref?dM(ref,p.ll):null}); });
    ppl.sort(function(a,b){ return (a.cls==='sos'?-1:0)-(b.cls==='sos'?-1:0) || (a.d==null?1e9:a.d)-(b.d==null?1e9:b.d); });
    if(me.ll) pin('me', me.ll, 'me', '', null);
    for(var k2 in mk) if(!mk[k2]._seen){ map && map.removeLayer(mk[k2]); delete mk[k2]; }
    var all=rows.concat(ppl);
    var box=$('#v3people');
    box.innerHTML = all.map(function(r,i){ return '<button type="button" data-i="'+i+'"><i class="'+r.cls+'">'+r.ch+'</i><span><b>'+esc(r.t)+'</b><small>'+r.s+'</small></span>'+(r.d!=null?'<em>'+fmtD(r.d)+'</em>':'')+'</button>'; }).join('')
      + (grp && !ppl.length ? '<p class="small">Пока никого из группы на карте. Когда остальные нажмут «Показывать меня группе», они появятся здесь.</p>' : '');
    $$('button[data-i]', box).forEach(function(b){ b.onclick=function(e){ if(e.target.closest('a')) return; var r=all[+b.getAttribute('data-i')]; A.buzz(6); if(r.ll) fly(r.ll); }; });
  }
  /* одна кнопка */
  $('#v3shareBtn').onclick=function(){
    A.buzz(8);
    if(sharing()){ A.set('v3consent','0'); W.set('share',false); untrack(); signal('forget',{id:me.id}); render(); A.toast('Группа больше не видит ваше место', function(){ $('#v3shareBtn').click(); }); return; }
    var nm=$('#v3name'); if(!me.name){ var v=(nm.value||'').trim(); if(!v){ $('#v3nameBox').hidden=false; nm.focus(); A.toast('Напишите имя — так вас узнают на карте'); return; } me.name=v.slice(0,24); W.set('name',me.name); }
    $('#v3nameBox').hidden=true;
    A.set('v3consent','1'); W.set('share',true); gps(); connect().then(function(){ publish(true); render(); }); render();
    A.toast('Готово: группа видит вас, пока гид открыт');
  };
  $('#v3name').onkeydown=function(e){ if(e.key==='Enter'){ e.preventDefault(); $('#v3shareBtn').click(); } };
  $('#v3shareNo').onclick=function(){ A.buzz(6); A.set('v3consent','0'); W.set('share',false); render(); A.toast('Хорошо. Вы видите группу, группа вас — нет'); };
  $('#v3invite').onclick=function(){
    A.buzz(6); var tel=W.get('tel.'+grp,''), url=location.origin+location.pathname+'?g='+encodeURIComponent(grp)+(tel?'&tel='+encodeURIComponent(tel):'');
    var text='Гид JURT: откройте ссылку — вы в группе '+grp+', карта и «Я потерялся» внутри.';
    if(navigator.share) navigator.share({title:'Гид JURT', text:text, url:url}).catch(function(){});
    else window.open('https://wa.me/?text='+encodeURIComponent(text+' '+url),'_blank','noopener');
  };
  $('#v3leadTools').setAttribute('href', '../where/?g='+encodeURIComponent(grp||''));
  function mapShow(){ gps(); connect(); mapInit().then(function(){ if(map) setTimeout(function(){ map.invalidateSize(); },60); }); render(); }
  /* место уходит группе, пока гид открыт на любой вкладке */
  if(grp && A.get('v3consent',null)==='1'){ gps(); connect().then(function(){ publish(true); }); }
  else if(grp) connect();
  setInterval(function(){ if(document.hidden) return; var v=$('#v-map'); if(v && v.classList.contains('on')) render(); }, 30000);

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
