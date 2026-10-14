#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Cross-check the cell views of every GT2N standard-cell library.

For each libs.ref/<lib> the script collects the cell names found in the
Liberty, LEF, GDS, CDL, SPICE and Verilog views and reports cells that are
missing from one of them, plus pin mismatches between Liberty, LEF, CDL and
Verilog. Physical-only cells (filler, tap, decap) are allowed to be absent
from timing-oriented views as documented in PHYSICAL_ONLY.

Exit status is non-zero when an inconsistency is found.
"""

import re
import struct
import sys
from pathlib import Path

LIBS_REF = Path(__file__).resolve().parents[2] / "libs.ref"
PG_PINS = {"vdd", "vss"}


def strip_comments(text):
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def liberty_cells(path):
    text = strip_comments(path.read_text(errors="replace"))
    cells = {}
    for m in re.finditer(r"^\s*cell\s*\(\s*\"?([\w]+)\"?\s*\)", text, re.M):
        start = m.end()
        nxt = re.search(r"^\s*cell\s*\(", text[start:], re.M)
        body = text[start:start + nxt.start()] if nxt else text[start:]
        pins = set(re.findall(r"^\s*pin\s*\(\s*\"?(\w+)\"?\s*\)", body, re.M))
        cells[m.group(1)] = pins
    return cells


def lef_cells(path):
    cells = {}
    current = None
    for line in path.read_text(errors="replace").splitlines():
        tok = line.split()
        if not tok:
            continue
        if tok[0] == "MACRO":
            current = tok[1]
            cells[current] = set()
        elif tok[0] == "PIN" and current:
            cells[current].add(tok[1])
        elif tok[0] == "END" and len(tok) > 1 and tok[1] == current:
            current = None
    return cells


def spice_cells(path):
    cells = {}
    for line in path.read_text(errors="replace").splitlines():
        tok = line.split()
        if tok and tok[0].lower() == ".subckt":
            cells[tok[1]] = {t for t in tok[2:] if "=" not in t}
    return cells


def verilog_cells(path):
    text = path.read_text(errors="replace")
    cells = {}
    for m in re.finditer(r"^\s*module\s+(\w+)\s*\((.*?)\)\s*;", text, re.M | re.S):
        ports = re.sub(r"`\w+(\s+\w+)?", " ", m.group(2))
        cells[m.group(1)] = {p for p in re.findall(r"\w+", ports)}
    return cells


def gds_cells(path):
    data = path.read_bytes()
    names = set()
    pos = 0
    while pos + 4 <= len(data):
        length, rtype = struct.unpack(">HH", data[pos:pos + 4])
        if length < 4:
            break
        if rtype == 0x0606:  # STRNAME
            names.add(data[pos + 4:pos + length].rstrip(b"\0").decode())
        pos += length
    return {n: None for n in names}


PHYSICAL_ONLY = re.compile(r"_(filler|tap[bf]spdn|decapcc)_")


def check_lib(libdir):
    lib = libdir.name
    errors = []
    views = {}
    for p in sorted((libdir / "lib").glob("*.lib")):
        views[f"lib:{p.stem}"] = liberty_cells(p)
    views["lef"] = lef_cells(libdir / "lef" / f"{lib}.lef")
    views["gds"] = gds_cells(libdir / "gds" / f"{lib}.gds")
    views["cdl"] = spice_cells(libdir / "cdl" / f"{lib}.cdl")
    for opt, fn in (("spice", spice_cells), ("verilog", verilog_cells)):
        ext = {"spice": "spice", "verilog": "v"}[opt]
        p = libdir / opt / f"{lib}.{ext}"
        if p.is_file():
            views[opt] = fn(p)

    reference = views["lef"]
    for name, cells in views.items():
        missing = sorted(set(reference) - set(cells))
        extra = sorted(set(cells) - set(reference))
        if name == "gds":
            extra = []  # GDS may carry helper/via cells
        if missing:
            errors.append(f"{lib}: {name} lacks {len(missing)} cell(s): {' '.join(missing)}")
        if extra:
            errors.append(f"{lib}: {name} has {len(extra)} cell(s) not in LEF: {' '.join(extra)}")

    # Pin consistency (Liberty pins exclude pg_pin groups).
    for name, cells in views.items():
        if name in ("lef", "gds"):
            continue
        for cell, pins in cells.items():
            lef_pins = reference.get(cell)
            if lef_pins is None or pins is None:
                continue
            expected = lef_pins if name != "lib" and not name.startswith("lib:") else lef_pins - PG_PINS
            got = pins
            if name == "verilog":
                got = pins - PG_PINS
                expected = lef_pins - PG_PINS
            if got != expected:
                errors.append(f"{lib}: {name} pins of {cell} {sorted(got)} != LEF {sorted(expected)}")
    return errors, {k: len(v) for k, v in views.items()}


def main():
    libs = sorted(p for p in LIBS_REF.iterdir() if p.is_dir())
    all_errors = []
    for libdir in libs:
        errors, counts = check_lib(libdir)
        print(f"{libdir.name}: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
        all_errors += errors
    for e in all_errors:
        print("ERROR:", e)
    if all_errors:
        sys.exit(1)
    print(f"OK: {len(libs)} libraries consistent")


if __name__ == "__main__":
    main()
