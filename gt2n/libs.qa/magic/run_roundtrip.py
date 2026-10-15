#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Check that every GT2N cell library survives a GDS -> Magic -> GDS trip.

Usage: run_roundtrip.py [--workdir DIR] [lib ...]  (needs magic and klayout)
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PDK = HERE.parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", default=str(HERE / "run"))
    parser.add_argument("libs", nargs="*")
    args = parser.parse_args()
    work = Path(args.workdir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    libs = args.libs or sorted(p.name for p in (PDK / "libs.ref").iterdir() if p.is_dir())
    env = dict(os.environ, PDK_ROOT=str(PDK.parent), PDK=PDK.name)
    failed = []
    for lib in libs:
        src = PDK / "libs.ref" / lib / "gds" / f"{lib}.gds"
        out = work / f"{lib}_magic.gds"
        env.update(IN_GDS=str(src), OUT_GDS=str(out))
        subprocess.run(["magic", "-dnull", "-noconsole", "-rcfile",
                        str(PDK / "libs.tech" / "magic" / "gt2n.magicrc"),
                        str(HERE / "roundtrip.tcl")], env=env, check=True,
                       capture_output=True, cwd=work)
        # RTTOP is the wrapper cell roundtrip.tcl places every cell in.
        res = subprocess.run(["klayout", "-b", "-rd", f"a={src}", "-rd", f"b={out}",
                              "-rd", "extra=RTTOP", "-r", str(HERE / "xor.rb")],
                             capture_output=True, text=True)
        summary = [l for l in res.stdout.splitlines() if l.startswith("GT2N_XOR")]
        diffs = int(summary[-1].split()[1]) if summary else -1
        print(f"{lib}: {'PASS' if diffs == 0 else 'FAIL'} ({diffs} differences in shapes, texts or cells)")
        if diffs != 0:
            print(res.stdout[-2000:])
            failed.append(lib)
    if failed:
        sys.exit(f"Magic round-trip failed for: {' '.join(failed)}")


if __name__ == "__main__":
    main()
