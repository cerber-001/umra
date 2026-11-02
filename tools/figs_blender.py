"""Реалистичные фигуры паломников для haram3d — из MPFB2 (CC0, makehuman.org).

Мужчина и женщина, по три уровня детализации (near / mid / far):
тело MPFB в позе «руки вниз» → прореживание (голова, глаза, кисти — бережнее) →
одежда-оболочки вокруг тела: изар, волосы, борода, брюки полиции; абая и хиджаб.

Каждая вершина несёт «кость» (uv.y после экспорта) и вес u (uv.x) — по ним
шейдер сайта сгибает руки, ноги, наклон и земной поклон (см. figMat в haram3d/index.html).
Материалы fig_m0..fig_m12 — номера частей, цвет задаёт шейдер.

Отдельно (проверка):
  Blender -b --factory-startup --python tools/figs_blender.py -- <папка>
    → превью PNG (спереди, сбоку, 3/4, лица) и число треугольников.
Из props_blender.py: figs_blender.build(collection, mk_mat).
"""
import bpy, bmesh, addon_utils, sys, os, math
import numpy as np
from mathutils import Vector, Matrix

HGT = {False: 1.74, True: 1.60}
TIERS = (("hi", int(os.environ.get("FIGS_HI", 9000)), 7.0, 40), ("near", int(os.environ.get("FIGS_NEAR", 3200)), 10.0, 24), ("mid", 800, 6.0, 12),
         ("far", 230, 3.0, 8), ("xfar", 70, 2.0, 5))
NI = {"hi": 0, "near": 0, "mid": 1, "far": 2, "xfar": 2}       # подробность оболочек: складки, очки
NR = {"hi": 14, "near": 10, "mid": 5, "far": 3, "xfar": 3}     # рядов в юбке
NMAT = 15
# m0 одежда/изар/абая · m1 кожа · m2 волосы/хиджаб · m3 борода · m5 предплечье · m6 правое плечо
# m7 торс (рида по диагонали) · m8 белок глаза · m9 зрачок · m10 губы · m11 обувь · m12 брюки
# m13 стёкла солнцезащитных очков · m14 оправа (глаз не видно: в исламе их не изображают)
CATS = {"up": ("upperarm",), "fore": ("lowerarm",), "hand": ("wrist", "metacarpal", "finger"),
        "leg": ("upperleg", "lowerleg", "foot", "toe"), "neck": ("neck",),
        "head": ("head", "jaw", "special", "oris", "levator", "orbicularis", "oculi", "temporalis", "risorius", "tongue", "eye."),
        "lips": None, "scalp": None, "ears": None, "body": None, "eye": ("helper-l-eye", "helper-r-eye")}
EXTRA = ("hairm", "beardm", "face")  # маски из prep: волосы, борода, открытое лицо
# v3.19 скелет: 12 звеньев, каждое вращается в плоскости «вперёд-вверх» вокруг своего сустава (шейдер — figMat):
# 0 таз, 1 живот, 2 грудь (с руками), 3 шея+голова, 4/5/6/7 правые бедро/голень/стопа/пальцы, 8/9/10/11 левые;
# 12/13 — юбка изара/абаи у бедра и у голени (смесь правой и левой ноги по x).
NK = 12
KPAR = (-1, 0, 1, 2, 0, 4, 5, 6, 0, 8, 9, 10)
KDEP = (0, 1, 2, 3, 1, 2, 3, 4, 1, 2, 3, 4)
KKEY = {"root": 0, "spine05": 0, "pelvis.L": 0, "pelvis.R": 0, "spine04": 1, "spine03": 1, "spine02": 2, "spine01": 2,
        "neck01": 3, "upperleg01.R": 4, "lowerleg01.R": 5, "foot.R": 6, "upperleg01.L": 8, "lowerleg01.L": 9, "foot.L": 10}


def skel_classes(rig):
    """кость → звено: ближайший предок из KKEY (пальцы ног — свои звенья)."""
    out = {}
    for b in rig.data.bones:
        x, c = b, 0
        while x is not None:
            if x.name.startswith("toe"):
                c = 7 if x.name.endswith(".R") else 11
                break
            if x.name in KKEY:
                c = KKEY[x.name]
                break
            x = x.parent
        out[b.name] = c
    return out


def ksub(c):
    return [k for k in range(NK) if k == c or any(a == c for a in kanc(k))]


def kanc(k):
    while KPAR[k] >= 0:
        k = KPAR[k]
        yield k


SUBM = np.array([[1.0 if (k == c or c in tuple(kanc(k))) else 0.0 for k in range(NK)] for c in range(NK)], np.float32)


def kclass(K, z=None, nz=0.0):
    """K (NK, n) — веса звеньев; звено = самое глубокое с заметным весом, вес w = доля звена и его потомков
    (остальное идёт за родителем: шейдер смешивает угол родителя и звена)."""
    tot = K.sum(0); dep = np.array(KDEP, np.float32)
    score = np.where(K > .04 * np.maximum(tot, 1e-6), dep[:, None] * 10 + K, -1)
    cls = score.argmax(0); w = (SUBM @ K)[cls, np.arange(K.shape[1])] / np.maximum(tot, 1e-6)
    w = np.clip(w, 0, 1)
    if z is not None:
        lo = tot < 1e-3
        cls[lo] = np.where(z[lo] > nz, 3, 0); w[lo] = 1
    return cls, w


def sstep(a, b, x):
    t = np.clip((np.asarray(x, float) - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def ctx(ob):
    return bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob], selected_editable_objects=[ob])


# ---------------------------------------------------------------- тело MPFB
def base(woman):
    addon_utils.enable("bl_ext.blender_org.mpfb", default_set=True)
    from bl_ext.blender_org.mpfb.services.humanservice import HumanService
    # v3.19: «как с конкурса красоты» — идеальные пропорции, стройность, у мужчин рельеф мышц
    md = {"gender": 0.0 if woman else 1.0, "age": 0.42, "muscle": 0.5 if woman else 0.68, "weight": 0.42 if woman else 0.48,
          "proportions": 1.0, "height": 0.6, "cupsize": 0.5, "firmness": 0.7, "race": {"asian": 0.45, "caucasian": 0.5, "african": 0.05}}
    h = HumanService.create_human(macro_detail_dict=md)
    rig = HumanService.add_builtin_rig(h, "default", import_weights=True)
    bpy.context.view_layer.update()
    ev = h.evaluated_get(bpy.context.evaluated_depsgraph_get())
    zs = [v.co.z for v in ev.data.vertices]
    H0 = max(zs) - min(zs)
    for s in ("L", "R"):
        sx = 1 if s == "L" else -1
        for bn, d in (("upperarm01", (sx * .07, 0, -1)), ("lowerarm01", (0, 0, -1)), ("wrist", (0, -.05, -1))):
            pb = rig.pose.bones[bn + "." + s]
            hd, tl = pb.head.copy(), pb.tail.copy()
            q = (tl - hd).normalized().rotation_difference(Vector(d).normalized())
            pb.matrix = Matrix.Translation(hd) @ q.to_matrix().to_4x4() @ Matrix.Translation(-hd) @ pb.matrix
            bpy.context.view_layer.update()
        # v3.19: пальцы вместе — у MPFB они веером (Т-поза); сводим 2, 4, 5 к среднему, оставляя лишь щель между ними
        m3 = rig.pose.bones["finger3-1." + s]
        d3 = (m3.tail - m3.head).normalized()
        for fg, keep in ((2, .25), (4, .25), (5, .35)):
            n = "finger%d-1.%s" % (fg, s)
            if n not in rig.pose.bones:
                continue
            pb = rig.pose.bones[n]
            hd, d = pb.head.copy(), (pb.tail - pb.head).normalized()
            t = Vector((d.x, d3.y + (d.y - d3.y) * keep, d.z)).normalized()
            q = d.rotation_difference(t)
            pb.matrix = Matrix.Translation(hd) @ q.to_matrix().to_4x4() @ Matrix.Translation(-hd) @ pb.matrix
            bpy.context.view_layer.update()
        # большой палец у MPFB оттопырен почти на 50° вперёд («коготь») — прижимаем его к указательному
        pb, p2 = rig.pose.bones["finger1-1." + s], rig.pose.bones["finger2-1." + s]
        hd, d = pb.head.copy(), (pb.tail - pb.head).normalized()
        q = d.rotation_difference(d.lerp((p2.tail - p2.head).normalized(), .55).normalized())
        pb.matrix = Matrix.Translation(hd) @ q.to_matrix().to_4x4() @ Matrix.Translation(-hd) @ pb.matrix
        bpy.context.view_layer.update()
        # кисть в покое: пальцы мягко согнуты к ладони, мизинец чуть больше
        for fg, ang in ((1, (5, 6, 4)), (2, (6, 11, 6)), (3, (8, 13, 7)), (4, (10, 14, 8)), (5, (11, 16, 10))):
            for i, a in enumerate(ang, 1):
                n = "finger%d-%d.%s" % (fg, i, s)
                if n in rig.pose.bones:
                    pb = rig.pose.bones[n]
                    hd = pb.head.copy()
                    pb.matrix = Matrix.Translation(hd) @ Matrix.Rotation(math.radians(a) * sx, 4, "Y") @ Matrix.Translation(-hd) @ pb.matrix
                    bpy.context.view_layer.update()
        pb = rig.pose.bones["upperleg01." + s]
        hip, ft = pb.head.copy(), rig.pose.bones["foot." + s].head.copy()
        v = ft - hip
        t = Vector((sx * .095 * H0 / HGT[woman] - hip.x, v.y, v.z))
        q = v.normalized().rotation_difference(t.normalized())
        pb.matrix = Matrix.Translation(hip) @ q.to_matrix().to_4x4() @ Matrix.Translation(-hip) @ pb.matrix
        bpy.context.view_layer.update()
    J = {k: (rig.matrix_world @ rig.pose.bones[k].head).copy()
         for k in ("upperarm01.R", "lowerarm01.R", "wrist.R", "upperleg01.R", "lowerleg01.R", "foot.R", "toe3-1.R",
                   "spine04", "spine02", "neck01", "head")}
    kcls = skel_classes(rig)
    with ctx(h):
        if h.data.shape_keys:
            bpy.ops.object.shape_key_remove(all=True, apply_mix=True)
        for m in list(h.modifiers):
            if m.type == "MASK":
                h.modifiers.remove(m)
        for m in list(h.modifiers):
            if m.type == "ARMATURE":
                bpy.ops.object.modifier_apply(modifier=m.name)
    h.parent = None
    bpy.data.objects.remove(rig)
    # группы вершин → массивы весов
    names = [g.name for g in h.vertex_groups]
    cat_of = {}
    for i, n in enumerate(names):
        for c, pre in CATS.items():
            ok = (n == c) if pre is None else (n in pre) if c == "eye" else n.startswith(pre)
            if ok:
                cat_of[i] = c
                break
    me = h.data
    nv = len(me.vertices)
    W = {c: np.zeros(nv, np.float32) for c in CATS}
    for v in me.vertices:
        for g in v.groups:
            c = cat_of.get(g.group)
            if c:
                W[c][v.index] += g.weight
    for c in CATS:
        a = me.attributes.new("a_" + c, "FLOAT", "POINT")
        a.data.foreach_set("value", np.minimum(W[c], 1.0))
    # скелет: сумма весов костей по 12 звеньям (таз, живот, грудь+руки, голова, бедро/голень/стопа/пальцы П и Л)
    K = np.zeros((NK, nv), np.float32)
    gk = {i: kcls[n] for i, n in enumerate(names) if n in kcls}
    for v in me.vertices:
        for g in v.groups:
            c = gk.get(g.group)
            if c is not None:
                K[c, v.index] += g.weight
    for c in range(NK):
        me.attributes.new("a_k%d" % c, "FLOAT", "POINT").data.foreach_set("value", K[c])
    keep = (W["body"] > .5) | (W["eye"] > .5)
    bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[i] for i in np.nonzero(~keep)[0]], context="VERTS")
    bm.to_mesh(me); bm.free()
    h.vertex_groups.clear()
    # разворот лицом к +Y (−z в three), правый бок на +X; масштаб; пол z=0; плечо y=0
    s = HGT[woman] / H0
    M = Matrix.Rotation(math.pi, 4, "Z") @ Matrix.Scale(s, 4)
    me.transform(M)
    J = {k: M @ v for k, v in J.items()}
    co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    off = Vector((0, -J["upperarm01.R"].y, -co[:, 2].min()))
    me.transform(Matrix.Translation(off))
    J = {k: v + off for k, v in J.items()}
    me.update()
    h.name = "fig_base_" + ("w" if woman else "m")
    return h, J


def arrays(me):
    n = len(me.vertices)
    co = np.empty(n * 3); me.vertices.foreach_get("co", co)
    A = {}
    for c in list(CATS) + list(EXTRA) + ["k%d" % i for i in range(NK)]:
        a = np.zeros(n, np.float32)
        if "a_" + c in me.attributes:
            me.attributes["a_" + c].data.foreach_get("value", a)
        A[c] = a
    return co.reshape(-1, 3), A


# ---------------------------------------------------------------- мерки
def metrics(P, A, J, woman):
    m = {}
    head = (A["head"] > .5) & (A["neck"] < .3) & (A["ears"] < .5)
    eye = A["eye"] > .5
    m["eye_z"] = P[eye, 2].mean()
    m["eyes"] = [P[eye & (P[:, 0] > 0)].mean(0), P[eye & (P[:, 0] < 0)].mean(0)]
    m["top_z"] = P[:, 2].max()
    hp = P[head]
    m["hcy"] = hp[:, 1].mean()
    front = hp[hp[:, 1] > m["hcy"]]
    m["chin_z"] = front[:, 2].min()
    m["mouth_z"] = P[A["lips"] > .5, 2].mean()
    m["hair_z"] = m["eye_z"] + .065
    m["HIPZ"] = J["upperleg01.R"].z
    m["WZ"] = m["HIPZ"] + (.10 if woman else .12)
    m["TY"] = m["HIPZ"] + .1
    m["JX"], m["JZ"] = J["upperarm01.R"].x, J["upperarm01.R"].z
    m["ZT"] = m["JZ"] - .14   # абая идёт от груди (под накидкой хиджаба), а не от пояса
    m["E"] = J["lowerarm01.R"]; m["Wr"] = J["wrist.R"]
    m["z_cb"] = m["JZ"] - .08
    m["KZ"] = J["lowerleg01.R"].z
    m["J"] = J
    return m


def fdd(P, m):  # диагональ риды: >0 — открытое правое плечо
    return (P[:, 0] - .06) * .54 + (P[:, 2] - (m["JZ"] - .03)) * .84


def armw(A):
    return A["up"] + A["fore"] + A["hand"]


def face_oval(P, m, mth=0.0, mz=0.0):
    zc = (m["chin_z"] + m["hair_z"]) / 2; rz = (m["hair_z"] - m["chin_z"]) / 2
    th = np.degrees(np.abs(np.arctan2(P[:, 0], P[:, 1] - m["hcy"])))
    e = np.clip(1 - ((P[:, 2] - zc) / (rz + mz)) ** 2, 0, 1)
    return (th < 60 * np.sqrt(e) + mth) & (P[:, 2] > m["chin_z"] - mz) & (P[:, 2] < m["hair_z"] + mz)


# ---------------------------------------------------------------- подготовка (полное разрешение)
def prep(h, m, woman):
    """Полное разрешение: срезать скрытое одеждой; волосы, борода, хиджаб — участки самой головы,
    приподнятые по нормали (граница идёт по рёбрам сетки, форма — по черепу)."""
    me = h.data
    P, A = arrays(me)
    aw = armw(A)
    z = P[:, 2]
    th = np.degrees(np.abs(np.arctan2(P[:, 0], P[:, 1] - m["hcy"])))
    hd = ((A["head"] > .3) | (A["neck"] > .3) | (A["ears"] > .3)) & (aw < .2)
    bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
    hairm = np.zeros(len(P)); beardm = np.zeros(len(P)); face = np.zeros(len(P)); ridam = np.zeros(len(P))
    if not woman:
        hid = (z > .43) & (z < m["WZ"] - .025) & (aw < .2)
        push = np.zeros(len(P))
        tor = (z > m["WZ"] - .02) & (A["head"] < .3) & (A["neck"] < .3) & (aw < .2)
        push[tor] = .01 * np.clip(-fdd(P[tor], m) / .015, 0, 1)
        push[(A["up"] > .3) & (P[:, 0] < 0)] = .012
        hl = m["eye_z"] + .065 - .125 * sstep(.25, .75, th / 180)
        hairm = hd * (A["eye"] < .5) * (A["ears"] < .5) * (A["neck"] < .5) * sstep(-.004, .004, z - hl)
        mz = m["mouth_z"]
        lim = np.where(th < 35, mz + .016, mz + .012 + .03 * np.clip((th - 35) / 55, 0, 1))
        beardm = (hd * (th < 100) * sstep(-.004, .004, lim - z) * (z > m["chin_z"] - .035) * (A["lips"] < .3) * (A["eye"] < .5)
                  * ~((th < 12) & (z > mz + .012) & (z < mz + .02)))  # желобок под носом
        push += hairm * (.004 + .008 * sstep(m["eye_z"], m["top_z"], z)) + beardm * .005
        # рида (идтиба): грудь и левое плечо под тканью, правое плечо открыто по диагонали fdd
        ridam = (((z > m["WZ"] - .02) & (A["head"] < .3) & (A["neck"] < .3) & (A["fore"] + A["hand"] < .2)
                  & ~((A["up"] > .3) & (P[:, 0] > 0)) & (fdd(P, m) < 0)) | ((A["up"] > .3) & (P[:, 0] < 0))).astype(float)
    else:
        hid = (z > .07) & (z < m["ZT"] - .05) & (aw < .2)
        # уши — под ткань: прижать к черепу
        ear = A["ears"] > .3
        hx = hd & ~ear & (A["head"] > .5)
        for i in np.nonzero(ear)[0]:
            sel = hx & (np.abs(z - z[i]) < .012)
            if sel.any():
                hw = np.abs(P[sel, 0]).max() * .97
                if abs(P[i, 0]) > hw:
                    bm.verts[i].co.x = math.copysign(hw, P[i, 0])
        chin, hz = m["chin_z"] - .008, m["hair_z"] + .012
        zc, rz = (chin + hz) / 2, (hz - chin) / 2
        e = np.clip(1 - ((z - zc) / rz) ** 2, 0, 1)
        face = (hd * (A["ears"] < .3) * (1 - sstep(-4, 6, th - 74 * e ** .3))
                * sstep(chin - .006, chin + .006, z) * (1 - sstep(hz - .012, hz + .004, z)))
        for ec in m["eyes"]:  # глаза и уголки целиком в открытом лице
            r = ((P[:, 0] - ec[0]) / .03) ** 2 + ((z - ec[2]) / .018) ** 2
            face = np.maximum(face, hd * (P[:, 1] > m["hcy"]) * (1 - sstep(.8, 1.1, r)))
        # химар: шея и плечи — ткань, спадающая от подбородка; кромка ниже на груди, выше на руках
        neck = (A["neck"] > .3) & (A["head"] < .5)
        cape = sstep(-.006, .006, z - (m["JZ"] - .13 - .04 * np.clip(P[:, 1] / .1, 0, 1) + .05 * np.clip(np.abs(P[:, 0]) / .2, 0, 1)))
        cape = np.where((A["fore"] + A["hand"] > .2) | (z < m["WZ"]), 0, cape) * (1 - sstep(.2, .6, A["up"]))  # кромка идёт поверх плеча, не по руке
        face = np.where(neck, 0, face)
        push = np.where((A["head"] < .3) & (A["hand"] < .3) & (z > m["WZ"] - .03), .01 + .008 * cape, 0)
        push = np.where(neck, .022 + .01 * sstep(m["z_cb"], chin, z), push)
        push = np.where(hd & ~neck & (z > chin - .045), (1 - face) * (.013 + .012 * sstep(m["eye_z"], m["top_z"], z)), push)
        face = np.where(hd | neck, face, 0)
        hairm = np.maximum(cape, (hd | neck)) * (1 - face)  # у женщин hairm = ткань хиджаба (лицо открыто)
    for nm, arr in (("hairm", hairm), ("beardm", beardm), ("face", face)):  # до удаления: потом индексы сбиты
        lay = bm.verts.layers.float.get("a_" + nm) or bm.verts.layers.float.new("a_" + nm)
        for v in bm.verts:
            v[lay] = float(arr[v.index])
    # класс грани (2 — волосы/хиджаб, 3 — борода) живёт в material_index и переживает Decimate;
    # по границе классов сетка разрезана: кромка — граница острова, Decimate её не ломает
    for f in bm.faces:
        ix = [v.index for v in f.verts]
        lp = A["lips"][ix]
        f.material_index = (5 if lp.mean() > .5 or (lp.max() > .5 and abs(z[ix].mean() - m["mouth_z"]) < .004) else 6 if A["eye"][ix].mean() > .5 else 2 if hairm[ix].mean() > .5
                            else 3 if beardm[ix].mean() > .5 else 8 if A["hand"][ix].mean() > .5 else 7 if (A["fore"] + A["hand"])[ix].mean() > .5
                            else 4 if ridam[ix].mean() > .5 else 0)
    # кромка по рёбрам — «лесенка»; сгладить её как кривую: вершина границы -> к середине соседей по границе
    bnd = {}
    for e in bm.edges:
        if len(e.link_faces) == 2 and e.link_faces[0].material_index != e.link_faces[1].material_index:
            a_, b_ = e.verts
            bnd.setdefault(a_.index, []).append(b_.index); bnd.setdefault(b_.index, []).append(a_.index)
    co = np.array([v.co[:] for v in bm.verts])
    for _ in range(6):
        nw = co.copy()
        for i, nb_ in bnd.items():
            if len(nb_) == 2:
                nw[i] = .5 * co[i] + .25 * (co[nb_[0]] + co[nb_[1]])
        co = nw
    # соседний ряд выровнять, чтобы четырёхугольники у кромки не сплющило
    near_ = {e.other_vert(bm.verts[i]).index for i in bnd for e in bm.verts[i].link_edges} - set(bnd)
    for _ in range(2):
        nw = co.copy()
        for i in near_:
            v = bm.verts[i]
            nw[i] = .5 * co[i] + .5 * np.mean([co[e.other_vert(v).index] for e in v.link_edges], 0)
        co = nw
    for i in list(bnd) + list(near_):
        bm.verts[i].co = co[i]
    # подъём ткани/волос нарастает от кромки за 3 ряда сетки: иначе крайний ряд кожи тянется «зубцами»
    ring = np.full(len(P), 9)
    for v in bm.verts:
        cs = {f.material_index for f in v.link_faces} - {7, 8}   # локоть и запястье — не кромка
        if len(cs) > 1 and cs & {0, 5, 6}:  # кромка у открытой кожи, губ, глаз
            ring[v.index] = 0
    for k in range(1, 4):
        for v in bm.verts:
            if ring[v.index] == k - 1:
                for e in v.link_edges:
                    o = e.other_vert(v).index
                    ring[o] = min(ring[o], k)
    # внутри ткани поле подъёма сгладить: иначе ступенька шея/голова даёт «воротник» гранями
    for _ in range(8):
        nw = push.copy()
        for v in bm.verts:
            if ring[v.index] > 0 and push[v.index]:
                nw[v.index] = .5 * push[v.index] + .5 * np.mean([push[e.other_vert(v).index] for e in v.link_edges])
        push = nw
    push = push * np.array([.12, .35, .7, 1, 1, 1, 1, 1, 1, 1])[ring]
    bm.normal_update()
    for v in bm.verts:
        if push[v.index]:
            v.co += v.normal * float(push[v.index])
    dele = [f for f in bm.faces if all(hid[v.index] for v in f.verts)]  # до разреза: потом индексы новые
    # режем только кромки поднятых классов; губы/глаза с кожей и бородой — общие рёбра (без щелей после Decimate)
    cut = [e for e in bm.edges if len(e.link_faces) == 2 and e.link_faces[0].material_index != e.link_faces[1].material_index
           and not {e.link_faces[0].material_index, e.link_faces[1].material_index} & {5, 6, 7, 8}]
    bmesh.ops.split_edges(bm, edges=cut)
    bmesh.ops.delete(bm, geom=dele, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(me); bm.free()
    P, A = arrays(me)
    g = h.vertex_groups.new(name="keep")
    # кромка волос/бороды/хиджаба (граница острова) — держать
    bd = np.zeros(len(P))
    tb = bmesh.new(); tb.from_mesh(me)
    for e in tb.edges:
        if e.is_boundary or (len(e.link_faces) == 2 and e.link_faces[0].material_index != e.link_faces[1].material_index):
            bd[e.verts[0].index] = bd[e.verts[1].index] = 1
    tb.free()
    kw = np.maximum.reduce([A["head"] * (A["neck"] < .5), A["eye"], A["neck"] * .3, A["hand"] * .7,
                            (A["leg"] > .5) * (P[:, 2] < .12) * .4, A["lips"], bd])
    # Collapse: вес 0 — вершина заморожена, 1 — свободна; цена ребра растёт на длину·(2−w1−w2)·factor
    for i, w in enumerate(kw):
        g.add([i], float(1 - .92 * min(w, 1)), "REPLACE")


# ---------------------------------------------------------------- оболочки
TH = {}


def dirs(seg):
    if seg not in TH:
        th = 2 * np.pi * np.arange(seg) / seg
        TH[seg] = (th, np.stack([np.sin(th), np.cos(th)], 1))
    return TH[seg]


def sup(P, sel, cx, cy, seg, pad=0.0):
    th, D = dirs(seg)
    Q = P[sel][:, :2] - (cx, cy)
    if len(Q) == 0:
        return None
    r = (Q @ D.T).max(axis=0)
    r = np.maximum(r, (np.roll(r, 1) + 2 * r + np.roll(r, -1)) / 4)
    return r + pad


def rad(P, sel, cx, cy, seg, pad=0.0):
    """Радиальный профиль среза: повторяет талию, в отличие от выпуклого sup."""
    Q = P[sel][:, :2] - (cx, cy)
    if len(Q) == 0:
        return None
    b = ((np.arctan2(Q[:, 0], Q[:, 1]) % (2 * np.pi)) / (2 * np.pi) * seg + .5).astype(int) % seg
    r = np.zeros(seg)
    np.maximum.at(r, b, np.hypot(Q[:, 0], Q[:, 1]))
    ok = r > 0
    if not ok.all():
        ix = np.arange(seg)
        r = np.interp(ix, ix[ok], r[ok], period=seg)
    for _ in range(2):
        r = (np.roll(r, 1) + 2 * r + np.roll(r, -1)) / 4
    return r + pad


def band(P, z, dz):
    return np.abs(P[:, 2] - z) < dz


class Shells:
    def __init__(s, bm, uv, sk):
        s.bm = bm
        s.uv, s.sk = uv, sk
        s.skf = lambda co: (3, 1.0)   # звено скелета и вес для каждой новой вершины (слой sk)

    def face(s, vs, mat, bone, ufun, want, smooth=True):
        try:
            f = s.bm.faces.new(vs)
        except ValueError:
            return None
        f.material_index = mat; f.smooth = smooth
        f.normal_update()
        if f.normal.dot(want) < 0:
            f.normal_flip()
        for l in f.loops:
            l[s.uv].uv = (float(ufun(l.vert.co.z)), 1.0 - bone)
            c, w = s.skf(l.vert.co)
            l[s.sk].uv = (float(w), 1.0 - c)
        return f

    def polar(s, rings, seg, bone, mat, ufun, keep=None, flip=False, cap=None, want=None):
        """rings: [(z, cx, cy, r[seg])] снизу вверх; keep(z, θ) — оставить грань."""
        th, D = dirs(seg)
        V = [[s.bm.verts.new((cx + r[j] * D[j, 0], cy + r[j] * D[j, 1], z)) for j in range(seg)] for z, cx, cy, r in rings]
        for k in range(len(rings) - 1):
            for j in range(seg):
                j1 = (j + 1) % seg
                vs = [V[k][j], V[k + 1][j], V[k + 1][j1], V[k][j1]]
                c = sum((v.co for v in vs), Vector()) / 4
                tc = math.atan2(c.x - (rings[k][1] + rings[k + 1][1]) / 2, c.y - (rings[k][2] + rings[k + 1][2]) / 2)
                if keep and not keep(c.z, tc):
                    continue
                w = want or Vector((c.x - rings[k][1], c.y - rings[k][2], 0)) * (-1 if flip else 1)
                s.face(vs, mat, bone, ufun, w)
        if cap is not None:
            z, cx, cy, _ = rings[-1]
            t = s.bm.verts.new((cx, cy, cap))
            for j in range(seg):
                s.face([V[-1][j], V[-1][(j + 1) % seg], t], mat, bone, ufun, Vector((0, 0, 1)))
        loose = [v for row in V for v in row if not v.link_faces]
        if loose:
            bmesh.ops.delete(s.bm, geom=loose, context="VERTS")

    def annulus(s, z, cx, cy, r_in, r_out, seg, bone, mat, ufun, up=True):
        s.polar([(z, cx, cy, r_in), (z, cx, cy, r_out)], seg, bone, mat, ufun, want=Vector((0, 0, 1 if up else -1)))


def shells(S, P, A, m, woman, tier, seg, police):
    ni, nr = NI[tier], NR[tier]   # xfar — как far, но реже сетка и меньше треугольников
    aw = armw(A)
    HIPZ = m["HIPZ"]
    legu = lambda z: min(max((HIPZ - z) / (HIPZ - .05), 0.0), 1.0)
    one = lambda z: 1.0
    th, D = dirs(seg)
    head = (A["head"] > .5) & (A["ears"] < .5)
    hcy = m["hcy"]
    KZ = m["KZ"]

    tor = TORSO[woman]

    def skirt(co):   # юбка — как тело прямо под ней (CHAIN): выше таза — торс, ниже — бедро (12) и голень (13), смесь П/Л по x
        v = CHAIN[woman](co)
        if v < 0:
            return (1, -v) if v >= -1 else (2, min(-v - 1, 1.0))
        return (12, v) if v <= 1 else (13, min(v - 1, 1.0))
    S.skf = skirt
    if not woman:
        # изар
        body = aw < .2
        cy = P[body & band(P, HIPZ, .05), 1].mean()
        zs = np.linspace(.38, m["WZ"], nr)
        rings = []
        for z in zs:
            t = (z - .38) / (m["WZ"] - .38)
            b_ = float(sstep(HIPZ - .1, m["WZ"], z))     # у пояса ткань повторяет тело
            r = (1 - b_) * sup(P, body & band(P, z, .04), 0, cy, seg) + b_ * rad(P, body & band(P, z, .015), 0, cy, seg)
            r = r + .008 + .012 * (1 - t) ** 1.5
            if ni == 0:
                r = r + .004 * (1 - t) * np.sin(7 * th + .7)
            rings.append((z, 0, cy, r))
        S.polar(rings, seg, 0, 0, legu)
        r_in = rad(P, body & band(P, m["WZ"], .015), 0, cy, seg, -.005)
        S.annulus(m["WZ"], 0, cy, r_in, rings[-1][3], seg, 0, 0, legu)
        if ni < 2:   # подшивка: край ткани с изнанки — в поклоне под подол видно, а стопы выходят свободно
            S.polar([(.38, 0, cy, rings[0][3]), (.40, 0, cy, rings[0][3] * .72)], seg, 0, 0, legu, want=Vector((0, 0, -1)))
        # брюки полиции: звено — как у ближайшей точки тела
        if police and ni < 2:
            kd = FULL_KD[woman]
            S.skf = lambda co: tuple(kd(co))
            sg = 16 if tier == "hi" else (12, 6)[ni]
            for sx, bone in ((1, 6), (-1, 7)):
                side = (A["leg"] > .3) & (P[:, 0] * sx > 0) & (aw < .2)
                zs = np.linspace(.105, m["WZ"], (10, 4)[ni])  # от щиколотки: ниже — стопа, брюки не раструбом
                rings = []
                for z in zs:
                    sel = side & band(P, z, .03) & ((P[:, 1] < P[side & band(P, .2, .03), 1].mean() + .06) | (z > .2))
                    if z > HIPZ - .05 or not sel.any():
                        cx, cyl = sx * .07, cy
                        sel = (aw < .2) & (P[:, 0] * sx > -.02) & band(P, z, .03)
                    else:
                        cx, cyl = P[sel, 0].mean(), P[sel, 1].mean()
                    rings.append((z, cx, cyl, sup(P, sel, cx, cyl, sg, .005 + .007 * (1 - legu(z)))))
                S.polar(rings, sg, bone, 12, legu)
    else:
        body = aw < .2
        cy = P[body & band(P, HIPZ, .05), 1].mean()
        # абая: А-силуэт от груди; верх ныряет под поверхность торса — шва и ступеньки на поясе нет
        ZT = m["ZT"]
        rT = rad(P, body & band(P, ZT, .015), 0, cy, seg)
        rH = rad(P, body & band(P, HIPZ + .02, .03), 0, cy, seg)
        rings = []
        for z in np.linspace(.04, ZT, nr):
            t = (z - .04) / (ZT - .04)
            if z >= HIPZ:
                q = (z - HIPZ) / (ZT - HIPZ)
                r = np.maximum((1 - q) * rH + q * rT, rad(P, body & band(P, z, .015), 0, cy, seg))
            else:
                q = (HIPZ - z) / (HIPZ - .04)
                r = np.maximum(rH, sup(P, body & band(P, max(z, .1), .04), 0, cy, seg)) + .05 * q ** 1.4
            r = r + .004 + .012 * sstep(ZT, ZT - .04, z)
            if ni == 0:
                r = r + .010 * (1 - t) ** 1.2 * (np.sin(7 * th + .5) + (.5 * np.sin(13 * th + 1.3) if seg > 30 else 0))
            rings.append((z, 0, cy, r))
        S.polar(rings, seg, 0, 0, legu)
        if ni < 2:
            S.polar([(.04, 0, cy, rings[0][3]), (.065, 0, cy, rings[0][3] * .72)], seg, 0, 0, legu, want=Vector((0, 0, -1)))


def sandals(S, P, A, m, tier):
    """Сандалии в ихраме: подошва и один широкий ремешок поперёк стопы (подъём и щиколотка открыты)."""
    if tier not in ("hi", "near", "mid"):
        return
    sg, n = {"hi": (32, 10), "near": (20, 6), "mid": (12, 3)}[tier]
    kd = FULL_KD[False]
    S.skf = lambda co: tuple(kd(co))
    uf = lambda z: 0.0
    y0 = m["J"]["foot.R"].y + .62 * (m["J"]["toe3-1.R"].y - m["J"]["foot.R"].y)
    for sx in (1, -1):
        leg = (A["leg"] > .3) & (P[:, 0] * sx > 0)
        foot = leg & (P[:, 2] < .04)
        cx, cy = P[foot, 0].mean(), P[foot, 1].mean()
        r = rad(P, foot, cx, cy, sg, .007)
        S.polar([(-.001, cx, cy, r * .985), (.011, cx, cy, r)], sg, 1, 11, uf)
        S.annulus(.011, cx, cy, r * .55, r, sg, 1, 11, uf)
        S.annulus(-.001, cx, cy, r * .1, r * .985, sg, 1, 11, uf, up=False)
        X = P[leg & (np.abs(P[:, 1] - y0) < .012) & (P[:, 2] < .09)][:, [0, 2]]
        xc = X[:, 0].mean()
        pts = []
        for j in range(n + 1):
            a = math.pi * j / n
            d = np.array((math.cos(a), math.sin(a)))
            rj = float(((X - (xc, .008)) @ d).max()) + .003
            pts.append((xc + rj * d[0], .008 + rj * d[1], d))
        V = [[S.bm.verts.new((x, y0 + dy, z)) for dy in (-.012, .012)] for x, z, d in pts]
        for j in range(n):
            d = pts[j][2] + pts[j + 1][2]
            S.face([V[j][0], V[j][1], V[j + 1][1], V[j + 1][0]], 11, 1, uf, Vector((d[0], 0, d[1])))


# ---------------------------------------------------------------- солнцезащитные очки
GL = {False: (.0275, .0215), True: (.0255, .0205)}   # полуширина/полувысота стекла (вайфарер)


def glasses(S, P, A, m, woman, tier):
    """Очки «вайфарер»: стекло m13 и оправа m14 по форме лица. Глаз не видно (в исламе их не изображают).
    near — стекло + толстая оправа с торцом, перемычка, дужки до ушей; mid — проще; far — по четырёхугольнику; xfar — нет."""
    if tier == "xfar":
        return
    ni = NI[tier]
    S.skf = lambda co: (3, 1.0)
    one = lambda z: 1.0
    a0, b0 = GL[woman]
    face = (A["head"] > .5) & (A["eye"] < .5) & (A["ears"] < .5)
    seg = (20, 12, 4)[ni]
    fwd = Vector((0, 1, 0))
    for ec in m["eyes"]:
        sx = 1 if ec[0] > 0 else -1
        cx, cz = ec[0] + sx * .002, ec[2] + .002

        def outline(sc, j):   # суперэллипс, верх шире низа (вайфарер), внешний угол чуть выше
            t = 2 * math.pi * j / seg + (math.pi / 4 if ni == 2 else 0)
            c, s_ = math.cos(t), math.sin(t)
            n = 2.8
            x = math.copysign(abs(c) ** (2 / n), c); z = math.copysign(abs(s_) ** (2 / n), s_)
            a = a0 * (1 + .10 * z) * sc; b = b0 * sc
            return cx + sx * x * a, cz + z * b + .003 * x * sx * sx * (x * sx > 0)

        # поверхность стекла: перед бровью/скулой на 5 мм, плавный изгиб к вискам
        sel = face & (np.abs(P[:, 0] - cx) < a0 * 1.1) & (np.abs(P[:, 2] - cz) < b0 * 1.2) & (np.abs(P[:, 0]) > .012)
        y0 = np.percentile(P[sel, 1], 97) + .005

        def ys(x, z):
            d = (x - cx) * sx
            return y0 - 1.6 * max(d, 0) ** 2 * 10 - .25 * max(-d, 0) ** 2 * 10 - .08 * (z - cz)

        def V(x, z, dy=0.0):
            return S.bm.verts.new((x, ys(x, z) + dy, z))
        if ni == 2:   # дальний план: один четырёхугольник на стекло
            q = [V(*outline(1.12, j)) for j in range(4)]
            S.face(q, 13, 1, one, fwd)
            continue
        # стекло — веер от центра
        c0 = V(cx, cz, .001)
        L = [V(*outline(1.0, j), .001) for j in range(seg)]
        for j in range(seg):
            S.face([c0, L[j], L[(j + 1) % seg]], 13, 1, one, fwd)
        # оправа: кольцо вокруг стекла (внешний край шире сверху — бровь вайфарера)
        O = []
        for j in range(seg):
            x, z = outline(1.0, j)
            dx, dz = (x - cx) * 1.0, (z - cz)
            tk = .0045 + .0035 * max(dz / b0, 0)
            r = math.hypot(dx, dz) or 1
            O.append(V(x + dx / r * tk, z + dz / r * tk, .0015))
        I = [V(*outline(1.0, j), .0015) for j in range(seg)]
        for j in range(seg):
            j1 = (j + 1) % seg
            S.face([I[j], O[j], O[j1], I[j1]], 14, 1, one, fwd)
        if ni == 0:   # торец оправы назад на 5 мм
            B = [S.bm.verts.new(v.co + Vector((0, -.005, 0))) for v in O]
            for j in range(seg):
                j1 = (j + 1) % seg
                c = (O[j].co + O[j1].co) / 2
                S.face([O[j], B[j], B[j1], O[j1]], 14, 1, one, Vector((c.x - cx, 0, c.z - cz)))
        # дужка: от внешнего верхнего угла оправы к уху
        ear = (A["ears"] > .3) & (P[:, 0] * sx > 0)
        ex = P[ear].mean(0) if ear.any() else np.array([sx * .075, m["hcy"] - .01, cz])
        hw = np.abs(P[face & (np.abs(P[:, 2] - cz) < .01), 0]).max()
        x0, z0 = cx + sx * a0 * 1.12, cz + b0 * .45
        y1 = ys(x0, z0) - .004
        tw, th_ = (.0025, .006) if ni == 0 else (.002, .005)
        pts = [(x0, y1, z0), (sx * (hw + .004), ex[1] + .01, ex[2] + .012)]
        for (xa, ya, za), (xb, yb, zb) in zip(pts[:-1], pts[1:]):
            q = [S.bm.verts.new(c) for c in ((xa, ya, za + th_ / 2), (xb, yb, zb + th_ / 2), (xb, yb, zb - th_ / 2), (xa, ya, za - th_ / 2))]
            S.face(q, 14, 1, one, Vector((sx, 0, 0)))
            q2 = [S.bm.verts.new(v.co - Vector((sx * tw, 0, 0))) for v in q]
            S.face(q2, 14, 1, one, Vector((-sx, 0, 0)))
            S.face([q[0], q[1], q2[1], q2[0]], 14, 1, one, Vector((0, 0, 1)))
    if ni < 2:   # перемычка над носом
        (xl, zl), (xr, zr) = [(e[0] - (1 if e[0] > 0 else -1) * (a0 - .001), e[2] + .002 + b0 * .35) for e in m["eyes"]]
        yb = max(np.percentile(P[face & (np.abs(P[:, 0]) < .006) & (np.abs(P[:, 2] - zl) < .006), 1], 99) + .003, 0)
        q = [S.bm.verts.new(c) for c in ((xl, yb, zl + .003), (xr, yb, zr + .003), (xr, yb, zr - .003), (xl, yb, zl - .003))]
        S.face(q, 14, 1, one, fwd)


# ---------------------------------------------------------------- уровень детализации
def tier_obj(h, m, woman, tier, target, kf, seg, mats, police, coll):
    ob = h.copy(); ob.data = h.data.copy(); coll.objects.link(ob)
    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    d = ob.modifiers.new("dec", "DECIMATE")
    d.decimate_type = "COLLAPSE"; d.ratio = min(1.0, target / tris)
    d.vertex_group = "keep"; d.vertex_group_factor = kf
    d.use_symmetry = True; d.symmetry_axis = "X"; d.use_collapse_triangulate = True
    with ctx(ob):
        bpy.ops.object.modifier_apply(modifier=d.name)
    ob.vertex_groups.clear()
    me = ob.data
    nb = sum(len(p.vertices) - 2 for p in me.polygons)
    P, A = arrays(me)
    aw = armw(A)
    bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
    uvl = bm.loops.layers.uv.verify()
    HIPZ, TY = m["HIPZ"], m["TY"]
    bone = np.ones(len(P), int); u = np.zeros(len(P))
    fh = A["fore"] + A["hand"]
    for i, p in enumerate(P):
        R = p[0] > 0
        if fh[i] > .02:
            bone[i], u[i] = (3 if R else 5), min(fh[i], 1)
        elif A["up"][i] > .02:
            bone[i], u[i] = (2 if R else 4), min(A["up"][i], 1)
        elif A["leg"][i] > .5 and p[2] < HIPZ:
            bone[i], u[i] = (6 if R else 7), min(max((HIPZ - p[2]) / (HIPZ - .05), 0), 1)
        else:
            bone[i], u[i] = 1, float(sstep(TY - .07, TY + .12, p[2]))
    fd = fdd(P, m)
    skl = bm.loops.layers.uv.new("sk")   # TEXCOORD_1 → в three uv1 = (вес w, звено)
    kc, kw = kclass(np.stack([A["k%d" % c] for c in range(NK)]), P[:, 2], m["J"]["neck01"].z)
    for f in bm.faces:
        ix = [v.index for v in f.verts]
        c = P[ix].mean(0)
        a = {k: A[k][ix].mean() for k in A}
        pre = f.material_index
        a["hairm"], a["beardm"] = float(pre == 2), float(pre == 3)
        if pre == 6:
            # глаз — шар (центр m["eyes"]); радужка — передняя шапка шара
            mat = 9 if f.normal.y > .6 and min(math.hypot(c[0] - ec[0], c[2] - ec[2]) for ec in m["eyes"]) < .008 else 8
        elif pre == 5:
            mat = 10
        elif pre == 8:
            mat = 1
        elif pre == 7:   # граница локтя — по классу грани, а не по среднему веса: длинный треугольник не даёт «шип» кожи вдоль плеча
            mat = 0 if woman else 5
        elif woman and a["hairm"] > .5 and a["eye"] < .5 and a["lips"] < .4:
            mat = 2
        elif a["up"] > .3:
            mat = 0 if woman or pre == 4 else 6
        elif not woman and a["hairm"] > .5:
            mat = 2
        elif not woman and a["beardm"] > .5:
            mat = 3
        elif a["leg"] > .5 and (c[2] < .10 if woman else tier in ("far", "xfar") and (c[2] < .022 or band_strap(c, m))):
            mat = 11
        elif c[2] > m["WZ"] - .02 and a["head"] < .3 and a["neck"] < .3:
            mat = 0 if woman else 7  # весь торс — m7: шейдер по диагонали решает, ткань или открытое плечо (идтиба)
        else:
            mat = 1
        f.material_index = mat; f.smooth = True
        for l in f.loops:
            l[uvl].uv = (u[l.vert.index], 1.0 - bone[l.vert.index])
            l[skl].uv = (float(kw[l.vert.index]), 1.0 - float(kc[l.vert.index]))
    Pfull, Afull = FULL[woman]
    S = Shells(bm, uvl, skl)
    shells(S, Pfull, Afull, m, woman, tier, seg, police)
    glasses(S, Pfull, Afull, m, woman, tier)
    if not woman:
        sandals(S, Pfull, Afull, m, tier)
    me.materials.clear()  # до to_mesh: очистка слотов сбрасывает material_index
    for mt in mats:
        me.materials.append(mt)
    bm.to_mesh(me); bm.free()
    print("TIER", tier, "body", tris, "->", nb, "+shells", sum(len(p.vertices) - 2 for p in me.polygons) - nb)
    for a in list(me.attributes):
        if a.name.startswith("a_"):
            me.attributes.remove(a)
    ob.name = "fig_%s_%s%s_mesh" % ("w" if woman else "m", tier, "_pol" if police else "")
    return ob


def band_strap(c, m):  # ремешок сандалии поперёк подъёма стопы
    return .035 < c[2] < .055


FULL = {}
FULL_KD = {}
TORSO = {}
CHAIN = {}


def contacts(P, A, m):
    """Точки опоры для шейдера (правая сторона; левая — зеркально по x): кончик пальцев, пятка, подъём,
    перед колена, лоб, кончик носа. Шейдер опускает фигуру так, чтобы нижняя из них стояла на полу."""
    K = np.stack([A["k%d" % c] for c in range(NK)])
    kc, _ = kclass(K, P[:, 2], m["J"]["neck01"].z)
    R = P[:, 0] > 0   # правая сторона фигуры (лицом к +y) — x > 0
    J = m["J"]
    toe, ft, shin, hd = (kc == 7) & R, (kc == 6) & R, (kc == 5) & R, kc == 3
    out = {}
    out["TT"] = P[toe][np.argmax(P[toe, 1])]
    hl = ft & (P[:, 2] < .03)
    out["HL"] = P[hl][np.argmin(P[hl, 1])]
    ins = ft & (P[:, 1] > J["foot.R"].y) & (P[:, 1] < J["toe3-1.R"].y)
    out["IN"] = P[ins][np.argmax(P[ins, 2])]
    kn = shin & (np.abs(P[:, 2] - J["lowerleg01.R"].z) < .04)
    out["KF"] = P[kn][np.argmax(P[kn, 1])]
    fh = hd & (np.abs(P[:, 2] - (m["eye_z"] + .045)) < .01) & (np.abs(P[:, 0]) < .02)
    out["FH"] = P[fh][np.argmax(P[fh, 1])]
    nt = hd & (np.abs(P[:, 0]) < .01) & (P[:, 2] < m["eye_z"]) & (P[:, 2] > m["mouth_z"])
    out["NT"] = P[nt][np.argmax(P[nt, 1])]
    return out


def build(coll, mk_mat):
    """Строит корни fig_{m|w}_{near|mid|far} (у мужчин брюки полиции — отдельные материалы m12, скрываются шейдером)."""
    mats = [mk_mat(i) for i in range(NMAT)]
    roots = []
    for woman in (False, True):
        h, J = base(woman)
        coll.objects.link(h) if h.name not in coll.objects else None
        P, A = arrays(h.data)
        m = metrics(P, A, J, woman)
        FULL[woman] = (P, A)
        from mathutils.kdtree import KDTree
        kd = KDTree(len(P))
        for i, p in enumerate(P):
            kd.insert(p, i)
        kd.balance()
        kc, kw = kclass(np.stack([A["k%d" % c] for c in range(NK)]), P[:, 2], m["J"]["neck01"].z)
        FULL_KD[woman] = lambda co, kd=kd, kc=kc, kw=kw: (int(kc[kd.find(co)[1]]), float(kw[kd.find(co)[1]]))
        # положение вдоль позвоночника (0 таз → 1 живот → 2 грудь) в точке торса — среднее по 8 соседним вершинам тела
        tm = np.nonzero((kc <= 2) & (armw(A) < .2) & (P[:, 2] > m["HIPZ"] - .05) & (A["head"] < .3) & (A["neck"] < .3))[0]
        kt = KDTree(len(tm))
        for i, j in enumerate(tm):
            kt.insert(P[j], i)
        kt.balance()
        st = np.where(kc[tm] == 0, 0.0, np.where(kc[tm] == 1, kw[tm], 1 + kw[tm]))
        TORSO[woman] = lambda co, kt=kt, st=st: float(np.mean([st[i] for _, i, _ in kt.find_n(co, 8)]))
        # ткань юбки — по телу под ней: место на цепочке «грудь (−2) … таз (0) … бедро (1) … голень (2)»;
        # гауссово среднее в радиусе 9 см — переход таз → бедро растянут на всю ягодицу, в поклоне ткань огибает её дугой, без угла
        bm_ = np.nonzero((armw(A) < .2) & (A["head"] < .3))[0]
        kb = KDTree(len(bm_))
        for i, j in enumerate(bm_):
            kb.insert(P[j], i)
        kb.balance()
        c_, w_ = kc[bm_], kw[bm_]
        ch = np.select([c_ == 0, c_ == 1, c_ == 2, c_ == 3, (c_ == 4) | (c_ == 8), (c_ == 5) | (c_ == 9)],
                       [0.0 * w_, -w_, -1 - w_, -2 + 0 * w_, w_, 1 + w_], 2.0)
        def chain_at(co, kb=kb, ch=ch):
            nb = kb.find_range(co, .09) or kb.find_n(co, 10)
            return float(np.average([ch[i] for _, i, _ in nb], weights=[math.exp(-(d / .045) ** 2) + 1e-6 for _, _, d in nb]))
        CHAIN[woman] = chain_at
        CT = contacts(P, A, m)
        prep(h, m, woman)
        for tier, target, kf, seg in TIERS:
            ob = tier_obj(h, m, woman, tier, target, kf, seg, mats, not woman, coll)
            r = bpy.data.objects.new("fig_%s_%s" % ("w" if woman else "m", tier), None)
            coll.objects.link(r)
            ob.parent = r
            E, Wr = m["E"], m["Wr"]
            for k, v in (("JX", m["JX"]), ("JY", m["JZ"]), ("EX", E.x), ("EY", E.z), ("EZ", -E.y), ("WX", Wr.x), ("WY", Wr.z),
                         ("TY", m["TY"]), ("HY", m["HIPZ"]), ("WZ", m["WZ"]), ("H", HGT[woman]), ("EYE", m["eye_z"])):
                r[k] = round(float(v), 4)
            # суставы скелета и точки опоры в координатах three (Y = z Blender, Z = −y Blender)
            for k, jn in (("HP", "upperleg01.R"), ("K", "lowerleg01.R"), ("A", "foot.R"), ("B", "toe3-1.R"),
                          ("S4", "spine04"), ("S2", "spine02"), ("N", "neck01")):
                r[k + "Y"], r[k + "Z"] = round(m["J"][jn].z, 4), round(-m["J"][jn].y, 4)
            for k, v in CT.items():
                r[k + "Y"], r[k + "Z"] = round(float(v[2]), 4), round(float(-v[1]), 4)
            print("FIG", r.name, "tris", sum(len(p.vertices) - 2 for p in ob.data.polygons),
                  {k: r[k] for k in r.keys()})
            roots.append(r)
        for c in list(h.users_collection):
            c.objects.unlink(h)
    return roots


# ---------------------------------------------------------------- проверка отдельно
PREV = [(.85, .82, .74), (.78, .58, .45), (.12, .1, .09), (.2, .15, .12), (0, 0, 0), (.6, .4, .3), (.7, .5, .4),
        (.9, .88, .82), (.95, .95, .92), (.05, .04, .03), (.6, .3, .3), (.25, .17, .1), (.15, .2, .3), (.03, .035, .04), (.08, .06, .05)]


def prev_mat(i):
    mt = bpy.data.materials.new("fig_m%d" % i)
    mt.diffuse_color = PREV[i] + (1,)
    mt.use_backface_culling = True
    return mt


if __name__ == "__main__" and "--" in sys.argv:
    OUT = sys.argv[sys.argv.index("--") + 1]
    os.makedirs(OUT, exist_ok=True)
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    C = bpy.data.collections.new("Люди"); bpy.context.scene.collection.children.link(C)
    roots = build(C, prev_mat)
    for i, r in enumerate(roots):
        r.location = (i * .75 - 1.9, 0, 0)
    sc = bpy.context.scene
    try:
        sc.render.engine = "BLENDER_WORKBENCH"
    except TypeError as e:
        print(e)
    sc.display.shading.light = "STUDIO"; sc.display.shading.color_type = "MATERIAL"
    sc.display.shading.show_backface_culling = True
    sc.render.resolution_x, sc.render.resolution_y = 1400, 1000
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.type = "ORTHO"
    PI = math.pi
    for nm, loc, rot, s_ in (("front", (0, 8, .9), (PI / 2, 0, PI), 4.8), ("back", (0, -10, .9), (PI / 2, 0, 0), 4.8),
                             ("side", (8, 0, .9), (PI / 2, 0, PI / 2), 4.0),
                             ("q34", (6, 6, 1.6), (math.radians(80), 0, math.radians(135)), 3.2),
                             ("face_m", (-1.9, 3, 1.55), (PI / 2, 0, PI), .5), ("face_w", (1.1, 3, 1.42), (PI / 2, 0, PI), .5),
                             ("face_m3", (-1.9 + .6, 1.6, 1.6), (math.radians(88), 0, math.radians(160)), .5),
                             ("face_w3", (1.7, 1.6, 1.45), (math.radians(88), 0, math.radians(160)), .5)):
        cam.location = loc; cam.rotation_euler = rot; cam.data.ortho_scale = s_
        sc.render.filepath = os.path.join(OUT, nm + ".png"); bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "figs.blend"))
