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
TIERS = (("near", int(os.environ.get("FIGS_NEAR", 2300)), 10.0, 24), ("mid", 620, 6.0, 12), ("far", 230, 3.0, 8), ("xfar", 70, 2.0, 5))
NMAT = 13
# m0 одежда/изар/абая · m1 кожа · m2 волосы/хиджаб · m3 борода · m5 предплечье · m6 правое плечо
# m7 торс (рида по диагонали) · m8 белок глаза · m9 зрачок · m10 губы · m11 обувь · m12 брюки
CATS = {"up": ("upperarm",), "fore": ("lowerarm",), "hand": ("wrist", "metacarpal", "finger"),
        "leg": ("upperleg", "lowerleg", "foot", "toe"), "neck": ("neck",),
        "head": ("head", "jaw", "special", "oris", "levator", "orbicularis", "oculi", "temporalis", "risorius", "tongue", "eye."),
        "lips": None, "scalp": None, "ears": None, "body": None, "eye": ("helper-l-eye", "helper-r-eye")}
EXTRA = ("hairm", "beardm", "face")  # маски из prep: волосы, борода, открытое лицо


def sstep(a, b, x):
    t = np.clip((np.asarray(x, float) - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def ctx(ob):
    return bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob], selected_editable_objects=[ob])


# ---------------------------------------------------------------- тело MPFB
def base(woman):
    addon_utils.enable("bl_ext.blender_org.mpfb", default_set=True)
    from bl_ext.blender_org.mpfb.services.humanservice import HumanService
    md = {"gender": 0.0 if woman else 1.0, "age": 0.5, "muscle": 0.5, "weight": 0.55, "proportions": 0.6, "height": 0.5,
          "cupsize": 0.5, "firmness": 0.5, "race": {"asian": 0.45, "caucasian": 0.5, "african": 0.05}}
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
        pb = rig.pose.bones["upperleg01." + s]
        hip, ft = pb.head.copy(), rig.pose.bones["foot." + s].head.copy()
        v = ft - hip
        t = Vector((sx * .095 * H0 / HGT[woman] - hip.x, v.y, v.z))
        q = v.normalized().rotation_difference(t.normalized())
        pb.matrix = Matrix.Translation(hip) @ q.to_matrix().to_4x4() @ Matrix.Translation(-hip) @ pb.matrix
        bpy.context.view_layer.update()
    J = {k: (rig.matrix_world @ rig.pose.bones[k].head).copy()
         for k in ("upperarm01.R", "lowerarm01.R", "wrist.R", "upperleg01.R", "foot.R", "neck01", "head")}
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
    for c in list(CATS) + list(EXTRA):
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
    m["E"] = J["lowerarm01.R"]; m["Wr"] = J["wrist.R"]
    m["z_cb"] = m["JZ"] - .08
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
        hid = (z > .07) & (z < m["WZ"] - .02) & (aw < .2)
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
        cape = np.where((A["fore"] + A["hand"] > .2) | (z < m["WZ"]), 0, cape)
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
                            else 3 if beardm[ix].mean() > .5 else 4 if ridam[ix].mean() > .5 else 0)
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
        cs = {f.material_index for f in v.link_faces}
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
           and not {e.link_faces[0].material_index, e.link_faces[1].material_index} & {5, 6}]
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


def band(P, z, dz):
    return np.abs(P[:, 2] - z) < dz


class Shells:
    def __init__(s, bm):
        s.bm = bm
        s.uv = bm.loops.layers.uv.verify()

    def face(s, vs, mat, bone, ufun, want):
        try:
            f = s.bm.faces.new(vs)
        except ValueError:
            return None
        f.material_index = mat; f.smooth = True
        f.normal_update()
        if f.normal.dot(want) < 0:
            f.normal_flip()
        for l in f.loops:
            l[s.uv].uv = (float(ufun(l.vert.co.z)), 1.0 - bone)
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


def shells(bm, P, A, m, woman, tier, seg, police):
    S = Shells(bm)
    ni = {"near": 0, "mid": 1, "far": 2, "xfar": 2}[tier]   # xfar — как far, но реже сетка и меньше треугольников
    aw = armw(A)
    HIPZ = m["HIPZ"]
    legu = lambda z: min(max((HIPZ - z) / (HIPZ - .05), 0.0), 1.0)
    one = lambda z: 1.0
    th, D = dirs(seg)
    head = (A["head"] > .5) & (A["ears"] < .5)
    hcy = m["hcy"]
    if not woman:
        # изар
        body = aw < .2
        cy = P[body & band(P, HIPZ, .05), 1].mean()
        zs = np.linspace(.38, m["WZ"], (9, 4, 3)[ni])
        rings = []
        for z in zs:
            t = (z - .38) / (m["WZ"] - .38)
            r = sup(P, body & band(P, z, .04), 0, cy, seg, .01 + .03 * (1 - t) ** 1.5)
            if ni == 0:
                r = r + .004 * (1 - t) * np.sin(7 * th + .7)
            rings.append((z, 0, cy, r))
        S.polar(rings, seg, 0, 0, legu)
        r_in = sup(P, body & band(P, m["WZ"], .02), 0, cy, seg, -.005)
        S.annulus(m["WZ"], 0, cy, r_in, rings[-1][3], seg, 0, 0, legu)
        # брюки полиции
        if police and ni < 2:
            sg = (12, 6)[ni]
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
        # абая
        zs = np.linspace(.04, m["WZ"], (9, 4, 3)[ni])
        rings = []
        for z in zs:
            t = (z - .04) / (m["WZ"] - .04)
            r = sup(P, body & band(P, max(z, .1), .04), 0, cy, seg, .006 + .085 * (1 - t) ** 1.4)
            if ni == 0:
                r = r + .006 * (1 - t) * np.sin(9 * th)
            rings.append((z, 0, cy, r))
        S.polar(rings, seg, 0, 0, legu)
        r_in = sup(P, body & band(P, m["WZ"], .02), 0, cy, seg, -.005)
        S.annulus(m["WZ"], 0, cy, r_in, rings[-1][3], seg, 0, 0, legu)


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
        elif a["hand"] > .5:
            mat = 1
        elif woman and a["hairm"] > .5 and a["eye"] < .5 and a["lips"] < .4 and a["fore"] < .3:
            mat = 2
        elif a["fore"] > .3:
            mat = 0 if woman else 5
        elif a["up"] > .3:
            mat = 0 if woman or pre == 4 else 6
        elif not woman and a["hairm"] > .5:
            mat = 2
        elif not woman and a["beardm"] > .5:
            mat = 3
        elif woman and a["hairm"] > .5 and a["eye"] < .5 and a["lips"] < .4:
            mat = 2
        elif a["leg"] > .5 and (c[2] < (.10 if woman else .022) or (not woman and band_strap(c, m))):
            mat = 11
        elif c[2] > m["WZ"] - .02 and a["head"] < .3 and a["neck"] < .3:
            mat = 0 if woman else 7  # весь торс — m7: шейдер по диагонали решает, ткань или открытое плечо (идтиба)
        else:
            mat = 1
        f.material_index = mat; f.smooth = True
        for l in f.loops:
            l[uvl].uv = (u[l.vert.index], 1.0 - bone[l.vert.index])
    Pfull, Afull = FULL[woman]
    shells(bm, Pfull, Afull, m, woman, tier, seg, police)
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
            print("FIG", r.name, "tris", sum(len(p.vertices) - 2 for p in ob.data.polygons),
                  {k: r[k] for k in r.keys()})
            roots.append(r)
        for c in list(h.users_collection):
            c.objects.unlink(h)
    return roots


# ---------------------------------------------------------------- проверка отдельно
PREV = [(.85, .82, .74), (.78, .58, .45), (.12, .1, .09), (.2, .15, .12), (0, 0, 0), (.6, .4, .3), (.7, .5, .4),
        (.9, .88, .82), (.95, .95, .92), (.05, .04, .03), (.6, .3, .3), (.25, .17, .1), (.15, .2, .3)]


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
                             ("face_m", (-1.9, 3, 1.55), (PI / 2, 0, PI), .5), ("face_w", (.35, 3, 1.42), (PI / 2, 0, PI), .5),
                             ("face_m3", (-1.9 + .6, 1.6, 1.6), (math.radians(88), 0, math.radians(160)), .5),
                             ("face_w3", (.35 + .6, 1.6, 1.45), (math.radians(88), 0, math.radians(160)), .5)):
        cam.location = loc; cam.rotation_euler = rot; cam.data.ortho_scale = s_
        sc.render.filepath = os.path.join(OUT, nm + ".png"); bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "figs.blend"))
