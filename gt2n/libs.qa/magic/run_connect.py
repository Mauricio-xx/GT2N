#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Check the connectivity and abstract-LEF rules of the GT2N Magic technology.

Runs connect.tcl in Magic and checks that abutting cuts on a shared conductor
connect, that crossing metals without a cut do not, that GATE under GCUT and
DUMMY does not conduct after a GDS round trip, that 'lef write -hide'
obstructs every routing layer the cell uses, that a LEF obstruction
overlapping a pin does not erase the pin, and that a LEF obstruction on a cut
layer does not connect.

Usage: run_connect.py [--workdir DIR]  (needs magic)
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PDK = HERE.parents[1]


def nodes(ext):
    """Node names of a Magic .ext file, and the label names merged into them."""
    names, equiv = [], []
    for line in ext.read_text().splitlines():
        f = line.split()
        if f and f[0] == "node":
            names.append(f[1].strip('"'))
        elif f and f[0] == "equiv":
            equiv.append((f[1].strip('"'), f[2].strip('"')))
    return names, equiv


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workdir", default=str(HERE / "run" / "connect"))
    args = parser.parse_args()
    work = Path(args.workdir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    for old in [*work.glob("*.ext"), *work.glob("*.lef"), *work.glob("*.gds"),
                *work.glob("*.feedback")]:
        old.unlink()
    env = dict(os.environ, PDK_ROOT=str(PDK.parent), PDK=PDK.name)
    res = subprocess.run(["magic", "-dnull", "-noconsole", "-rcfile",
                          str(PDK / "libs.tech" / "magic" / "gt2n.magicrc"),
                          str(HERE / "connect.tcl")], env=env, cwd=work,
                         capture_output=True, text=True)
    (work / "magic.log").write_text(res.stdout + res.stderr)

    failed = []

    def check(name, ok, detail):
        print(f"{name}: {'PASS' if ok else 'FAIL'} ({detail})")
        if not ok:
            failed.append(name)

    abut = sorted(work.glob("abut_*.ext"))
    check("abutting cuts", len(abut) > 0, f"{len(abut)} cut pairs")
    for ext in abut:
        names, _ = nodes(ext)
        check(ext.stem, len(names) == 1, f"nodes {names}")

    for cell, want in (("open_m1_m2", 2), ("gate_cut_src", 3), ("lef_cut_obs", 2)):
        ext = work / f"{cell}.ext"
        if not ext.is_file():
            check(cell, False, "no .ext written")
            continue
        names, equiv = nodes(ext)
        check(cell, len(names) == want and not equiv,
              f"nodes {names}, merged {equiv}, expected {want} separate nodes")

    lef = work / "lef_obs.lef"
    want = {"BPR", "M0", "M1", "M2", "M3"}
    obs = set()
    if lef.is_file():
        m = re.search(r"^\s*OBS\b(.*?)^\s*END\b", lef.read_text(), re.S | re.M)
        if m:
            obs = set(re.findall(r"LAYER\s+(\S+)\s*;", m.group(1)))
    check("lef write -hide OBS", want <= obs,
          f"OBS layers {sorted(obs)}, expected {sorted(want)}")

    ext, top = work / "lef_pin_obs.ext", work / "lef_pin_obs_top.ext"
    fb = work / "lef_pin_obs.feedback"
    if ext.is_file() and top.is_file() and fb.is_file():
        names, _ = nodes(ext)
        merged = [l for l in top.read_text().splitlines()
                  if l.startswith("merge") and "/P\"" in l and '"W"' in l]
        count = fb.read_text().strip()
        check("lef_pin_obs", names == ["P"] and bool(merged) and count == "0",
              f"abstract nodes {names}, parent wire merged with P: {bool(merged)}, "
              f"illegal overlaps {count}")
    else:
        check("lef_pin_obs", False, "no .ext or feedback written")

    if failed:
        sys.exit(f"Magic connectivity checks failed: {' '.join(failed)} (see {work})")


if __name__ == "__main__":
    main()
