#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Write the GT2N DRC rule fixtures (known-bad and known-good patterns).

Run by KLayout:

    klayout -b -r make_drc_fixtures.py -rd out_gds=<fixtures.gds> -rd out_json=<expected.json>

Every pattern is its own cell, placed once in TOP and far enough from the
others that no check sees two patterns. The JSON file holds, for each cell
and each deck mode (route, full), the exact number of markers per rule that
libs.tech/klayout/tech/drc/gt2n.lydrc must report; every rule not listed
must report nothing. A bad pattern may trip more than its target rule when
the geometry cannot avoid it (for example two vias closer than the via
corner spacing also bring their metals too close); those rules are listed
as well. run_drc_rules.py runs the deck and compares.

Coordinates are in nm, on the 0.5 nm manufacturing grid unless a pattern
is meant to be off grid. Rule values follow icv_runset/ and gt2_tech.lef.
"""

import json
import math

import pya

out_gds = globals().get("out_gds")
out_json = globals().get("out_json")
if not out_gds or not out_json:
    raise SystemExit("usage: klayout -b -r make_drc_fixtures.py -rd out_gds=... -rd out_json=...")

# GDS layer numbers (libs.tech/klayout/tech/drc/gt2n.lydrc)
NWELL, ACT, GATE, DUMMY, GCUT, NSEL, PSEL, BPR, VBPR, SDCON, VSD, VG = 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12
M0, V0, SVT, HVT = 20, 22, 96, 97
LAYER = {"M1": 25, "V1": 27, "M2": 30, "V2": 32, "M3": 35, "V3": 37, "M4": 40, "V4": 42,
         "M5": 45, "V5": 47, "M6": 50, "V6": 52, "M7": 55, "V7": 57, "M8": 60, "V8": 62,
         "M9": 65, "V9": 67, "M10": 70, "V10": 72, "M11": 75, "V11": 77, "M12": 80,
         "V12": 82, "M13": 85, "V13": 87, "RDL": 90, "BPR": BPR, "BV0": 910, "BM1": 920,
         "BV1": 930, "BM2": 940, "BV2": 950, "BM3": 960, "BV3": 970, "BM4": 980,
         "BV4": 990, "BRDL": 1000}

FIXTURES = []  # (name, shapes, expected route, expected full)


def fixture(name, shapes, expect=None, route=None, full_only=False):
    """Add one pattern. `expect` is the full-mode result; the route-mode
    result is `route` when given, {} for device-layer patterns (full_only)
    and `expect` otherwise."""
    expect = dict(expect or {})
    if route is None:
        route = {} if full_only else expect
    FIXTURES.append((name, shapes, dict(route), expect))


def transpose(shapes):
    return [(l, y0, x0, y1, x1) for (l, x0, y0, x1, y1) in shapes]


def orient(shapes, vertical):
    """Patterns are drawn for a vertical line; transpose them for horizontal ones."""
    return shapes if vertical else transpose(shapes)


def diag_bad(c):
    """Corner offset with a corner-to-corner distance below c."""
    return math.floor(c / 2)


def diag_good(c):
    """Smallest integer corner offset with a corner-to-corner distance >= c."""
    return math.ceil(c / math.sqrt(2))


# --- M1..M6 (ICV): width, length, spacing, tip-to-tip, corner, bend --------
# name: (width, min length, spacing, tip-to-tip, corner, vertical lines)
ROUTE_METALS = {
    "M1": (14, 28, 14, 20, 16, True),
    "M2": (12, 24, 12, 17, 15, False),
    "M3": (14, 28, 14, 20, 16, True),
    "M4": (21, 42, 21, 30, 24, False),
    "M5": (21, 42, 21, 30, 24, True),
    "M6": (38, 55, 38, 55, 45, False),
}
for m, (w, lmin, s, t, c, vert) in ROUTE_METALS.items():
    ly = LAYER[m]
    n = max(4 * lmin, 100)
    db, dg = diag_bad(c), diag_good(c)
    pat = {
        "1": ([(ly, 0, 0, w - 1, n)], [(ly, 0, 0, w, n)], 1),
        "2": ([(ly, 0, 0, w, lmin - 1)], [(ly, 0, 0, w, lmin)], 1),
        "3": ([(ly, 0, 0, w, n), (ly, w + s - 1, 0, 2 * w + s - 1, n)],
              [(ly, 0, 0, w, n), (ly, w + s, 0, 2 * w + s, n)], 1),
        "4": ([(ly, 0, 0, w, n), (ly, 0, n + t - 1, w, 2 * n + t - 1)],
              [(ly, 0, 0, w, n), (ly, 0, n + t, w, 2 * n + t)], 1),
        "5": ([(ly, 0, 0, w, n), (ly, w + db, n + db, 2 * w + db, 2 * n + db)],
              [(ly, 0, 0, w, n), (ly, w + dg, n + dg, 2 * w + dg, 2 * n + dg)], 2),
        # L-bend drawn as two rectangles (as P&R writes wires) / two
        # overlapping collinear rectangles that merge into one line
        "6": ([(ly, 0, 0, w, n), (ly, 0, n - lmin, 4 * w, n)],
              [(ly, 0, 0, w, n), (ly, 0, n // 2, w, n + n // 2)], 1),
    }
    for k, (bad, good, count) in pat.items():
        fixture(f"{m}.{k}_bad", orient(bad, vert), {f"{m}.{k}": count})
        fixture(f"{m}.{k}_good", orient(good, vert))
# single-polygon bend (not only the two-rectangle form)
fixture("M3.6_bad_polygon", [("poly", LAYER["M3"], [(0, 0), (0, 100), (56, 100), (56, 72), (14, 72), (14, 0)])],
        {"M3.6": 1})

# --- V1..V5 (ICV): landing, enclosure, corner, presence ---------------------
# name: (via w, via h, vertical metal, horizontal metal, corner, vertical
#        metal enclosure (vertical), horizontal metal enclosure (horizontal))
ROUTE_VIAS = {
    "V1": (14, 12, "M1", "M2", 18, 4, 4),
    "V2": (14, 12, "M3", "M2", 18, 4, 4),
    "V3": (14, 21, "M3", "M4", 18, 4, 4),
    "V4": (21, 21, "M5", "M4", 27, 5, 5),
    "V5": (21, 38, "M5", "M6", 27, 6, 6),
}


def no_vm(v, vm, hm):
    """Rule for a via missing metal vm: Vx.7 needs the lower metal, Vx.8 the upper one."""
    return f"{v}.7" if int(vm[1:]) < int(hm[1:]) else f"{v}.8"


def landed(v, vm, hm, w, h, x=0, y=0, ext=20):
    """Via at (x, y) on its vertical and horizontal metal, both ext past it."""
    return [(LAYER[v], x, y, x + w, y + h),
            (LAYER[vm], x, y - ext, x + w, y + h + ext),
            (LAYER[hm], x - ext, y, x + w + ext, y + h)]


for v, (w, h, vm, hm, c, ev, eh) in ROUTE_VIAS.items():
    lv, lvm, lhm = LAYER[v], LAYER[vm], LAYER[hm]
    sv, sh = ROUTE_METALS[vm][2], ROUTE_METALS[hm][2]
    fixture(f"{v}_good", landed(v, vm, hm, w, h))
    # vertical metal ends halfway across the via (partial landing)
    fixture(f"{v}.3_bad_line_end", [(lv, 0, 0, w, h), (lvm, 0, -60, w, h / 2), (lhm, -20, 0, w + 20, h)],
            {f"{v}.3": 2})
    # via next to the vertical metal, sharing its edge from outside
    fixture(f"{v}.3_bad_outside", [(lv, w, 0, 2 * w, h), (lvm, 0, -20, w, h + 20), (lhm, w - 20, 0, 2 * w + 20, h)],
            {f"{v}.3": 2, no_vm(v, vm, hm): 1})
    # vertical metal wider than the via: vertical edges not aligned
    fixture(f"{v}.3_bad_inset", [(lv, 0, 0, w, h), (lvm, -3, -20, w + 3, h + 20), (lhm, -20, 0, w + 20, h)],
            {f"{v}.3": 2})
    # horizontal metal ends halfway across the via
    fixture(f"{v}.4_bad_line_end", [(lv, 0, 0, w, h), (lvm, 0, -20, w, h + 20), (lhm, -60, 0, w / 2, h)],
            {f"{v}.4": 2})
    # via overlaps the horizontal metal by 2 nm only
    fixture(f"{v}.4_bad_sliver", [(lv, 0, 0, w, h), (lvm, 0, -20, w, h + 20), (lhm, -60, 0, 2, h)],
            {f"{v}.4": 2})
    en_v = f"{v}.{vm}.EN"
    en_h = f"{v}.{hm}.EN"
    fixture(f"{en_v}_bad", [(lv, 0, 0, w, h), (lvm, 0, -40, w, h + ev - 1), (lhm, -20, 0, w + 20, h)],
            {en_v: 1})
    fixture(f"{en_v}_good", [(lv, 0, 0, w, h), (lvm, 0, -40, w, h + ev), (lhm, -20, 0, w + 20, h)])
    fixture(f"{en_h}_bad", [(lv, 0, 0, w, h), (lvm, 0, -20, w, h + 20), (lhm, -40, 0, w + eh - 1, h)],
            {en_h: 1})
    fixture(f"{en_h}_good", [(lv, 0, 0, w, h), (lvm, 0, -20, w, h + 20), (lhm, -40, 0, w + eh, h)])
    fixture(f"{no_vm(v, vm, hm)}_bad", [(lv, 0, 0, w, h), (lhm, -20, 0, w + 20, h)],
            {f"{v}.3": 2, no_vm(v, vm, hm): 1})
    fixture(f"{no_vm(v, hm, vm)}_bad", [(lv, 0, 0, w, h), (lvm, 0, -20, w, h + 20)],
            {f"{v}.4": 2, no_vm(v, hm, vm): 1})
    fixture(f"{v}.1_bad", [(lv, 0, 0, w - 1, h)] + landed(v, vm, hm, w, h)[1:], {f"{v}.1": 1, f"{v}.3": 1})
    fixture(f"{v}.2_bad", [(lv, 0, 0, w, h - 1)] + landed(v, vm, hm, w, h)[1:], {f"{v}.2": 1, f"{v}.4": 1})
    # diagonal neighbours on adjacent tracks at minimum metal spacing: legal
    fixture(f"{v}.6_good", landed(v, vm, hm, w, h) + landed(v, vm, hm, w, h, w + sv, h + sh))
    # closer diagonal neighbours: their metals are then too close as well
    d = diag_bad(c)
    fixture(f"{v}.6_bad", landed(v, vm, hm, w, h) + landed(v, vm, hm, w, h, w + d, h + d),
            {f"{v}.6": 2, f"{vm}.3": 1, f"{hm}.3": 1})

# --- upper and backside stacks (tech LEF) -----------------------------------
UPPER_METALS = {"M7": 38, "M8": 38, "M9": 38, "M10": 56, "M11": 56, "M12": 360, "M13": 360,
                "RDL": 1600, "BM1": 56, "BM2": 56, "BM3": 360, "BM4": 360, "BRDL": 1600}
for m, w in UPPER_METALS.items():
    ly = LAYER[m]
    # minimum width in every direction: a stub shorter than the width
    fixture(f"{m}.W_bad", [(ly, 0, 0, w, w / 2)], {f"{m}.W": 1})
    fixture(f"{m}.W_good", [(ly, 0, 0, w, 3 * w)])
    # euclidian spacing: corner-to-corner
    db, dg = diag_bad(w), diag_good(w)
    fixture(f"{m}.S_bad", [(ly, 0, 0, w, 3 * w), (ly, w + db, 3 * w + db, 2 * w + db, 6 * w + db)], {f"{m}.S": 2})
    fixture(f"{m}.S_good", [(ly, 0, 0, w, 3 * w), (ly, w + dg, 3 * w + dg, 2 * w + dg, 6 * w + dg)])
fixture("M7.S_bad_parallel", [(LAYER["M7"], 0, 0, 38, 200), (LAYER["M7"], 75, 0, 113, 200)], {"M7.S": 1})

# name: (width = spacing, metal below, metal above, LEF enclosure)
UPPER_VIAS = {"V6": (38, "M6", "M7", 8), "V7": (38, "M7", "M8", 8), "V8": (38, "M8", "M9", 8),
              "V9": (38, "M9", "M10", 0), "V10": (56, "M10", "M11", 0), "V11": (56, "M11", "M12", 0),
              "V12": (56, "M12", "M13", 0), "V13": (56, "M13", "RDL", 0), "BV1": (56, "BM1", "BM2", 0),
              "BV2": (56, "BM2", "BM3", 0), "BV3": (56, "BM3", "BM4", 0), "BV4": (56, "BM4", "BRDL", 0)}


def plates(below, above, x0, y0, x1, y1):
    """Metal below and above, wide enough for their own width rules."""
    pad = max(UPPER_METALS.get(below, 38), UPPER_METALS.get(above, 38))
    return [(LAYER[below], x0 - pad, y0 - pad, x1 + pad, y1 + pad),
            (LAYER[above], x0 - pad, y0 - pad, x1 + pad, y1 + pad)]


for v, (w, below, above, enc) in UPPER_VIAS.items():
    lv = LAYER[v]
    fixture(f"{v}.W_bad", [(lv, 0, 0, w, w - 1)] + plates(below, above, 0, 0, w, w), {f"{v}.W": 1})
    fixture(f"{v}.W_good", [(lv, 0, 0, w, w)] + plates(below, above, 0, 0, w, w))
    db, dg = diag_bad(w), diag_good(w)
    fixture(f"{v}.S_bad", [(lv, 0, 0, w, w), (lv, w + db, w + db, 2 * w + db, 2 * w + db)]
            + plates(below, above, 0, 0, 2 * w + db, 2 * w + db), {f"{v}.S": 2})
    fixture(f"{v}.S_good", [(lv, 0, 0, w, w), (lv, w + dg, w + dg, 2 * w + dg, 2 * w + dg)]
            + plates(below, above, 0, 0, 2 * w + dg, 2 * w + dg))
    fixture(f"{v}.EN1_bad", [(lv, 0, 0, w, w)] + plates(below, above, 0, 0, w, w)[1:], {f"{v}.EN1": 1})
    fixture(f"{v}.EN2_bad", [(lv, 0, 0, w, w)] + plates(below, above, 0, 0, w, w)[:1], {f"{v}.EN2": 1})
    if enc:
        lb, la = LAYER[below], LAYER[above]
        # LEF "ENCLOSURE e 0": e on both sides of one axis, 0 on the other
        fixture(f"{v}.EN_good", [(lv, 0, 0, w, w), (lb, -20, 0, w + 20, w), (la, 0, -20, w, w + 20)])
        # below: short of e on the left, e on both sides vertically; above:
        # short of e at the bottom, e on both sides horizontally
        fixture(f"{v}.EN_good_other_axis",
                [(lv, 0, 0, w, w), (lb, -enc / 2, -20, w + 20, w + 20), (la, -20, -enc / 2, w + 20, w + 20)])
        fixture(f"{v}.EN3_bad", [(lv, 0, 0, w, w), (lb, -20, 0, w + enc / 2, w), (la, 0, -20, w, w + 20)],
                {f"{v}.EN3": 1})
        fixture(f"{v}.EN4_bad", [(lv, 0, 0, w, w), (lb, -20, 0, w + 20, w), (la, 0, -20, w, w + enc / 2)],
                {f"{v}.EN4": 1})
# BV0 lands on a 32 nm BPR rail (a device layer, checked in full mode only)
fixture("BV0.W_bad", [(LAYER["BV0"], 0, 0, 32, 31), (BPR, -100, 0, 132, 32), (LAYER["BM1"], -56, -56, 88, 88)],
        {"BV0.W": 1})
fixture("BV0.W_good", [(LAYER["BV0"], 0, 0, 32, 32), (BPR, -100, 0, 132, 32), (LAYER["BM1"], -56, -56, 88, 88)])
fixture("BV0.S_bad", [(LAYER["BV0"], 0, 0, 32, 32), (BPR, -100, 0, 132, 32), (LAYER["BV0"], 48, 48, 80, 80),
                      (BPR, -52, 48, 180, 80), (LAYER["BM1"], -56, -56, 136, 136)],
        {"BV0.S": 2, "BPR.2": 1}, route={"BV0.S": 2})
fixture("BV0.EN1_bad", [(LAYER["BV0"], 0, 0, 32, 32), (LAYER["BM1"], -56, -56, 88, 88)], {"BV0.EN1": 1})
fixture("BV0.EN2_bad", [(LAYER["BV0"], 0, 0, 32, 32), (BPR, -100, 0, 132, 32)], {"BV0.EN2": 1})

# --- manufacturing grid ------------------------------------------------------
fixture("GRID.1_bad", [(LAYER["M1"], 0.1, 0, 14.1, 100)], {"GRID.1": 4})
fixture("GRID.1_good", [(LAYER["M1"], 0.5, 0, 14.5, 100)])
fixture("GRID.1_bad_device", [(NWELL, 0.1, 0, 100.1, 100)], {"GRID.1": 4}, full_only=True)

# --- device and local-interconnect layers (full mode) ------------------------
# BPR: 32 nm rails, 112 nm apart, continuous, straight
fixture("BPR_good", [(BPR, 0, 0, 2000, 32), (BPR, 0, 144, 2000, 176), (BPR, 1000, 0, 3000, 32)], full_only=True)
fixture("BPR.1_bad", [(BPR, 0, 0, 2000, 31)], {"BPR.1": 1}, full_only=True)
fixture("BPR.2_bad", [(BPR, 0, 0, 2000, 32), (BPR, 0, 143, 2000, 175)], {"BPR.2": 1}, full_only=True)
fixture("BPR.3_bad", [(BPR, 0, 0, 2000, 32), (BPR, 4000, 0, 6000, 32)], {"BPR.3": 1}, full_only=True)
fixture("BPR.3_good", [(BPR, 0, 0, 2000, 32), (BPR, 12000, 0, 14000, 32)], full_only=True)
fixture("BPR.4_bad", [(BPR, 0, 0, 2000, 32), (BPR, 1000, 16, 3000, 48)], {"BPR.1": 1, "BPR.4": 1}, full_only=True)

# VBPR: exactly 16 x 11 nm inside SDCON
SD = (SDCON, 0, 0, 16, 60)
fixture("VBPR_good", [SD, (VBPR, 0, 20, 16, 31)], full_only=True)
fixture("VBPR.1_bad", [SD, (VBPR, 0, 20, 16, 40)], {"VBPR.1": 1}, full_only=True)
fixture("VBPR.2_bad", [SD, (VBPR, 1, 20, 15, 31)], {"VBPR.2": 1}, full_only=True)
fixture("VBPR.2_bad_wide", [SD, (VBPR, -7, 20, 23, 31)], {"VBPR.2": 1, "VBPR.4": 1}, full_only=True)
fixture("VBPR.3_bad", [SD, (VBPR, 0, 20, 16, 31), (GCUT, -20, 20, 30, 31)], {"VBPR.3": 1, "GCUT.6": 1},
        full_only=True)

# GATE: 14 nm lines on a 42 nm pitch
GATES = [(GATE, x, 0, x + 14, 300) for x in (0, 42, 84, 126)]
fixture("GATE_good", GATES, full_only=True)
fixture("GATE.1_bad", [(GATE, 0, 0, 13, 300)], {"GATE.1": 1}, full_only=True)
# 35 nm and 27 nm gaps; the "> 28 nm" form marks both edges of a gap
fixture("GATE.2_bad", [(GATE, 0, 0, 14, 300), (GATE, 49, 0, 63, 300), (GATE, 90, 0, 104, 300)],
        {"GATE.2": 3}, full_only=True)
fixture("GATE.4_bad", [(GATE, 0, 0, 14, 300), (GATE, 0, 0, 60, 14)], {"GATE.1": 1, "GATE.4": 1}, full_only=True)

# DUMMY: exactly on a GATE
fixture("DUMMY_good", [(GATE, 0, 0, 14, 300), (DUMMY, 0, 0, 14, 300)], full_only=True)
fixture("DUMMY.1_bad", [(GATE, 0, 0, 14, 300), (DUMMY, 0, 0, 13, 300)], {"DUMMY.1": 1}, full_only=True)
fixture("DUMMY.2_bad", [(DUMMY, 0, 0, 14, 300)], {"DUMMY.2": 1, "DUMMY.4": 1}, full_only=True)
fixture("DUMMY.4_bad", [(GATE, 0, 0, 14, 300), (DUMMY, 2, 0, 16, 300)], {"DUMMY.4": 1}, full_only=True)
fixture("DUMMY.3_bad", [(GATE, 0, 0, 14, 300), (GATE, 0, 0, 40, 14), (DUMMY, 0, 0, 14, 300), (DUMMY, 0, 0, 40, 14)],
        {"GATE.1": 1, "GATE.4": 1, "DUMMY.1": 1, "DUMMY.3": 1}, full_only=True)

# GCUT: vertical edges in the gaps between (non-dummy) gates
G3 = GATES[:3]
fixture("GCUT_good", G3 + [(GCUT, 21, 100, 77, 110)], full_only=True)
fixture("GCUT.1_bad", G3 + [(GCUT, 21, 100, 77, 109)], {"GCUT.1": 1}, full_only=True)
fixture("GCUT.2_bad", G3 + [(GCUT, 21, 100, 62, 110)], {"GCUT.2": 1}, full_only=True)
fixture("GCUT.5_bad", G3 + [(GCUT, 21, 100, 77, 110), (GCUT, 21, 100, 31, 130)], {"GCUT.2": 1, "GCUT.5": 1},
        full_only=True)
fixture("GCUT.6_bad", G3 + [(GCUT, 200, 100, 250, 110)], {"GCUT.6": 1}, full_only=True)
fixture("GCUT.7_bad_inside", G3 + [(GCUT, 5, 100, 51, 110)], {"GCUT.7": 2}, full_only=True)
fixture("GCUT.7_bad_coincident", G3 + [(GCUT, 14, 100, 56, 110)], {"GCUT.7": 2}, full_only=True)
fixture("GCUT.7_good_dummy", G3 + [(DUMMY, 0, 0, 14, 300), (GCUT, 5, 100, 63, 110)], full_only=True)
fixture("GCUT.8_bad", G3 + [(GCUT, 21, 100, 77, 110), (ACT, 7, 105, 133, 125)],
        {"GCUT.8": 1, "ACT.6": 2}, full_only=True)

# ACT: ends inside DUMMY gates
ACT_ROW = GATES + [(DUMMY, 0, 0, 14, 300), (DUMMY, 126, 0, 140, 300)]
fixture("ACT_good", ACT_ROW + [(ACT, 7, 100, 133, 120)], full_only=True)
fixture("ACT.1_bad", ACT_ROW + [(ACT, 7, 100, 133, 107)], {"ACT.1": 1}, full_only=True)
fixture("ACT.3_bad", ACT_ROW + [(ACT, 7, 100, 133, 120), (ACT, 7, 149, 133, 169)], {"ACT.3": 1}, full_only=True)
fixture("ACT.2_bad", GATES[:2] + [(DUMMY, 0, 0, 14, 300), (DUMMY, 42, 0, 56, 300), (ACT, 7, 100, 49, 120)],
        {"ACT.2": 1}, full_only=True)
fixture("ACT.6_bad", ACT_ROW + [(ACT, 7, 100, 112, 120)], {"ACT.6": 1}, full_only=True)
fixture("ACT.BPR.1_bad", ACT_ROW + [(ACT, 7, 101, 133, 121), (BPR, -100, 60, 300, 92)], {"ACT.BPR.1": 1},
        full_only=True)
fixture("GCUT.ACT.1_bad", ACT_ROW + [(ACT, 7, 119, 133, 139), (GCUT, 21, 100, 77, 110)], {"GCUT.ACT.1": 1},
        full_only=True)
fixture("NSEL.3_bad", ACT_ROW + [(ACT, 7, 100, 133, 120), (NSEL, -10, 86, 150, 158)], {"NSEL.3": 1},
        full_only=True)
fixture("VG.ACT.1_bad", ACT_ROW + [(ACT, 7, 100, 133, 120), (M0, 32, 125, 66, 137), (VG, 42, 125, 56, 137)],
        {"VG.ACT.1": 1}, full_only=True)

# SDCON: 16 nm wide, 20 nm tip-to-tip (different nets), 6 nm from GATE
fixture("SDCON_good", [SD, (SDCON, 0, 80, 16, 140)], full_only=True)
fixture("SDCON.1_bad", [(SDCON, 0, 0, 17, 60)], {"SDCON.1": 1}, full_only=True)
fixture("SDCON.ACT.1_good", ACT_ROW + [(ACT, 7, 100, 133, 120), (SDCON, 20, 95, 36, 125)], full_only=True)
fixture("SDCON.ACT.1_bad", ACT_ROW + [(ACT, 7, 100, 133, 120), (SDCON, 20, 95, 36, 124)],
        {"SDCON.ACT.1": 1}, full_only=True)
fixture("SDCON.2_bad", [SD, (SDCON, 0, 79, 16, 139)], {"SDCON.2": 1}, full_only=True)
fixture("SDCON.3_bad", [SD, (SDCON, 0, 44, 40, 60)], {"SDCON.1": 1, "SDCON.3": 1}, full_only=True)
fixture("SDCON.GATE.1_bad", [SD, (GATE, 21, -100, 35, 200)], {"SDCON.GATE.1": 1}, full_only=True)

# VSD: exactly 13 x 12 nm inside SDCON and M0
M0_SD = (M0, -10, 24, 26, 36)
fixture("VSD_good", [SD, M0_SD, (VSD, 1.5, 24, 14.5, 36)], full_only=True)
fixture("VSD.1_bad_wide", [SD, M0_SD, (VSD, -2, 24, 18, 36)], {"VSD.1": 1, "VSD.4": 1}, full_only=True)
fixture("VSD.2_bad", [SD, (M0, -10, 22, 26, 34), (VSD, 1.5, 22, 14.5, 33)], {"VSD.2": 1}, full_only=True)
fixture("VSD.3_bad", [SD, M0_SD, (VSD, 1.5, 24, 14.5, 36), (VSD, 1.5, 24, 8, 40)],
        {"VSD.1": 1, "VSD.2": 1, "VSD.3": 1, "VSD.5": 1}, full_only=True)
fixture("VSD.SDCON.1_bad", [SD, M0_SD, (VSD, 0.5, 24, 13.5, 36)], {"VSD.SDCON.1": 1}, full_only=True)
fixture("VSD.M0.1_bad", [SD, (M0, -10, 24, 17.5, 36), (VSD, 1.5, 24, 14.5, 36)],
        {"VSD.M0.1": 1}, full_only=True)

# VG: exactly 14 x 12 nm inside GATE and M0
fixture("VG_good", [(GATE, 0, 0, 14, 300), (M0, -10, 100, 24, 112), (VG, 0, 100, 14, 112)], full_only=True)
fixture("VG.1_bad_wide", [(GATE, 0, 0, 14, 300), (M0, -17, 100, 31, 112), (VG, -7, 100, 21, 112)],
        {"VG.1": 1, "VG.5": 1}, full_only=True)
fixture("VG.2_bad", [(GATE, 0, 0, 14, 300), (M0, -10, 100, 24, 112), (VG, 0, 101, 14, 112)],
        {"VG.2": 1}, full_only=True)
fixture("VG.3_bad", [(GATE, 0, 0, 14, 300), (DUMMY, 0, 0, 14, 300), (M0, -10, 100, 24, 112),
                     (VG, 0, 100, 14, 112)], {"VG.3": 1}, full_only=True)
fixture("VG.4_bad", [(M0, -10, 100, 24, 112), (VG, 0, 100, 14, 112)], {"VG.4": 1, "VG.5": 1}, full_only=True)
fixture("VG.7_bad", [(GATE, 0, 0, 14, 300), (M0, -10, 100, 24, 112), (VG, 0, 100, 14, 112), (VG, 0, 100, 7, 118)],
        {"VG.1": 1, "VG.2": 1, "VG.7": 1, "VG.M0.1": 1}, full_only=True)
fixture("VG.M0.2_bad", [(GATE, 0, 0, 14, 300), (M0, -10, 100, 17, 112), (VG, 0, 100, 14, 112)],
        {"VG.M0.2": 1}, full_only=True)

# M0: 12 nm tall lines, >= 24 nm long
fixture("M0_good", [(M0, 0, 0, 40, 12), (M0, 0, 24, 40, 36), (M0, 57, 0, 97, 12)], full_only=True)
fixture("M0.1_bad", [(M0, 0, 0, 40, 13)], {"M0.1": 1}, full_only=True)
fixture("M0.1_bad_short", [(M0, 0, 0, 40, 30)], {"M0.1": 1}, full_only=True)
fixture("M0.2_bad", [(M0, 0, 0, 23, 12)], {"M0.2": 1}, full_only=True)
fixture("M0.3_bad", [(M0, 0, 0, 40, 12), (M0, 0, 23, 40, 35)], {"M0.3": 1}, full_only=True)
fixture("M0.4_bad", [(M0, 0, 0, 40, 12), (M0, 56, 0, 96, 12)], {"M0.4": 1}, full_only=True)
fixture("M0.5_bad", [(M0, 0, 0, 40, 12), (M0, 50, 22, 90, 34)], {"M0.5": 2}, full_only=True)
fixture("M0.5_good", [(M0, 0, 0, 40, 12), (M0, 51, 23, 91, 35)], full_only=True)
fixture("M0.6_bad", [(M0, 0, 0, 60, 12), (M0, 0, 0, 24, 36)], {"M0.1": 1, "M0.6": 1}, full_only=True)

# V0: exactly 14 x 12 nm, edges on M1 (vertical) and M0 (horizontal)
V0_M0 = (M0, -10, 0, 24, 12)
V0_M1 = (LAYER["M1"], 0, -20, 14, 32)
fixture("V0_good", [V0_M0, V0_M1, (V0, 0, 0, 14, 12)], full_only=True)
fixture("V0.1_bad_wide", [(M0, -10, 0, 38, 12), (LAYER["M1"], 0, -20, 28, 32), (V0, 0, 0, 28, 12)],
        {"V0.1": 1}, full_only=True)
fixture("V0.2_bad", [V0_M0, V0_M1, (V0, 0, 0, 14, 11)], {"V0.2": 1, "V0.8": 1}, full_only=True)
fixture("V0.3_bad", [V0_M0, (LAYER["M1"], 0, -20, 14, 40), (V0, 0, 0, 14, 12), (V0, 0, 0, 7, 18)],
        {"V0.1": 1, "V0.2": 1, "V0.3": 1, "V0.4": 1, "V0.7": 1, "V0.8": 1}, full_only=True)
fixture("V0.4_bad", [(M0, -20, 0, 7, 12), V0_M1, (V0, 0, 0, 14, 12)], {"V0.4": 1, "V0.8": 2}, full_only=True)
fixture("V0.M0.1_bad", [(M0, -10, 0, 16, 12), V0_M1, (V0, 0, 0, 14, 12)], {"V0.M0.1": 1}, full_only=True)
fixture("V0.M1.1_bad", [V0_M0, (LAYER["M1"], 0, -20, 14, 14), (V0, 0, 0, 14, 12)], {"V0.M1.1": 1}, full_only=True)
fixture("V0.5_bad", [V0_M0, (LAYER["M1"], 0, -40, 14, 6), (V0, 0, 0, 14, 12)],
        {"V0.5": 1, "V0.7": 2}, full_only=True)
fixture("V0.6_bad", [V0_M0, V0_M1, (V0, 0, 0, 14, 12), (M0, 11, 21, 45, 33),
                     (LAYER["M1"], 21, 1, 35, 53), (V0, 21, 21, 35, 33)],
        {"V0.6": 2, "M0.3": 1, "M1.3": 1}, route={"M1.3": 1}, full_only=True)
fixture("V0.7_bad_inset", [V0_M0, (LAYER["M1"], -3, -20, 17, 32), (V0, 0, 0, 14, 12)],
        {"V0.7": 2}, full_only=True)
fixture("V0.8_bad", [(M0, -10, 0, 24, 14), V0_M1, (V0, 0, 0, 14, 12)], {"M0.1": 1, "V0.8": 1}, full_only=True)

# implant and VT layers
fixture("NSEL_good", [(NSEL, 0, 0, 100, 72)], full_only=True)
fixture("NSEL.1_bad", [(NSEL, 0, 0, 100, 71)], {"NSEL.1": 1}, full_only=True)
fixture("NSEL.PSEL.1_bad", [(NSEL, 0, 0, 100, 72), (PSEL, 50, 0, 150, 72)], {"NSEL.PSEL.1": 1}, full_only=True)
fixture("SVT.1_bad", [(SVT, 0, 0, 100, 71)], {"SVT.1": 1}, full_only=True)
fixture("SVT.2_bad", [(SVT, 0, 0, 13, 100)], {"SVT.2": 1}, full_only=True)
fixture("VT_OVERLAP.1_bad", [(SVT, 0, 0, 100, 100), (HVT, 50, 0, 150, 100)], {"VT_OVERLAP.1": 1}, full_only=True)


# --- write -------------------------------------------------------------------
layout = pya.Layout()
layout.dbu = 0.0001
top = layout.create_cell("TOP")
expected = {}
y = 0
for name, shapes, route, full in FIXTURES:
    if name in expected:
        raise SystemExit(f"duplicate fixture {name}")
    cell = layout.create_cell(name)
    for shape in shapes:
        if shape[0] == "poly":
            pts = [pya.Point(round(px * 10), round(py * 10)) for px, py in shape[2]]
            cell.shapes(layout.layer(shape[1], 0)).insert(pya.Polygon(pts))
        else:
            ly, x0, y0, x1, y1 = shape
            cell.shapes(layout.layer(ly, 0)).insert(
                pya.Box(*(round(v * 10) for v in (x0, y0, x1, y1))))
    # one column, 4 um clear above every pattern (> RDL/BRDL 1.6 um spacing;
    # BPR.3 only pairs rails that overlap vertically)
    bbox = cell.bbox()
    top.insert(pya.CellInstArray(cell.cell_index(), pya.Trans(0, y - bbox.bottom)))
    box = bbox.moved(0, y - bbox.bottom).to_dtype(layout.dbu)
    expected[name] = {"route": route, "full": full, "bbox": [box.left, box.bottom, box.right, box.top]}
    y += bbox.height() + 40000
layout.write(out_gds)
with open(out_json, "w") as f:
    json.dump(expected, f, indent=1, sort_keys=True)
print(f"wrote {len(FIXTURES)} fixtures -> {out_gds}")
