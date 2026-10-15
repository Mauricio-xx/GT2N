#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Build the GT2N LVS regression cases from a libs.ref library.

Run by KLayout (run_lvs_tests.py does this):

    klayout -b -r make_lvs_tests.py -rd lib_dir=<libs.ref/lib> -rd out_dir=<dir>

Each case is a small layout made from the library cells, some of them
mutated, plus the reference netlist. Positive cases must match, negative cases
must not. Writes <case>.gds, <case>.cdl (block cases: top subcircuit followed
by the library CDL) and cases.json, which run_lvs_tests.py reads.

Pin and rail positions come from the labels and shapes of the library cells,
so the cases work for every library.
"""

import json
import os

import pya

lib_dir = globals().get("lib_dir")
out_dir = globals().get("out_dir")
if not lib_dir or not out_dir:
    raise SystemExit("usage: klayout -b -r make_lvs_tests.py -rd lib_dir=... -rd out_dir=...")

lib = os.path.basename(os.path.normpath(lib_dir))
lib_gds = os.path.join(lib_dir, "gds", lib + ".gds")
lib_cdl = os.path.join(lib_dir, "cdl", lib + ".cdl")
suffix = lib[len("gt2_6t"):]  # e.g. _w31_svt

src = pya.Layout()
src.read(lib_gds)
dbu = src.dbu
NM = 1e-3  # um

ACT, GATE, DUMMY, NSEL, BPR, VBPR, M1, BOUNDARY = (2, 0), (3, 0), (4, 0), (6, 0), (8, 0), (9, 0), (25, 0), (235, 250)
BPR_LABEL, M1_LABEL = (8, 251), (25, 251)


def cname(base):
    return "gt2_6t_" + base + suffix


def region(layout, cell, ld):
    li = layout.find_layer(*ld)
    return pya.Region() if li is None else pya.Region(cell.begin_shapes_rec(li))


def label(cell_name, ld, text):
    """Position (um) of the text `text` on layer `ld` of a library cell."""
    cell = src.cell(cell_name)
    li = src.find_layer(*ld)
    for shape in cell.shapes(li).each():
        if shape.is_text() and shape.text_string.lower() == text.lower():
            return shape.dtext.position()
    raise SystemExit(f"{cell_name}: no '{text}' label on {ld}")


def width(cell_name):
    cell = src.cell(cell_name)
    return cell.dbbox_per_layer(src.find_layer(*BOUNDARY)).width()


def add_box(layout, cell, ld, box):
    cell.shapes(layout.layer(*ld)).insert(box)


# Mutations of a cell copy ------------------------------------------------------

def no_vbpr(layout, cell):
    """Remove the BPR-to-SDCON vias (the tap loses its BPR-to-M1 path)."""
    cell.shapes(layout.layer(*VBPR)).clear()


def m1_short(layout, cell):
    """M1 bar across all M1 shapes at mid height (tap: vdd pin to vss pin)."""
    box = region(layout, cell, M1).bbox()
    yc, half = box.center().y, int(round(7 * NM / dbu))
    add_box(layout, cell, M1, pya.Box(box.left, yc - half, box.right, yc + half))


def bpr_short(layout, cell):
    """Vertical BPR bar from the bottom rail to the top rail."""
    box = region(layout, cell, BPR).bbox()
    add_box(layout, cell, BPR, pya.Box(box.left, box.bottom, box.left + int(round(14 * NM / dbu)), box.top))


def gate_plus_1nm(layout, cell):
    """Widen the first real gate (not dummy) by 1 nm: L + 1 nm."""
    gates = region(layout, cell, GATE) - region(layout, cell, DUMMY)
    box = min((p.bbox() for p in gates.each()), key=lambda b: b.left)
    add_box(layout, cell, GATE, pya.Box(box.right, box.bottom, box.right + int(round(NM / dbu)), box.top))


def nsheet_plus_1nm(layout, cell):
    """Widen the NMOS sheets (active inside NSEL) by 1 nm at the bottom: W + 1 nm."""
    act = region(layout, cell, ACT) & region(layout, cell, NSEL)
    box = act.bbox()
    add_box(layout, cell, ACT, pya.Box(box.left, box.bottom - int(round(NM / dbu)), box.right, box.bottom))


# Case writers ------------------------------------------------------------------

cases = []


def copy_cells(layout, names, mutate):
    cells = {}
    for name in names:
        cell = layout.create_cell(name)
        cell.copy_tree(src.cell(name))
        if name in mutate:
            mutate[name](layout, cell)
        cells[name] = cell
    return cells


def cell_case(case, cell_base, expect, log, mutate=None, why=""):
    """Library cell (optionally mutated) against its CDL subcircuit."""
    name = cname(cell_base)
    layout = pya.Layout()
    layout.dbu = dbu
    copy_cells(layout, [name], {name: mutate} if mutate else {})
    gds = os.path.join(out_dir, case + ".gds")
    layout.write(gds)
    cases.append(dict(name=case, gds=gds, top=name, cdl=lib_cdl, mode="transistor",
                      expect=expect, log=log, why=why))


# Signal-only abstract LVS (signal_only_lvs, an OpenROAD-flow-scripts option)
# leaves the supplies out. It needs a DEF; one without components or nets is
# enough for these blocks.
SIGNAL_DEF = os.path.join(out_dir, "signal_only.def")
with open(SIGNAL_DEF, "w") as out:
    out.write("VERSION 5.8 ;\nDESIGN signal_only ;\nUNITS DISTANCE MICRONS 2000 ;\n"
              "COMPONENTS 0 ;\nEND COMPONENTS\nNETS 0 ;\nEND NETS\nEND DESIGN\n")


def block_case(case, insts, labels, ports, netlist, expect, log, mutate=None, boxes=(),
               modes=("transistor",), why=""):
    """Top cell LVS_<CASE> built from library cells.

    insts:   (instance, cell base, x, y, mirror_x) in um
    labels:  (text, layer, x, y) texts of the top cell
    netlist: (instance, [nets], cell base) in CDL pin order
    expect:  expected verdict, or {mode: verdict}
    log:     expected log pattern, or {mode: pattern}
    boxes:   (layer, DBox) shapes of the top cell
    modes:   transistor, abstract, signal (abstract with signal_only_lvs)
    """
    top_name = "LVS_" + case.upper()
    names = sorted({cname(base) for _, base, _, _, _ in insts})
    layout = pya.Layout()
    layout.dbu = dbu
    cells = copy_cells(layout, names, {cname(k): v for k, v in (mutate or {}).items()})
    top = layout.create_cell(top_name)
    for _, base, x, y, mirror in insts:
        top.insert(pya.DCellInstArray(cells[cname(base)].cell_index(), pya.DTrans(0, mirror, x, y)))
    for text, ld, x, y in labels:
        top.shapes(layout.layer(*ld)).insert(pya.DText(text, pya.DTrans(x, y)))
    for ld, box in boxes:
        top.shapes(layout.layer(*ld)).insert(box)
    gds = os.path.join(out_dir, case + ".gds")
    layout.write(gds)
    cdl = os.path.join(out_dir, case + ".cdl")
    text = f".SUBCKT {top_name} {' '.join(ports)}\n"
    for inst, nets, base in netlist:
        text += f"X{inst} {' '.join(nets)} {cname(base)}\n"
    text += f".ENDS {top_name}\n\n"
    # Bytes: the library CDL header is not ASCII.
    with open(cdl, "wb") as out, open(lib_cdl, "rb") as lib_text:
        out.write(text.encode() + lib_text.read())
    for mode in modes:
        options = {"signal_only_lvs": "1", "def_file": SIGNAL_DEF} if mode == "signal" else {}
        cases.append(dict(name=case if mode == "transistor" else f"{case}_{mode}", gds=gds, top=top_name,
                          cdl=cdl, mode="abstract" if mode == "signal" else mode, options=options,
                          expect=expect[mode] if isinstance(expect, dict) else expect,
                          log=log[mode] if isinstance(log, dict) else log, why=why))


# Library cells -----------------------------------------------------------------

# Expected verdict and a regular expression the log must contain.
MATCH, MISMATCH = "match", "mismatch"
DEVICES = r"[1-9]\d* device pair\(s\)"
SUBCIRCUITS = r"[1-9]\d* subcircuit pair\(s\)"
SUPPLY_OK = "supply check passed"
DONT = "Netlists don't match"
GUARD = "Supply net mismatch"
SIGNAL_ONLY = r"signal-only LVS removed PG interface pins total=[1-9]"

cell_case("cell_inv", "inv_x1", MATCH, DEVICES)
cell_case("cell_dffasync", "dffasync_x1", MATCH, DEVICES, why="two vss rails, joined by connect_implicit")
cell_case("cell_mux2", "mux2_x1", MATCH, DEVICES, why="two vss rails, joined by connect_implicit")
cell_case("cell_tapfspdn", "tapfspdn", MATCH, SUPPLY_OK)
cell_case("cell_tapbspdn", "tapbspdn", MATCH, SUPPLY_OK)
cell_case("cell_filler", "filler", MATCH, SUPPLY_OK)
cell_case("cell_tap_no_vbpr", "tapfspdn", MISMATCH, "Supply vdd of device-less cell", no_vbpr,
          why="tap without VBPR: M1 pins not connected to the BPR rails")
cell_case("cell_tap_short", "tapfspdn", MISMATCH, "Supply short in device-less cell", m1_short,
          why="tap with its vdd and vss M1 pins shorted")
cell_case("cell_filler_short", "filler", MISMATCH, "Supply short in device-less cell", bpr_short,
          why="filler with its BPR rails shorted")
cell_case("cell_inv_l_plus_1nm", "inv_x1", MISMATCH, DONT, gate_plus_1nm,
          why="gate length 1 nm too long (ICV compares L exactly)")
cell_case("cell_inv_w_plus_1nm", "inv_x1", MISMATCH, DONT, nsheet_plus_1nm,
          why="NMOS sheet width 1 nm too wide (ICV compares W exactly)")

# Blocks ------------------------------------------------------------------------

TAP, INV, DFF = "tapfspdn", "inv_x1", "dffasync_x1"
w_tap, w_inv = width(cname(TAP)), width(cname(INV))
tap_vdd, tap_vss = label(cname(TAP), M1_LABEL, "vdd"), label(cname(TAP), M1_LABEL, "vss")
inv_a, inv_y = label(cname(INV), M1_LABEL, "A"), label(cname(INV), M1_LABEL, "Y")
inv_vdd, inv_vss = label(cname(INV), BPR_LABEL, "vdd"), label(cname(INV), BPR_LABEL, "vss")
bpr_rails = region(src, src.cell(cname(INV)), BPR)
rail_vss = min((p.bbox() for p in bpr_rails.each()), key=lambda b: b.bottom).to_dtype(dbu)
rail_vdd = max((p.bbox() for p in bpr_rails.each()), key=lambda b: b.bottom).to_dtype(dbu)


def inv_pins(i, x):
    return [(f"A{i}", M1_LABEL, x + inv_a.x, inv_a.y), (f"Y{i}", M1_LABEL, x + inv_y.x, inv_y.y)]


# Tap and two abutting inverters, supply labels on the tap M1 pins only.
tap_insts = [("TAP", TAP, 0, 0, False), ("I1", INV, w_tap, 0, False), ("I2", INV, w_tap + w_inv, 0, False)]
tap_labels = ([("VDD", M1_LABEL, tap_vdd.x, tap_vdd.y), ("VSS", M1_LABEL, tap_vss.x, tap_vss.y)]
              + inv_pins(1, w_tap) + inv_pins(2, w_tap + w_inv))
tap_ports = ["A1", "Y1", "A2", "Y2", "VDD", "VSS"]
tap_netlist = [("TAP", ["VDD", "VSS"], TAP), ("I1", ["A1", "Y1", "VDD", "VSS"], INV),
               ("I2", ["A2", "Y2", "VDD", "VSS"], INV)]
block_case("blk_tap_inv2", tap_insts, tap_labels, tap_ports, tap_netlist, MATCH, SUBCIRCUITS,
           modes=("transistor", "abstract"), why="rails reach the labelled M1 pins through the tap")
# Transistor mode: the floating labelled net is purged and the compare alone
# matches, the supply guard fails it. Abstract mode: the tap black box has
# split pins.
block_case("blk_tap_inv2_no_vbpr", tap_insts, tap_labels, tap_ports, tap_netlist, MISMATCH,
           {"transistor": GUARD, "abstract": DONT}, mutate={TAP: no_vbpr}, modes=("transistor", "abstract"),
           why="tap without VBPR: the inverter rails are cut off from VDD/VSS")

# Tap, inverter, filler, inverter: the filler rails connect the second
# inverter. The schematic lists the filler, as OpenROAD write_cdl does.
FILL = "filler"
x_fill, x_inv2 = w_tap + w_inv, w_tap + w_inv + width(cname(FILL))
block_case("blk_tap_inv_fill_inv",
           tap_insts[:2] + [("F1", FILL, x_fill, 0, False), ("I2", INV, x_inv2, 0, False)],
           tap_labels[:2] + inv_pins(1, w_tap) + inv_pins(2, x_inv2), tap_ports,
           tap_netlist[:2] + [("F1", ["VDD", "VSS"], FILL), tap_netlist[2]], MATCH,
           {"transistor": SUBCIRCUITS, "abstract": SUBCIRCUITS, "signal": SIGNAL_ONLY},
           modes=("transistor", "abstract", "signal"), why="the filler rails connect the second inverter")

# Second inverter 1 um away from the tap row: its rails touch nothing.
far = w_tap + w_inv + 1.0
block_case("blk_inv_floating", tap_insts[:2] + [("I2", INV, far, 0, False)],
           tap_labels[:2] + inv_pins(1, w_tap) + inv_pins(2, far), tap_ports, tap_netlist, MISMATCH, DONT,
           modes=("transistor", "abstract"), why="second inverter with floating rails")

# Inverter alone, VDD/VSS labelled BPR stubs 1 um away: the rails touch nothing.
stub_x = w_inv + 1.0
stubs = [(BPR, pya.DBox(stub_x, r.bottom, stub_x + 0.1, r.top)) for r in (rail_vss, rail_vdd)]
block_case("blk_inv_unpowered", [("I1", INV, 0, 0, False)],
           [("VDD", BPR_LABEL, stub_x + 0.05, inv_vdd.y), ("VSS", BPR_LABEL, stub_x + 0.05, inv_vss.y)]
           + inv_pins(1, 0), ["A1", "Y1", "VDD", "VSS"], [("I1", ["A1", "Y1", "VDD", "VSS"], INV)],
           MISMATCH, DONT, boxes=stubs, modes=("transistor", "abstract"),
           why="inverter whose rails do not reach the labelled supply")

# Two inverters 1 um apart, rails bridged with BPR in the top cell, supply
# labels on the rails of the first one.
bridges = [(BPR, pya.DBox(r.left, r.bottom, 1.0 + r.right, r.top)) for r in (rail_vss, rail_vdd)]
block_case("blk_inv2_bridged", [("I1", INV, 0, 0, False), ("I2", INV, 1.0, 0, False)],
           [("VDD", BPR_LABEL, inv_vdd.x, inv_vdd.y), ("VSS", BPR_LABEL, inv_vss.x, inv_vss.y)]
           + inv_pins(1, 0) + inv_pins(2, 1.0), tap_ports,
           [("I1", ["A1", "Y1", "VDD", "VSS"], INV), ("I2", ["A2", "Y2", "VDD", "VSS"], INV)],
           MATCH, SUBCIRCUITS, boxes=bridges, modes=("transistor", "abstract"))

# Flip-flop (vss rails at the bottom and at the top) and an inverter mirrored
# in the row above, sharing the top vss rail. A BPR path left of the cells
# joins the bottom rail (labelled VSS) and the top rail. Without that path
# the top rail is open. Transistor mode flattens the flip-flop into the block
# (lvs_flatten_cells), so the open rail is a mismatch of the compare. Abstract
# mode joins the flip-flop rails (lvs_implicit_cells) and reports the open
# rail as an error.
dff_rails = sorted((p.bbox().to_dtype(dbu) for p in region(src, src.cell(cname(DFF)), BPR).each()),
                   key=lambda b: b.bottom)
d_bot, d_vdd, d_top = dff_rails[0], dff_rails[1], dff_rails[-1]
dff_pins = ["CLK", "D", "Q", "RESETN", "SETN"]
row2 = d_top.center().y
dff_insts = [("D1", DFF, 0, 0, False), ("I1", INV, -w_inv, row2, True)]
dff_labels = ([(pin, M1_LABEL, label(cname(DFF), M1_LABEL, pin).x, label(cname(DFF), M1_LABEL, pin).y)
               for pin in dff_pins]
              + [("A1", M1_LABEL, -w_inv + inv_a.x, row2 - inv_a.y), ("Y1", M1_LABEL, -w_inv + inv_y.x, row2 - inv_y.y),
                 ("VSS", BPR_LABEL, -0.15, d_bot.center().y), ("VDD", BPR_LABEL, 0.1, d_vdd.center().y)])
dff_ports = dff_pins + ["A1", "Y1", "VDD", "VSS"]
dff_netlist = [("D1", dff_pins + ["VDD", "VSS"], DFF), ("I1", ["A1", "Y1", "VDD", "VSS"], INV)]
bottom_ext = (BPR, pya.DBox(-0.3, d_bot.bottom, 0, d_bot.top))
dff_path = [(BPR, pya.DBox(-0.3, d_top.bottom, -w_inv, d_top.top)),
            (BPR, pya.DBox(-0.3, d_bot.bottom, -0.3 + 0.016, d_top.top))]
block_case("blk_dff_rails", dff_insts, dff_labels, dff_ports, dff_netlist, MATCH,
           {"transistor": DEVICES, "abstract": SUBCIRCUITS}, boxes=[bottom_ext] + dff_path,
           modes=("transistor", "abstract"),
           why="both flip-flop vss rails connected in the block")
# Signal-only LVS leaves the supplies out, so the open rail is not reported.
rail_open = "Split supply rails not connected"
block_case("blk_dff_top_rail_open", dff_insts, dff_labels, dff_ports, dff_netlist,
           {"transistor": MISMATCH, "abstract": MISMATCH, "signal": MATCH},
           {"transistor": DONT, "abstract": rail_open, "signal": SIGNAL_ONLY}, boxes=[bottom_ext],
           modes=("transistor", "abstract", "signal"),
           why="top vss rail of the flip-flop (and the inverter on it) not connected to VSS")
# Flip-flop alone, top vss rail touching nothing: in abstract mode KLayout
# stops the extraction.
rail_floating = "Netlist extraction failed"
block_case("blk_dff_top_rail_floating", dff_insts[:1], dff_labels[:len(dff_pins)] + dff_labels[-2:],
           dff_pins + ["VDD", "VSS"], dff_netlist[:1],
           {"transistor": MISMATCH, "abstract": MISMATCH, "signal": MATCH},
           {"transistor": DONT, "abstract": rail_floating, "signal": SIGNAL_ONLY}, boxes=[bottom_ext],
           modes=("transistor", "abstract", "signal"), why="top vss rail of the flip-flop floating")

with open(os.path.join(out_dir, "cases.json"), "w") as out:
    json.dump(dict(lib=lib, cases=cases), out, indent=1)
print(f"{lib}: wrote {len(cases)} LVS cases to {out_dir}")
