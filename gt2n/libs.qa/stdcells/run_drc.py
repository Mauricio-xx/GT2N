#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Run the GT2N KLayout DRC deck (full mode) on every standard-cell library.

For each libs.ref/<lib>/gds/<lib>.gds a test layout is built with
make_drc_testchip.py (every cell abutted by fillers, plus a small placed
block of abutted, mirrored rows) and checked with
libs.tech/klayout/tech/drc/gt2n.lydrc in full mode. Violations listed in
drc_waivers.txt (known issues of the upstream cell layouts) are reported but
do not fail the run.

Usage: run_drc.py [--workdir DIR] [lib ...]    (requires klayout in PATH)
"""

import argparse
import fnmatch
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PDK = HERE.parents[1]
DECK = PDK / "libs.tech" / "klayout" / "tech" / "drc" / "gt2n.lydrc"


def load_waivers():
    waivers = []
    for line in (HERE / "drc_waivers.txt").read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            rule, cell = line.split()[:2]
            waivers.append((rule, cell))
    return waivers


def waived(rule, cell, waivers):
    return any(fnmatch.fnmatch(rule, r) and fnmatch.fnmatch(cell, c) for r, c in waivers)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workdir", default=str(HERE / "run"))
    parser.add_argument("--mode", default="full", choices=("full", "route"))
    parser.add_argument("libs", nargs="*")
    args = parser.parse_args()
    work = Path(args.workdir)
    work.mkdir(parents=True, exist_ok=True)
    libs = args.libs or sorted(p.name for p in (PDK / "libs.ref").iterdir() if p.is_dir())
    waivers = load_waivers()
    failed = []
    for lib in libs:
        gds = PDK / "libs.ref" / lib / "gds" / f"{lib}.gds"
        chip = work / f"{lib}_drc_top.gds"
        rdb = work / f"{lib}_drc.lyrdb"
        subprocess.run(["klayout", "-b", "-r", str(HERE / "make_drc_testchip.py"),
                        "-rd", f"in_gds={gds}", "-rd", f"out_gds={chip}"],
                       check=True, capture_output=True)
        subprocess.run(["klayout", "-b", "-r", str(DECK), "-rd", f"input={chip}",
                        "-rd", "topcell=TOP", "-rd", f"report={rdb}",
                        "-rd", f"drc_mode={args.mode}"], check=True, capture_output=True)
        real, known = Counter(), Counter()
        for item in ET.parse(rdb).getroot().iter("item"):
            rule = item.find("category").text.strip("'")
            cell = item.find("cell").text
            (known if waived(rule, cell, waivers) else real)[(rule, cell)] += 1
        status = "FAIL" if real else "PASS"
        print(f"{lib}: {status} ({sum(real.values())} violation(s), "
              f"{sum(known.values())} waived)")
        for (rule, cell), n in sorted(real.items()):
            print(f"    {rule:12s} {cell} x{n}")
        if real:
            failed.append(lib)
    if failed:
        sys.exit(f"DRC failed for: {' '.join(failed)}")


if __name__ == "__main__":
    main()
