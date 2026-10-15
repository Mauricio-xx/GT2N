#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Build a DRC/LVS test layout from a GT2N standard-cell GDS library.

The library GDS has one top cell per standard cell. This script (run by
KLayout) creates a single top cell TOP that places every cell of the library
in its own row, abutted on both sides by the library filler cell so that the
shared boundary geometry (half dummy gates, active, implants) sees the same
context as after placement. Whole-library DRC/LVS then runs in one pass:

    klayout -b -r make_drc_testchip.py -rd in_gds=<lib.gds> -rd out_gds=<out.gds>

Rows are separated by `row_gap` um (default 0.432 = 3 rows) so cells do not
interact with each other.

Above these rows sits a small placed block of `block_pairs` (default 2) pairs
of abutted rows, the upper row of each pair mirrored (MX) as in a placed
design, so that every cell is also checked next to other cells and across the
shared rails above and below it. Single-height cells alternate between the
two rows of a pair (the rows swap from one pair to the next, so that each
cell appears in both orientations); double-height cells span the pair.
Fillers close every row and pad the shorter row of a pair.
"""

import pya

in_gds = globals().get("in_gds")
out_gds = globals().get("out_gds")
row_gap = float(globals().get("row_gap", "0.432"))
block_pairs = int(globals().get("block_pairs", "2"))
if not in_gds or not out_gds:
    raise SystemExit("usage: klayout -b -r make_drc_testchip.py -rd in_gds=... -rd out_gds=...")

layout = pya.Layout()
layout.read(in_gds)
cells = sorted(layout.top_cells(), key=lambda c: c.name)
fillers = [c for c in cells if "_filler_" in c.name]
filler = fillers[0] if fillers else None
# Cell width/height come from the prBoundary (235/250) so that geometry
# overhanging the boundary (half dummy gates) does not shift the abutment.
boundary = layout.find_layer(235, 250)


def outline(cell):
    if boundary is not None:
        box = cell.bbox_per_layer(boundary)
        if not box.empty():
            return box
    return cell.bbox()


def place(cell, x, y, mirrored=False):
    """Place `cell` with its outline at (x, y), mirrored at the x axis (MX)
    if requested, and return the x of its right edge."""
    box = outline(cell)
    if mirrored:
        trans = pya.Trans(0, True, x - box.left, y + box.top)
    else:
        trans = pya.Trans(0, False, x - box.left, y - box.bottom)
    top.insert(pya.CellInstArray(cell.cell_index(), trans))
    return x + box.width()


top = layout.create_cell("TOP")
y = 0
for cell in cells:
    box = outline(cell)
    x = 0
    row = [filler, cell, filler] if filler else [cell]
    for member in row:
        x = place(member, x, y)
    y += box.height() + int(round(row_gap / layout.dbu))

if filler and block_pairs > 0:
    height, fill_w = outline(filler).height(), outline(filler).width()
    singles = [c for c in cells if c is not filler and outline(c).height() == height]
    doubles = [c for c in cells if outline(c).height() == 2 * height]
    for pair in range(block_pairs):
        ends = []
        for r in (0, 1):
            members = singles[(r + pair) % 2::2]
            x = place(filler, 0, y + r * height, r == 1)
            for cell in members:
                x = place(cell, x, y + r * height, r == 1)
            ends.append(x)
        x = max(ends)
        for r, end in enumerate(ends):
            if (x - end) % fill_w:
                raise SystemExit(f"row width {x - end} is not a multiple of the filler width {fill_w}")
            while end < x:
                end = place(filler, end, y + r * height, r == 1)
        for cell in doubles:
            x = place(cell, x, y)
        for r in (0, 1):
            place(filler, x, y + r * height, r == 1)
        y += 2 * height
layout.write(out_gds)
print(f"placed {len(cells)} cells into TOP -> {out_gds}")
