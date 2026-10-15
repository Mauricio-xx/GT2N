#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Transistor-level KLayout LVS of every GT2N standard cell against its CDL.

Each cell of libs.ref/<lib>/gds/<lib>.gds is extracted with
libs.tech/klayout/tech/lvs/gt2n.lylvs in transistor mode and compared with
the matching subcircuit of libs.ref/<lib>/cdl/<lib>.cdl. Cells run in
parallel (one KLayout process per cell).

A cell passes when the netlists match and something was checked: device
pairs were compared, or, for the device-less cells (filler, tap cells; their
CDL subcircuits are empty), the deck's supply check passed. A match that
compared nothing counts as a failure.

Usage: run_lvs.py [--workdir DIR] [-j N] [lib ...]   (requires klayout in PATH)
"""

import argparse
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
PDK = HERE.parents[1]
DECK = PDK / "libs.tech" / "klayout" / "tech" / "lvs" / "gt2n.lylvs"


def cells_of(cdl):
    return sorted(line.split()[1] for line in cdl.read_text(errors="replace").splitlines()
                  if line.lower().startswith(".subckt"))


def run_cell(gds, cdl, cell, work):
    cmd = ["klayout", "-b", "-r", str(DECK), "-rd", f"input={gds}", "-rd", f"topcell={cell}",
           "-rd", f"schematic={cdl}", "-rd", "lvs_mode=transistor", "-rd", "threads=1",
           "-rd", f"report={work / (cell + '.lvsdb')}"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    out = res.stdout + res.stderr
    (work / f"{cell}_lvs.log").write_text(out)
    if "INFO : Congratulations! Netlists match." not in out:
        return cell, "fail"
    if re.search(r"top circuit \S+: [1-9]\d* device pair\(s\)", out):
        return cell, "device"
    if "supply check passed" in out:
        return cell, "supply"
    return cell, "unchecked"


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workdir", default=str(HERE / "run"))
    parser.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 1)
    parser.add_argument("libs", nargs="*")
    args = parser.parse_args()
    work = Path(args.workdir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    libs = args.libs or sorted(p.name for p in (PDK / "libs.ref").iterdir() if p.is_dir())
    failed = []
    totals = {"device": 0, "supply": 0}
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for lib in libs:
            gds = PDK / "libs.ref" / lib / "gds" / f"{lib}.gds"
            cdl = PDK / "libs.ref" / lib / "cdl" / f"{lib}.cdl"
            cells = cells_of(cdl)
            results = list(pool.map(lambda c: run_cell(gds, cdl, c, work), cells))
            bad = [c for c, status in results if status == "fail"]
            unchecked = [c for c, status in results if status == "unchecked"]
            device = sum(status == "device" for _, status in results)
            supply = sum(status == "supply" for _, status in results)
            totals["device"] += device
            totals["supply"] += supply
            if bad or unchecked:
                failed.append(lib)
                if bad:
                    print(f"{lib}: FAIL ({len(bad)}/{len(cells)} cells): {' '.join(bad)}")
                if unchecked:
                    print(f"{lib}: NOT CHECKED (match without any compared device or supply check): "
                          f"{' '.join(unchecked)}")
            else:
                print(f"{lib}: PASS ({len(cells)} cells: {device} compared at device level, "
                      f"{supply} device-less with supply check)")
            sys.stdout.flush()
    print(f"{totals['device']} cells compared at device level, "
          f"{totals['supply']} device-less cells with supply check")
    if failed:
        sys.exit(f"LVS failed for: {' '.join(failed)}")


if __name__ == "__main__":
    main()
