#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Transistor-level KLayout LVS of every GT2N standard cell against its CDL.

Each cell of libs.ref/<lib>/gds/<lib>.gds is extracted with
libs.tech/klayout/tech/lvs/gt2n.lylvs in transistor mode and compared with
the matching subcircuit of libs.ref/<lib>/cdl/<lib>.cdl. Cells run in
parallel (one KLayout process per cell).

Usage: run_lvs.py [--workdir DIR] [-j N] [lib ...]   (requires klayout in PATH)
"""

import argparse
import os
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
    return cell, "Netlists match" in out


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
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for lib in libs:
            gds = PDK / "libs.ref" / lib / "gds" / f"{lib}.gds"
            cdl = PDK / "libs.ref" / lib / "cdl" / f"{lib}.cdl"
            cells = cells_of(cdl)
            results = list(pool.map(lambda c: run_cell(gds, cdl, c, work), cells))
            bad = [c for c, ok in results if not ok]
            if bad:
                failed.append(lib)
                print(f"{lib}: FAIL ({len(bad)}/{len(cells)} cells): {' '.join(bad)}")
            else:
                print(f"{lib}: PASS ({len(cells)} cells, transistor level)")
            sys.stdout.flush()
    if failed:
        sys.exit(f"LVS failed for: {' '.join(failed)}")


if __name__ == "__main__":
    main()
