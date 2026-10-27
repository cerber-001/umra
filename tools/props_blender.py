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
