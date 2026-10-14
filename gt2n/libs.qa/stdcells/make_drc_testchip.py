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
"""

import pya

in_gds = globals().get("in_gds")
out_gds = globals().get("out_gds")
row_gap = float(globals().get("row_gap", "0.432"))
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


top = layout.create_cell("TOP")
y = 0
for cell in cells:
    box = outline(cell)
    x = 0
    row = [filler, cell, filler] if filler else [cell]
    for member in row:
        mbox = outline(member)
        top.insert(pya.CellInstArray(member.cell_index(),
                                     pya.Trans(x - mbox.left, y - mbox.bottom)))
        x += mbox.width()
    y += box.height() + int(round(row_gap / layout.dbu))
layout.write(out_gds)
print(f"placed {len(cells)} cells into TOP -> {out_gds}")
