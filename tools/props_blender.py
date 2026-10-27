# Реквизит 3D Харама (umra.jurt.kz/haram3d/) — все люди, герой и предметы сцены как объекты Blender.
# Запуск: Blender -b --factory-startup --python props_blender.py -- <out_dir>
# Пишет <out_dir>/props.blend (редактировать) и <out_dir>/props.glb (в сайт: haram3d/props.glb).
# Координаты задаём как в three.js (x, y вверх, z к зрителю) и переводим в Blender (x, -z, y);
# экспорт glTF с +Y вверх переводит обратно — числа в сайте совпадают с числами здесь.
# Имена объектов только с «_» (точки three.js вырезает). Части людей: <набор>_b<кость>m<материал>_<что>,
# кость/материал читает шейдер толпы (0 изар, 1 тело, 2–3 правая рука, 4–5 левая, 6–7 ступни, 8–9 штанины;
# материал 0 ткань, 1 кожа, 2 волосы/платок, 3 борода, 4 правое плечо ихрама, 5 предплечье, 6 рукав, 7 торс).
# Руки лежат у плеча (правая +JX, левая −JX, высота JY) — сайт сам вычитает это смещение.
import bpy, bmesh, math, sys, os

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.path.dirname(os.path.abspath(__file__))
TAU = math.tau


class G:
    """Сетка в координатах three.js: вершины и грани (против часовой — лицом наружу)."""
    def __init__(self, v=None, f=None):
        self.v, self.f = v or [], f or []

    def tf(self, fn):
        self.v = [fn(*p) for p in self.v]; return self

    def scale(self, sx, sy=None, sz=None):
        sy = sx if sy is None else sy; sz = sx if sz is None else sz
        return self.tf(lambda x, y, z: (x * sx, y * sy, z * sz))

    def move(self, dx=0, dy=0, dz=0):
        return self.tf(lambda x, y, z: (x + dx, y + dy, z + dz))

    def rotX(self, a):
        c, s = math.cos(a), math.sin(a)
        return self.tf(lambda x, y, z: (x, y * c - z * s, y * s + z * c))

    def rotZ(self, a):
        c, s = math.cos(a), math.sin(a)
        return self.tf(lambda x, y, z: (x * c - y * s, x * s + y * c, z))

    def add(self, *gs):
        for g in gs:
            o = len(self.v); self.v += g.v; self.f += [[i + o for i in f] for f in g.f]
        return self


def rev(prof, seg, zs=1.0):
    """Тело вращения вокруг y (как LatheGeometry): prof — [(радиус, y)] снизу вверх; радиус 0 — одна вершина-полюс."""
    v, idx = [], []
    for r, y in prof:
        if r < 1e-9:
            idx.append([len(v)] * seg); v.append((0.0, y, 0.0))
        else:
            row = []
            for i in range(seg):
                ph = TAU * i / seg; row.append(len(v)); v.append((r * math.sin(ph), y, r * math.cos(ph) * zs))
            idx.append(row)
    f = []
    for j in range(len(prof) - 1):
        for i in range(seg):
            k = (i + 1) % seg
            q = [idx[j][i], idx[j][k], idx[j + 1][k], idx[j + 1][i]]
            q = [a for n, a in enumerate(q) if a != q[n - 1]]
            if len(q) >= 3: f.append(q)
    return G(v, f)


def lathe(pts, seg, zs=1.0):
    return rev(pts, seg, zs)


def sphere(r, w=10, h=7, t0=0.0, t1=math.pi):
    """Сфера (или её пояс от угла t0 до t1 от макушки): w — по кругу, h — по высоте."""
    prof = [(r * math.sin(t0 + (t1 - t0) * k / h), r * math.cos(t0 + (t1 - t0) * k / h)) for k in range(h, -1, -1)]
    prof = [(0.0 if abs(a) < 1e-7 else a, b) for a, b in prof]
    return rev(prof, w)


def ball(r, x, y, z, sx=1, sy=1, sz=1, w=10, h=7):
    return sphere(r, w, h).scale(sx, sy, sz).move(x, y, z)


def cylinder(rT, rB, hgt, seg=9, open_=False):
    p = [(rB, -hgt / 2), (rT, hgt / 2)]
    if not open_: p = [(0.0, -hgt / 2)] + p + [(0.0, hgt / 2)]
    return rev(p, seg)


def cyl(r0, r1, y0, y1, x=0.0, seg=9):   # как cyl() в сайте: r0 сверху, r1 снизу, от y0 до y1
    return cylinder(r0, r1, y1 - y0, seg).move(x, (y0 + y1) / 2, 0)


def box(w, h, d):
    a, b, c = w / 2, h / 2, d / 2
    v = [(-a, -b, -c), (a, -b, -c), (a, b, -c), (-a, b, -c), (-a, -b, c), (a, -b, c), (a, b, c), (-a, b, c)]
    f = [[4, 5, 6, 7], [1, 0, 3, 2], [5, 1, 2, 6], [0, 4, 7, 3], [7, 6, 2, 3], [0, 1, 5, 4]]
    return G(v, f)


def torus(R, r, rs, ts):
    v, f = [], []
    for j in range(ts):
        u = TAU * j / ts
        for i in range(rs):
            a = TAU * i / rs
            v.append(((R + r * math.cos(a)) * math.cos(u), (R + r * math.cos(a)) * math.sin(u), r * math.sin(a)))
    for j in range(ts):
        for i in range(rs):
            j2, i2 = (j + 1) % ts, (i + 1) % rs
            f.append([j * rs + i, j2 * rs + i, j2 * rs + i2, j * rs + i2])
    return G(v, f)


MATS = {}


def mat(name, rgb, rough=0.8, metal=0.0, emit=None, emit_k=0.0, double=False):
    if name in MATS: return MATS[name]
    m = bpy.data.materials.new(name); m.use_nodes = True
    bs = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    col = ((rgb >> 16 & 255) / 255, (rgb >> 8 & 255) / 255, (rgb & 255) / 255)
    lin = tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in col)   # sRGB → линейный, как читает glTF
    bs.inputs["Base Color"].default_value = (*lin, 1)
    bs.inputs["Roughness"].default_value = rough; bs.inputs["Metallic"].default_value = metal
    if emit is not None:
        ec = ((emit >> 16 & 255) / 255, (emit >> 8 & 255) / 255, (emit & 255) / 255)
        el = tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in ec)
        for k in ("Emission Color", "Emission"):
            if k in bs.inputs: bs.inputs[k].default_value = (*el, 1); break
        if "Emission Strength" in bs.inputs: bs.inputs["Emission Strength"].default_value = emit_k
    m.use_backface_culling = not double
    m.diffuse_color = (*lin, 1)
    MATS[name] = m
    return m


def coll(name, parent=None):
    c = bpy.data.collections.new(name); (parent or bpy.context.scene.collection).children.link(c); return c


def obj(name, g, material, c, parent=None, smooth=75, loc=None, recalc=True):
    """Объект Blender из сетки three.js. smooth — угол (°), выше которого ребро острое; 0 — плоские грани."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([(x, -z, y) for x, y, z in g.v], [], g.f)
    me.validate(clean_customdata=False); me.update()
    if recalc:
        bm = bmesh.new(); bm.from_mesh(me)
        if all(e.is_manifold for e in bm.edges): bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me); bm.free()
    if smooth:
        try: me.set_sharp_from_angle(angle=math.radians(smooth))
        except AttributeError:
            for p in me.polygons: p.use_smooth = True
    else:
        try: me.shade_flat()
        except AttributeError:
            for p in me.polygons: p.use_smooth = False
    me.materials.append(material)
    o = bpy.data.objects.new(name, me); c.objects.link(o)
    if parent: o.parent = parent
    if loc: o.location = (loc[0], -loc[2], loc[1])
    return o


def empty(name, c, loc=(0, 0, 0), parent=None):
    e = bpy.data.objects.new(name, None); e.empty_display_size = 0.3; c.objects.link(e)
    e.location = (loc[0], -loc[2], loc[1])
    if parent: e.parent = parent
    return e


for o in list(bpy.data.objects): bpy.data.objects.remove(o)
bpy.context.scene.unit_settings.system = "METRIC"

# ---------- Люди толпы: 4 набора (мужчина/женщина × вблизи/издали) ----------
FIGM = [mat("fig_m0_cloth", 0xf2f0ea), mat("fig_m1_skin", 0xc89a72), mat("fig_m2_hair", 0x2a2522), mat("fig_m3_beard", 0x2a2522),
        mat("fig_m4_shoulder", 0xf2f0ea), mat("fig_m5_forearm", 0xc89a72), mat("fig_m6_sleeve", 0xf2f0ea), mat("fig_m7_torso", 0xd9b08a)]
C_FIG = coll("Люди_толпы")
for si, (woman, near) in enumerate([(False, True), (False, False), (True, True), (True, False)]):
    tag = ("w" if woman else "m") + ("n" if near else "f")
    root = empty("fig_" + ("w" if woman else "m") + "_" + ("near" if near else "far"), C_FIG, loc=(si * 1.2 - 1.8, 0, 6))
    S, W, H, CC = (14, 10, 7, 8) if near else (6, 6, 4, 5)
    JX, JY = (0.2, 1.39) if woman else (0.215, 1.42)
    parts = []

    def add(bone, m, label, g): parts.append((bone, m, label, g))

    def fball(r, x, y, z, sx=1, sy=1, sz=1, w=W, h=H): return ball(r, x, y, z, sx, sy, sz, w, h)

    def tube(rT, rB, yT, yB, x=0.0):   # трубка как в сайте: вблизи без крышек, издали с крышками
        return cylinder(rT, rB, yT - yB, CC, open_=near).move(x, (yT + yB) / 2, 0)

    if woman:
        add(0, 0, "abaya", lathe([[0, .05], [.3, .05], [.29, .15], [.26, .5], [.235, .85], [.22, 1.02], [0, 1.05]], S, .75))
        add(1, 0, "chest", lathe([[0, 1.0], [.22, 1.0], [.215, 1.2], [.2, 1.36], [0, 1.4]], S, .66))
        add(1, 2, "scarf", lathe([[0, 1.35], [.27, 1.36], [.22, 1.45], [.15, 1.53], [.125, 1.6], [.125, 1.7], [.09, 1.77], [0, 1.79]], S, .8))
        add(1, 1, "face", fball(.075, 0, 1.655, -.085, 1, 1.2, .7))
    else:
        add(0, 0, "izar", lathe([[0, .08], [.235, .08], [.245, .3], [.235, .7], [.215, 1.0], [.2, 1.04], [0, 1.04]], S, .72))
        add(1, 7, "torso", lathe([[0, 1.0], [.19, 1.0], [.205, 1.15], [.215, 1.3], [.2, 1.42], [.15, 1.48], [.06, 1.52], [0, 1.53]], S, .62))
        add(1, 0, "shoulderL", fball(.08, -.205, 1.405, 0))
        add(1, 4, "shoulderR", fball(.085, .205, 1.41, 0))
        add(1, 1, "neck", tube(.05, .055, 1.6, 1.48))
        add(1, 1, "head", fball(.11, 0, 1.665, 0, .85, 1.05, .98))
        if near:
            add(1, 1, "nose", fball(.022, 0, 1.652, -.1, .7, 1.1, 1.1, 6, 4))
            add(1, 1, "earR", fball(.026, .093, 1.665, 0, .45, 1, .75, 6, 4))
            add(1, 1, "earL", fball(.026, -.093, 1.665, 0, .45, 1, .75, 6, 4))
        add(1, 2, "hair", sphere(.118, W, H, 0, 1.45).rotX(.25).scale(.88, 1.07, 1).move(0, 1.665, 0))
        add(1, 3, "beard", fball(.07, 0, 1.6, -.06, 1.25, .8, .9))
    for side, (u, f, mu) in (("R", (2, 3, 6)), ("L", (4, 5, 0))):   # руки висят вдоль −y от плечевого сустава
        sx = JX if side == "R" else -JX
        arm = []
        if near: arm += [(u, mu, "shoulderball", fball(.062, 0, 0, 0)), (u, mu, "elbow", fball(.047, 0, -.29, 0))]
        arm.append((u, mu, "upper", tube(.055, .048, 0, -.29)))
        arm.append((f, 5, "fore", tube(.046, .038, -.29, -.52)))
        if near:
            arm.append((f, 1, "palm", fball(1, 0, -.565, 0, .017, .045, .038, 7, 5)))
            arm.append((f, 1, "thumb", fball(1, 0, -.57, -.045, .011, .028, .011, 5, 3)))
            for n, z in enumerate((-.027, -.009, .009, .027)):
                arm.append((f, 1, "finger%d" % (n + 1), fball(1, 0, -.632, z, .011, .034, .0095, 5, 3)))
        else:
            arm.append((f, 1, "hand", fball(.045, 0, -.58, 0, .55, 1.3, .85, 5, 3)))
        for b, m, lab, g in arm: add(b, m, "arm" + side + "_" + lab, g.move(sx, JY, 0))
    if not woman:
        for b, x, s in ((8, .095, "R"), (9, -.095, "L")): add(b, 0, "leg" + s, tube(.09, .07, .9, .1, x))
    for b, x, s in ((6, .09, "R"), (7, -.09, "L")):
        add(b, 0 if woman else 1, "foot" + s, fball(.05, x, .035, -.04, 1, .6, 2, 8 if near else 5, 5 if near else 3))
        if near and not woman: add(b, 1, "ankle" + s, tube(.035, .04, .13, .03, x))
    for b, m, lab, g in parts:
        obj("%s_b%dm%d_%s" % (tag, b, m, lab), g, FIGM[m], C_FIG, parent=root)

# ---------- Герой «Вы» ----------
C_HERO = coll("Герой")
HC = mat("hero_cloth", 0xffffff, .7, emit=0xfff1d0, emit_k=.3)
HS = mat("hero_skin", 0xc89a72, .8)
HIP = 1.0
hero = empty("hero", C_HERO, loc=(3.5, 0, 6))
hup = empty("hero_upper", C_HERO, loc=(0, HIP, 0), parent=hero)   # верх тела вращается вокруг таза (наклон, поклон)
obj("hero_lower", G().add(cyl(.27, .33, .08, 1.03, 0, 16), box(.1, .04, .27).move(-.1, .02, -.04), box(.1, .04, .27).move(.1, .02, -.04)), HC, C_HERO, parent=hero)
obj("hero_cloth_upper", G().add(cyl(.258, .278, .98, 1.27, 0, 16), box(.62, .15, .5).rotZ(-.62).move(-.04, 1.3, 0), box(.24, .2, .46).move(-.17, 1.42, 0)).move(0, -HIP, 0), HC, C_HERO, parent=hup)
obj("hero_skin_upper", G().add(cyl(.2, .24, 1.2, 1.47, 0, 14), cyl(.055, .06, 1.46, 1.58, 0, 10), sphere(.115, 16, 12).move(0, 1.68, 0)).move(0, -HIP, 0), HS, C_HERO, parent=hup)
obj("hero_cover", box(.27, .21, .49).move(.16, 1.42 - HIP, 0), HC, C_HERO, parent=hup)   # правое плечо закрыто вне тавафа


def seg_geo(r0, r1, l, s=10): return cylinder(r1, r0, l, s).move(0, l / 2, 0)   # сегмент руки растёт вверх от сустава


obj("hero_arm_up", seg_geo(.075, .065, .3), HC, C_HERO, parent=hup, loc=(.28, 1.44 - HIP, 0))
obj("hero_arm_fore", seg_geo(.06, .05, .26), HS, C_HERO, parent=hup, loc=(.28, 1.74 - HIP, 0))
obj("hero_hand", sphere(.055, 10, 8), HS, C_HERO, parent=hup, loc=(.28, 2.0 - HIP, 0))
obj("cup", cylinder(.035, .028, .09, 14).move(0, .03, 0), mat("cup", 0xffffff, .5, emit=0xffffff, emit_k=.2), C_HERO, parent=hero, loc=(.6, 1.2, 0))

# ---------- Предметы ----------
C_P = coll("Предметы")
row = [0]


def place():
    row[0] += 1; return (row[0] % 8 * 2.2 - 8, 0, -4 - row[0] // 8 * 2.6)


STEEL = mat("steel", 0xc9ced3, .35, .8)
obj("chair", G().add(box(.62, .08, .6).move(0, .5, .05), box(.62, .62, .08).move(0, .82, .36),
                     cyl(.33, .33, -.04, .04, 0, 14).rotZ(math.pi / 2).move(.36, .33, .15), cyl(.33, .33, -.04, .04, 0, 14).rotZ(math.pi / 2).move(-.36, .33, .15)),
    mat("chair", 0x3a4147, .5, .4), C_P, loc=place())
obj("barrier", G().add(box(1.4, 1, .06).move(0, .55, 0), box(.5, .08, .4).move(0, .04, 0)), mat("barrier", 0xf2f2f0, .7), C_P, loc=place(), smooth=0)
obj("sai_post", box(.08, 1, .08), STEEL, C_P, loc=place(), smooth=0)
obj("sai_rail", box(.1, .08, 1), STEEL, C_P, loc=place(), smooth=0)   # 1 м: длину ставит сайт
obj("sai_head", cylinder(.22, .3, .55, 6), mat("sai_lamp", 0xffffff, .5, emit=0xffe2ad, emit_k=1), C_P, loc=place(), smooth=0)
obj("sai_rod", cylinder(.025, .025, 1.3, 4), STEEL, C_P, loc=place())
obj("lamp_panel", box(2.2, 1, .3), mat("lamp_green", 0x4dff8a, .5, emit=0x4dff8a, emit_k=2.6), C_P, loc=place(), smooth=0)
obj("lamp_back", box(2.6, 1.4, .2).move(0, 0, .2), mat("lamp_back", 0x2b2b2b, .8), C_P, loc=place(), smooth=0)
obj("lamp_arm", box(.25, .25, 1).move(0, 0, .75), mat("lamp_back", 0x2b2b2b), C_P, loc=place(), smooth=0)
TOOL = 0
obj("tool_stick", cyl(.014, .014, -.585, .585, 0, 5).rotX(.59).move(0, .52, -.22), mat("tool_white", 0xd9dde0, .6, .3), C_P, loc=place())
obj("tool_mop", box(.42, .05, .12).move(0, .03, -.56), mat("tool_mop", 0x1f5fa8, .6, .3), C_P, loc=place(), smooth=0)
obj("tool_broom", box(.34, .09, .08).move(0, .05, -.56), mat("tool_broom", 0xd9a441, .6, .3), C_P, loc=place(), smooth=0)
obj("tool_mhandle", cyl(.014, .014, -.3, .3, 0, 5).rotX(.9).move(0, .85, -.4), mat("tool_white", 0xd9dde0), C_P, loc=place())
obj("tool_machine", box(.55, .5, .7).move(0, .25, -.75), mat("tool_machine", 0x4b5563, .6, .3), C_P, loc=place(), smooth=0)
obj("pram_body", G().add(box(.42, .3, .7).move(0, .55, 0), sphere(.24, 12, 6, 0, math.pi / 2).scale(.9, 1, 1).move(0, .7, .18)), mat("pram_cloth", 0xffffff, .8), C_P, loc=place())
pf = G().add(box(.42, .03, .03).move(0, 1, .42), box(.025, .42, .025).rotX(.29).move(.2, .8, .36), box(.025, .42, .025).rotX(.29).move(-.2, .8, .36))
for x in (.2, -.2):
    for z in (.25, -.25):
        pf.add(cyl(.1, .1, -.02, .02, 0, 10).rotZ(math.pi / 2).move(x, .1, z), box(.025, .35, .025).move(x, .3, z * .88))
obj("pram_frame", pf, mat("pram_frame", 0x2a2c30, .5, .4), C_P, loc=place())
obj("kiswa_ring", torus(.07, .018, 6, 14), mat("copper", 0xb87333, .35, .9), C_P, loc=place())
obj("flag_pole", cyl(.025, .025, 0, 3.2, 0, 6), mat("flag_pole", 0x555555, .6), C_P, loc=place())
fc = G([(-.45, -.3, 0), (.45, -.3, 0), (.45, .3, 0), (-.45, .3, 0)], [[0, 1, 2, 3]]).move(.45, 2.9, 0)
obj("flag_cloth", fc, mat("flag_cloth", 0xf07a1e, .7, emit=0xf07a1e, emit_k=.5, double=True), C_P, loc=place(), smooth=0, recalc=False)
bird = G([(0, 0, .08), (-.22, .02, -.12), (0, 0, -.1), (0, 0, .08), (0, 0, -.1), (.22, .02, -.12)], [[0, 1, 2], [3, 4, 5]])
obj("bird", bird, mat("bird", 0xffffff, .9, double=True), C_P, loc=place(), smooth=0, recalc=False)
obj("zamzam_cooler", G().add(cyl(.42, .42, 0, 1.1, 0, 14), cyl(.3, .42, 1.1, 1.3, 0, 14)), mat("zamzam", 0x1fa9c9, .4, .2, emit=0x0b5a6a, emit_k=.5), C_P, loc=place())
STONE = mat("stone", 0xece3d0, .75)
obj("gallery_column", cylinder(.32, .4, 6.5, 8).move(0, 3.25, 0), STONE, C_P, loc=place())
obj("gallery_dome", sphere(2.3, 12, 6, 0, math.pi / 2).scale(1, .75, 1), STONE, C_P, loc=(0, 0, -16))

# ---------- Макам Ибрахим (v3.14) — ключевая деталь, вблизи ----------
# Размеры: хрустальный колпак 1,30 м, Ø 0,80 м внизу (Saudipedia); камень ≈ 40×40×20 см в оправе из золота и серебра, два следа
# стоп 27×14 см (Madain Project); каркас — латунь под золото, восьмигранник ≈ 1,3 м поперёк, основание — белый мрамор Каррара
# и зелёный гранит (Saudipedia: при короле Фахде); арочные панели с решёткой, карниз, крыша-пирамида, барабан, купол, полумесяц —
# по фотографиям; общая высота ≈ 3,2 м. Начало координат — центр на полу матафа, грань с локальной +z смотрит на Каабу (сайт).
C_MQ = coll("Макам")
MQ = empty("maqam", C_MQ)
Q8 = math.pi / 8


def rotY(g, a):
    c, s = math.cos(a), math.sin(a)
    return g.tf(lambda x, y, z: (x * c + z * s, y, -x * s + z * c))


def octo(R0, R1, y0, y1):   # восьмигранник (усечённая пирамида): R — радиус по углам, грань с центром на +z
    return rotY(cyl(R1, R0, y0, y1, seg=8), Q8)


def slab(poly, z0, z1):   # плоская фигура (x, y) толщиной z0…z1
    n = len(poly); v = [(x, y, z0) for x, y in poly] + [(x, y, z1) for x, y in poly]
    f = [list(range(n - 1, -1, -1)), list(range(n, 2 * n))] + [[i, (i + 1) % n, n + (i + 1) % n, n + i] for i in range(n)]
    return G(v, f)


def bar(p, q, w, d, z):   # брусок в плоскости панели от p до q
    L = math.dist(p, q); a = math.atan2(q[1] - p[1], q[0] - p[0])
    return box(L + w * 0.6, w, d).rotZ(a).move((p[0] + q[0]) / 2, (p[1] + q[1]) / 2, z)


def bar3(r0, y0, r1, y1, th, w):   # ребро по меридиану: от (r0, y0) до (r1, y1) на угле th
    L = math.hypot(r1 - r0, y1 - y0); al = math.atan2(r1 - r0, y1 - y0)
    return rotY(box(w, L, w).rotX(al).move(0, (y0 + y1) / 2, (r0 + r1) / 2), th)


def star(r1, r2, n=8):
    return [((r1 if i % 2 == 0 else r2) * math.sin(math.pi * i / n), (r1 if i % 2 == 0 else r2) * math.cos(math.pi * i / n)) for i in range(2 * n)]


def clip(p0, p1, poly):   # отрезок внутри выпуклого многоугольника (против часовой), Кирус — Бек
    t0, t1 = 0.0, 1.0; dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        nx, ny = -(b[1] - a[1]), b[0] - a[0]
        num = nx * (p0[0] - a[0]) + ny * (p0[1] - a[1]); den = nx * dx + ny * dy
        if abs(den) < 1e-12:
            if num < 0: return None
        elif den > 0: t0 = max(t0, -num / den)
        else: t1 = min(t1, -num / den)
        if t0 > t1: return None
    return (p0[0] + t0 * dx, p0[1] + t0 * dy), (p0[0] + t1 * dx, p0[1] + t1 * dy)


def inside(p, poly):
    return all((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= 0 for a, b in zip(poly, poly[1:] + poly[:1]))


def arch(aw, yb, ys, n=10, k=0.25):   # стрельчатая арка (против часовой): низ справа → вверх → вершина → низ слева
    c = aw * k; R = aw + c; ph = math.acos(-c / R)
    left = [(c + R * math.cos(math.pi - (math.pi - ph) * i / n), ys + R * math.sin(math.pi - (math.pi - ph) * i / n)) for i in range(n + 1)]
    right = [(-x, y) for x, y in reversed(left)][1:]
    return [(aw, yb)] + [p for p in reversed(left + right)] + [(-aw, yb)]


GOLD = mat("maqam_gold", 0xd9b24c, .26, 1)          # латунь под золото
GOLD2 = mat("maqam_lattice", 0xc29a3a, .34, 1)      # решётка — чуть темнее, чтобы читался рисунок
MARB = mat("maqam_marble", 0xf3f1ec, .32)
GRAN = mat("maqam_granite", 0x1d3b30, .22, .05)     # зелёный гранит
GREEN = mat("maqam_green", 0x0f3a2c, .45, .1)       # тёмно-зелёная эмаль фриза
SILV = mat("maqam_silver", 0xd2d4d8, .3, 1)         # серебряная оправа камня
FOOT = mat("maqam_foot", 0x4a3826, .9)              # углубления следов — тёмные, читаются как впадины
STONE = mat("maqam_rock", 0xc4ad84, .92)            # сам камень: желтовато-белый с бурым
PANE = mat("maqam_pane", 0xdff1f4, .04, double=True)
CRYS = mat("maqam_crystal", 0xe9f7f9, .03, double=True)

RC, Y0, Y1 = .68, .70, 2.16                          # каркас: радиус по углам, низ, верх
AP, HW = RC * math.cos(Q8), RC * math.sin(Q8)        # апофема 0,63 м и полуширина грани 0,26 м
AW, YB, YS = .185, .86, 1.80                          # арка панели: полуширина, низ, пята
ARCH = arch(AW, YB, YS)
FW = HW - .045                                        # рамка панели до пилястр

# основание: зелёный гранит, белый мрамор, гранитный пояс
obj("maqam_granite", G().add(octo(.88, .86, 0, .1), octo(.8, .8, .55, .6)), GRAN, C_MQ, parent=MQ, smooth=20)
obj("maqam_marble", G().add(octo(.76, .76, .1, .5), octo(.76, .8, .5, .55)), MARB, C_MQ, parent=MQ, smooth=20)

g = G().add(octo(.74, .71, .6, Y0 + .02))            # латунный цоколь каркаса
lat, pane, green = G(), G(), G()
frame = [(-FW, YB - .02), (FW, YB - .02), (FW, Y1 - .02), (-FW, Y1 - .02)]
plate = [(-FW, YB), (-FW, Y1 - .02), (FW, Y1 - .02), (FW, YB), (AW, YB)] + ARCH[1:-1] + [(-AW, YB)]
inner = arch(AW - .015, YB + .015, YS)
for k in range(8):
    th = k * math.pi / 4; fg = G()
    fg.add(slab(plate, AP - .012, AP + .004))                                           # лицевая плита с проёмом арки
    for a, b in zip(ARCH[1:-1], ARCH[2:-1]): fg.add(bar(a, b, .026, .03, AP + .01))      # профиль арки
    for s in (-1, 1): fg.add(bar((s * AW, YB), (s * AW, YS), .026, .03, AP + .01))
    for a, b in zip(frame, frame[1:] + frame[:1]): fg.add(bar(a, b, .03, .03, AP + .012))   # рамка панели
    fg.add(box(2 * FW, YB - Y0 - .02, .02).move(0, (Y0 + YB) / 2, AP))                   # нижняя филёнка
    fg.add(box(.24, .06, .014).move(0, (Y0 + YB) / 2, AP + .015))                        # картуш на филёнке
    for s in (-1, 1): fg.add(slab(star(.032, .014), AP + .004, AP + .016).move(s * .16, 2.06, 0))   # розетки в пазухах арки
    fg.add(slab(star(.026, .011), AP + .004, AP + .016).move(0, 2.10, 0))
    g.add(rotY(fg, th))
    lg, sp = G(), .066                                                                   # решётка: ромбы + звёздочки
    for i in range(-30, 31):
        for dirn in (1, -1):
            c = i * sp
            p0 = (c - 3, 1.33 - 3 * dirn); p1 = (c + 3, 1.33 + 3 * dirn)
            seg = clip(p0, p1, inner)
            if seg and math.dist(*seg) > .01: lg.add(bar(seg[0], seg[1], .011, .012, AP - .018))
    for i in range(-30, 31):
        for j in range(-30, 31):
            if (i + j) % 2: continue
            x, y = (i + j) * sp / 2, 1.33 + (j - i) * sp / 2   # пересечения двух семейств линий
            if inside((x, y), inner) and (i % 2 == 0): lg.add(slab(star(.017, .007), AP - .027, AP - .009).move(x, y, 0))
    lg.add(bar((0, YB + .015), (0, YS + .2), .014, .016, AP - .02))                    # средняя стойка
    lat.add(rotY(lg, th))
    pane.add(rotY(slab(ARCH, AP - .034, AP - .03), th))                                  # стекло в арке
    # пилястра на углу: ствол, две каннелюры, база, капитель
    ph = th + Q8; pg = G()
    pg.add(box(.07, Y1 - Y0, .07).move(0, (Y0 + Y1) / 2, 0), box(.09, .07, .09).move(0, Y0 + .055, 0), box(.095, .06, .095).move(0, Y1 - .05, 0),
           box(.11, .025, .11).move(0, Y1 - .01, 0))
    for s in (-1, 1): pg.add(box(.012, Y1 - Y0 - .2, .012).move(s * .018, (Y0 + Y1) / 2, .037))
    g.add(rotY(pg.move(0, 0, RC - .01), ph))
    # фриз: зелёная эмаль с золотыми картушами и розетками на углах
    gg = G().add(box(.4, .055, .012).move(0, Y1 + .085, .672))
    for s in (-1, 1): gg.add(slab(star(.022, .01), .666, .678).move(s * .235, Y1 + .085, 0))
    g.add(rotY(gg, th))
    # рёбра крыши и купола на углах
    g.add(bar3(.79, Y1 + .215, .36, Y1 + .4, ph, .03))
green.add(octo(.72, .72, Y1 + .03, Y1 + .14))
g.add(octo(.72, .74, Y1, Y1 + .03), octo(.73, .78, Y1 + .14, Y1 + .2), octo(.78, .78, Y1 + .2, Y1 + .215),
      octo(.78, .36, Y1 + .215, Y1 + .4),                                                 # карниз и крыша-пирамида
      octo(.3, .3, Y1 + .4, Y1 + .52), octo(.31, .33, Y1 + .52, Y1 + .55))                # барабан
for k in range(8):   # ниши барабана
    green.add(rotY(slab(arch(.05, Y1 + .42, Y1 + .47, 5), .3 * math.cos(Q8) - .005, .3 * math.cos(Q8) + .006), k * math.pi / 4))
obj("maqam_gold", g, GOLD, C_MQ, parent=MQ, smooth=20)
obj("maqam_lattice", lat, GOLD2, C_MQ, parent=MQ, smooth=0)
obj("maqam_green", green, GREEN, C_MQ, parent=MQ, smooth=20)
obj("maqam_pane", pane, PANE, C_MQ, parent=MQ, smooth=0)

# купол (чуть луковичный), рёбра, навершие, полумесяц
YD = Y1 + .55
dp = [(.3, YD), (.322, YD + .05), (.334, YD + .11), (.322, YD + .18), (.28, YD + .25), (.2, YD + .31), (.11, YD + .35), (.045, YD + .375), (0, YD + .385)]
dome = G().add(lathe(dp, 32))
for k in range(8):
    for a, b in zip(dp[:-2], dp[1:-1]): dome.add(bar3(a[0] + .008, a[1], b[0] + .008, b[1], k * math.pi / 4 + Q8, .016))
yt = YD + .385
dome.add(cyl(.02, .03, yt - .01, yt + .03, seg=12), ball(.038, 0, yt + .065, 0, w=16, h=10), cyl(.012, .02, yt + .1, yt + .13, seg=10),
         ball(.026, 0, yt + .15, 0, w=14, h=8), cyl(.008, .008, yt + .17, yt + .21, seg=8))
R, r, h = .07, .06, .03
yi = (R * R - r * r + h * h) / (2 * h); xi = math.sqrt(R * R - yi * yi)
a0, a1 = math.atan2(yi, xi), math.atan2(yi, -xi) - math.tau
b0, b1 = math.atan2(yi - h, -xi), math.atan2(yi - h, xi) + math.tau
cres = [(R * math.cos(a0 + (a1 - a0) * i / 20), R * math.sin(a0 + (a1 - a0) * i / 20)) for i in range(21)] + \
       [(r * math.cos(b0 + (b1 - b0) * i / 16), h + r * math.sin(b0 + (b1 - b0) * i / 16)) for i in range(1, 16)]
dome.add(slab(cres, -.008, .008).move(0, yt + .27, 0))
obj("maqam_dome", dome, GOLD, C_MQ, parent=MQ, smooth=40)

# внутри: золотая подставка, камень в серебряной оправе с золотыми поясами, два следа стоп
# верхний пояс — рамка, а не сплошная плита: сквозь неё видно сам камень (известняк ≈ 40×40×20 см, следы глубиной 9–10 см)
inn = G().add(octo(.34, .36, Y0, Y0 + .05), box(.4, .025, .4).move(0, Y0 + .065, 0), box(.39, .02, .39).move(0, Y0 + .085, 0),
              box(.39, .02, .03).move(0, Y0 + .27, .18), box(.39, .02, .03).move(0, Y0 + .27, -.18),
              box(.03, .02, .33).move(.18, Y0 + .27, 0), box(.03, .02, .33).move(-.18, Y0 + .27, 0))
obj("maqam_stand", inn, GOLD, C_MQ, parent=MQ, smooth=0)
# серебряный футляр: низ под камнем + четыре стенки по бокам (сверху открыт — в нём лежит камень со следами)
case = G().add(box(.37, .1, .37).move(0, Y0 + .125, 0),
               box(.37, .09, .02).move(0, Y0 + .22, .175), box(.37, .09, .02).move(0, Y0 + .22, -.175),
               box(.02, .09, .33).move(.175, Y0 + .22, 0), box(.02, .09, .33).move(-.175, Y0 + .22, 0))
obj("maqam_case", case, SILV, C_MQ, parent=MQ, smooth=0)
# камень толщиной 10 см, следы — настоящие впадины глубиной ≈ 8,5 см с наклонными стенками (булево вычитание в Blender)
st = obj("maqam_stone", box(.33, .1, .33).move(0, Y0 + .229, 0), STONE, C_MQ, parent=MQ, smooth=0)
bowl = [(0.0, -1.0), (.45, -.97), (.7, -.85), (.86, -.6), (.95, -.3), (1.0, 0.0), (1.0, .25), (0.0, .25)]
for s in (-1, 1):
    cut = obj("maqam_cut", lathe(bowl, 28).scale(.055, .085, .13).move(s * .072, Y0 + .279, 0), FOOT, C_MQ, parent=MQ, smooth=0)
    m = st.modifiers.new("cut", "BOOLEAN"); m.object = cut; m.operation = "DIFFERENCE"; m.solver = "EXACT"
    try: m.material_mode = "TRANSFER"
    except (AttributeError, TypeError): pass
    bpy.context.view_layer.update()
    me = bpy.data.meshes.new_from_object(st.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    st.modifiers.clear(); st.data = me
    bpy.data.objects.remove(cut)
# серебряная окантовка — кольцо по краю каждой впадины, чуть выше камня
rim = G()
for s in (-1, 1):
    rim.add(lathe([(1.0, 0), (1.17, 0), (1.17, .004), (1.0, .004), (1.0, 0)], 28).scale(.055, 1, .13).move(s * .072, Y0 + .279, 0))
obj("maqam_rim", rim, SILV, C_MQ, parent=MQ, smooth=0)
# хрустальный колпак: внешняя стенка 0,40 м и толстое дно-кольцо, внутренняя стенка 0,33 м
cr = [(.3, Y0 + .02), (.4, Y0 + .02), (.4, Y0 + .92)] + [(.4 * math.cos(t), Y0 + .92 + .4 * math.sin(t)) for t in (math.pi / 2 * i / 10 for i in range(1, 10))] + [(0, Y0 + 1.32)]
ci = [(.3, Y0 + .02), (.33, Y0 + .12), (.33, Y0 + .92)] + [(.33 * math.cos(t), Y0 + .92 + .33 * math.sin(t)) for t in (math.pi / 2 * i / 10 for i in range(1, 10))] + [(0, Y0 + 1.25)]
obj("maqam_crystal", G().add(lathe(cr, 40), lathe(ci, 40)), CRYS, C_MQ, parent=MQ, smooth=60, recalc=False)
for o in C_MQ.objects:
    if o.type == "MESH": print("MQV", o.name, len(o.data.vertices))

# ---------- Хиджр Исмаила (Хатым) и Мизаб ар-Рахма (v3.16) ----------
# Хатым: полукруглая стена 1,32 м (haram_meta hijr_h), толщина ≈ 1,2–1,3 м; контур — кольцо OSM из haram.glb (вершины ниже, по углу от
# конца у Иракского угла к концу у Шами), сглажено сплайном. Облицовка — белый мрамор: цоколь, гладкое тело, филёнки с инкрустацией
# серо-зелёным мрамором и розетками, поясок под карнизом, скруглённый карниз с выносом. Фонарей на стене не ставим: на нынешних
# фотографиях их не подтвердили. Начало координат — центр дуги на полу (meta −6,665; 8,763).
# Мизаб: 2,58 м, из них 58 см в стене (Saudipedia; ajel.sa), наружу ≈ 2,0 м; ширина дна 26 см, борта 23 см; тик в золоте, открыт
# сверху и в сторону Хиджра, на кромках шипы от голубей (ajel.sa); на конце «борода» (лихйа) — пластина, отводящая струю от стены.
# Начало координат — середина стены Б→Д на уровне дна жёлоба, локальная +z — наружу, к Хиджру.
C_HJ = coll("Хатым_и_Мизаб")
HJ = empty("hatim", C_HJ)
HC = (-6.665, 8.763)
H_IN = [(-2.12, 9.93), (-2.88, 11.41), (-4.11, 12.53), (-5.67, 13.14), (-7.33, 13.16), (-8.9, 12.59), (-10.21, 11.47), (-11.0, 9.94),
        (-11.19, 8.23), (-10.72, 6.57), (-9.69, 5.2)]
H_OUT = [(-1.01, 10.49), (-1.87, 12.17), (-3.45, 13.59), (-5.42, 14.36), (-7.54, 14.4), (-9.54, 13.68), (-11.2, 12.24), (-12.22, 10.31),
         (-12.45, 8.13), (-11.86, 6.02), (-10.68, 4.46)]


def crom(P, t):   # Catmull — Rom по точкам P, t от 0 до 1 (концы закреплены)
    n = len(P) - 1; u = min(max(t, 0), 1) * n; i = min(int(u), n - 1); s = u - i
    p0, p1, p2, p3 = P[max(i - 1, 0)], P[i], P[i + 1], P[min(i + 2, n)]
    return tuple(.5 * (2 * p1[k] + (-p0[k] + p2[k]) * s + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * s * s + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * s ** 3) for k in (0, 1))


def hframe(t):   # точка внутренней и внешней грани, нормаль (внутр → наруж) и касательная, в плане meta
    a, b = crom(H_IN, t), crom(H_OUT, t)
    dx, dy = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dy); n = (dx / L, dy / L)
    return a, b, L, n, (n[1], -n[0])


def h3(x, y, h):   # meta (x, y) и высота → three относительно центра дуги
    return (x - HC[0], h, -(y - HC[1]))


def hpt(t, k, off, h):   # k: 0 — внутренняя грань, 1 — внешняя (дробное — между ними); off — метры по нормали наружу
    a, b, L, n, _ = hframe(t)
    return h3(a[0] + (b[0] - a[0]) * k + n[0] * off, a[1] + (b[1] - a[1]) * k + n[1] * off, h)


def sweep(prof, t0, t1, seg):   # замкнутое сечение prof [(k, off, h)] протянуто по дуге от t0 до t1, торцы закрыты
    v, f, m = [], [], len(prof)
    for j in range(seg + 1):
        t = t0 + (t1 - t0) * j / seg; v += [hpt(t, *p) for p in prof]
    for j in range(seg):
        for i in range(m): f.append([j * m + i, j * m + (i + 1) % m, (j + 1) * m + (i + 1) % m, (j + 1) * m + i])
    f.append(list(range(m - 1, -1, -1))); f.append([seg * m + i for i in range(m)])
    return G(v, f)


ARC = [0.0]   # длина дуги по внешней и внутренней грани — чтобы филёнки были одной ширины
for side in (H_OUT, H_IN):
    s, pr = 0.0, crom(side, 0)
    for j in range(1, 401):
        q = crom(side, j / 400); s += math.dist(pr, q); pr = q
    ARC.append(s)
L_OUT, L_IN = ARC[1], ARC[2]
HN = 140
HMARB = mat("hatim_marble", 0xf5f3ee, .27)
HBASE = mat("hatim_base", 0xd6d2c9, .33)
HINL = mat("hatim_inlay", 0x8e9a92, .3, .02)          # серо-зелёный мрамор инкрустации
HCAP = mat("hatim_cap", 0xfbfaf6, .22)                # карниз — светлее и глаже, на нём блик
body = sweep([(0, 0, .12), (0, 0, 1.17), (1, 0, 1.17), (1, 0, .12)], 0, 1, HN)
base = sweep([(0, -.03, 0), (0, -.03, .1), (0, -.012, .135), (1, .012, .135), (1, .03, .1), (1, .03, 0)], 0, 1, HN)
cap = sweep([(0, -.035, 1.165), (0, -.05, 1.2), (0, -.05, 1.25), (0, -.035, 1.29), (0, 0, 1.312), (.5, 0, 1.335), (1, 0, 1.312), (1, .035, 1.29),
             (1, .05, 1.25), (1, .05, 1.2), (1, .035, 1.165)], 0, 1, HN)
obj("hatim_body", body, HMARB, C_HJ, parent=HJ, smooth=30)
obj("hatim_base", base, HBASE, C_HJ, parent=HJ, smooth=30)
obj("hatim_cap", cap, HCAP, C_HJ, parent=HJ, smooth=50)


def hloc(t, k, off, x, y, z):   # локальная рамка на грани: x — вдоль дуги, y — вверх, z — по нормали от грани наружу (sign по стороне)
    a, b, L, n, tg = hframe(t); sg = 1 if k else -1
    px, py = (b if k else a)
    return h3(px + tg[0] * x + n[0] * sg * (off + z), py + tg[1] * x + n[1] * sg * (off + z), y)


inl = G()
band = [(.0, .0), (.004, .0), (.004, .05), (.0, .05)]
for k, Lside, npan in ((1, L_OUT, 20), (0, L_IN, 16)):
    sg = 1 if k else -1
    pr = lambda o, h: (k, sg * o, h)
    inl.add(sweep([pr(0, 1.075), pr(.005, 1.075), pr(.005, 1.115), pr(0, 1.115)], 0, 1, HN))      # поясок под карнизом
    inl.add(sweep([pr(0, .17), pr(.005, .17), pr(.005, .195), pr(0, .195)], 0, 1, HN))           # поясок над цоколем
    dt = 1 / npan; m = .07 / Lside                                                                # отступ рамки 7 см
    for p in range(npan):
        t0, t1 = p * dt + m, (p + 1) * dt - m
        for h0, h1 in ((.26, .29), (.98, 1.01)):                                                 # верх и низ рамки
            inl.add(sweep([pr(0, h0), pr(.005, h0), pr(.005, h1), pr(0, h1)], t0, t1, 8))
        for tt in (t0, t1):                                                                      # стойки рамки
            w = .015 / Lside
            inl.add(sweep([pr(0, .26), pr(.005, .26), pr(.005, 1.01), pr(0, 1.01)], tt - w, tt + w, 1))
        tc = (p + .5) * dt                                                                       # розетка в центре филёнки
        st8 = slab(star(.085, .04), 0, .006).tf(lambda x, y, z, tc=tc, k=k: hloc(tc, k, 0, x, y + .635, z))
        inl.add(st8)
        ring = slab([(.13 * math.sin(TAU * i / 32), .13 * math.cos(TAU * i / 32)) for i in range(32)], 0, .003)
        inl.add(ring.tf(lambda x, y, z, tc=tc, k=k: hloc(tc, k, 0, x, y + .635, z)))
    # швы между плитами облицовки — между филёнками, чуть темнее
    for p in range(npan + 1):
        tt = min(max(p * dt, .0005), .9995); w = .006 / Lside
        inl.add(sweep([pr(-.001, .2), pr(.002, .2), pr(.002, 1.07), pr(-.001, 1.07)], tt - w, tt + w, 1))
obj("hatim_inlay", inl, HINL, C_HJ, parent=HJ, smooth=0)
# торцы стены у проходов — полированные плиты с рамкой
ends = G()
for t in (0.0, 1.0):
    a, b, L, n, tg = hframe(t); sg = 1 if t == 0 else -1   # касательная смотрит к началу дуги: у t=0 наружу, у t=1 внутрь
    mid = ((a[0] + b[0]) / 2 + tg[0] * sg * .003, (a[1] + b[1]) / 2 + tg[1] * sg * .003)
    for (x0, x1, y0, y1) in ((-L / 2 + .07, L / 2 - .07, .26, .29), (-L / 2 + .07, L / 2 - .07, .98, 1.01), (-L / 2 + .07, -L / 2 + .1, .26, 1.01), (L / 2 - .1, L / 2 - .07, .26, 1.01)):
        q = [(mid[0] + n[0] * x0, mid[1] + n[1] * x0), (mid[0] + n[0] * x1, mid[1] + n[1] * x1)]
        ends.add(G([h3(q[0][0] + tg[0] * sg * e, q[0][1] + tg[1] * sg * e, y) for e in (0, .005) for y in (y0, y1)] +
                   [h3(q[1][0] + tg[0] * sg * e, q[1][1] + tg[1] * sg * e, y) for e in (0, .005) for y in (y0, y1)],
                   [[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6], [1, 5, 7, 3], [0, 2, 6, 4]]))
obj("hatim_end", ends, HINL, C_HJ, parent=HJ, smooth=0)

# Мизаб
MZ = empty("mizab", C_HJ)
MGOLD = mat("mizab_gold", 0xdcb54e, .2, 1)
MORN = mat("mizab_orn", 0xb98f2e, .3, 1)
MIN, MOUT, MW, MS = .58, 2.0, .26, .23
mzg = G().add(box(MW + .05, .03, MIN + MOUT).move(0, -.015, (MOUT - MIN) / 2))                           # дно
for s in (-1, 1):
    mzg.add(box(.025, MS, MIN + MOUT).move(s * (MW / 2 + .0125), MS / 2 - .03, (MOUT - MIN) / 2))       # борта
    mzg.add(rotY(cylinder(.018, .018, MIN + MOUT, 10).rotX(math.pi / 2), 0).move(s * (MW / 2 + .0125), MS - .03, (MOUT - MIN) / 2))   # валик по кромке
    mzg.add(box(.035, .03, MIN + MOUT).move(s * (MW / 2 + .0125), -.04, (MOUT - MIN) / 2))             # нижний поясок
# «борода»: щит под концом жёлоба, низ — стрельчатый
mzg.add(slab([(-.16, -.02), (.16, -.02), (.16, -.24), (.05, -.38), (0, -.46), (-.05, -.38), (-.16, -.24)][::-1], MOUT - .03, MOUT - .005))
obj("mizab_gold", mzg, MGOLD, C_HJ, parent=MZ, smooth=35)
orn = G()
for s in (-1, 1):   # бортовой орнамент: рамка-кант, ряд розеток, филёнки (по фото — чеканка на бортах)
    xo = s * (MW / 2 + .026)
    for y in (.02, .17):
        orn.add(box(.006, .012, MOUT - .06).move(xo, y, MOUT / 2))
    for i in range(9):
        zc = .14 + i * (MOUT - .28) / 8
        orn.add(rotY(slab(star(.04, .018), 0, .006), s * math.pi / 2).move(xo - s * .003, .095, zc))
    for i in range(8):
        z0 = .14 + i * (MOUT - .28) / 8
        for dz in (.045, (MOUT - .28) / 8 - .045):
            orn.add(box(.006, .1, .008).move(xo, .095, z0 + dz))
# шипы от голубей по кромкам
for s in (-1, 1):
    for i in range(int(MOUT / .07)):
        orn.add(cylinder(.0, .006, .05, 4).move(s * (MW / 2 + .0125), MS - .03 + .035, .05 + i * .07))
# чеканка на «бороде»: звезда в круге
orn.add(slab(star(.07, .032), MOUT - .002, MOUT + .004).move(0, -.2, 0))
orn.add(slab([(.1 * math.sin(TAU * i / 28), -.2 + .1 * math.cos(TAU * i / 28)) for i in range(28)], MOUT - .003, MOUT + .001))
obj("mizab_orn", orn, MORN, C_HJ, parent=MZ, smooth=0)
for o in C_HJ.objects:
    if o.type == "MESH": print("HJV", o.name, len(o.data.vertices))

os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "props.blend"))
kw = dict(filepath=os.path.join(OUT, "props.glb"), export_format="GLB", export_texcoords=False, export_vertex_color="NONE", export_normals=True,
          export_yup=True, export_apply=False, export_cameras=False, export_lights=False,
          export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6,
          export_draco_position_quantization=14, export_draco_normal_quantization=10)
try:
    bpy.ops.export_scene.gltf(**kw)
except TypeError as e:
    print("ARG", e); kw = {k: v for k, v in kw.items() if not k.startswith(("export_cameras", "export_lights"))}
    bpy.ops.export_scene.gltf(**kw)
for n in ("props.blend", "props.glb"):
    print("OUT", n, os.path.getsize(os.path.join(OUT, n)))
print("OBJ", len([o for o in bpy.data.objects if o.type == "MESH"]))
