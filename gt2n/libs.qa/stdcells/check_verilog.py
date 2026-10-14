#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Formally check the generated Verilog models against the Liberty files.

For every library the Liberty file is read by Yosys as the golden model and
each Verilog model is proven equivalent with a SAT miter (temporal induction
for flip-flops, after async2sync). Yosys resolves a simultaneous clear and
preset differently from the Liberty clear_preset_var1 attribute, so for
flip-flops with both asynchronous inputs the proof is split in two runs (set
held inactive, then reset held inactive); the conflict case is covered by
the Icarus simulation in tb_dffasync.v.

Usage: check_verilog.py [lib ...]   (requires yosys in PATH)
"""

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "scripts"))

import liberty  # noqa: E402
from gt2n_common import LIBS_REF, all_libs  # noqa: E402


def script_for(lib):
    libdir = LIBS_REF / lib
    libfile = sorted((libdir / "lib").glob("*.lib"))[0]
    vfile = libdir / "verilog" / f"{lib}.v"
    tree = liberty.read(libfile)
    lines = [
        f"read_liberty -ignore_miss_func {libfile}",
        "design -stash gold",
        f"read_verilog -sv {vfile}",
        "proc",
        "design -stash gate",
    ]
    checked = []
    for cell in tree.children("cell"):
        outputs = [p for p in cell.children("pin") if p.get("direction") == "output"]
        if not outputs:
            continue  # physical-only cell
        name = cell.name
        lines += [
            "design -reset",
            f"design -copy-from gold -as gold {name}",
            f"design -copy-from gate -as gate {name}",
            "miter -equiv -flatten -make_assert gold gate miter",
            "hierarchy -top miter",
        ]
        ffs = cell.children("ff")
        if not ffs:
            lines.append("sat -prove-asserts -verify miter")
        else:
            lines.append("async2sync")
            ff = ffs[0]
            clear = ff.get("clear")
            preset = ff.get("preset")
            pins = {p.name for p in cell.children("pin")}
            rn = next((p for p in pins if clear and p in clear), None)
            sn = next((p for p in pins if preset and p in preset), None)
            base = "sat -tempinduct -prove-asserts -set-init-zero -seq 1 -maxsteps 12 -verify"
            if rn and sn:
                lines.append(f"{base} -set in_{sn} 1 miter")
                lines.append(f"{base} -set in_{rn} 1 miter")
            else:
                lines.append(f"{base} miter")
        checked.append(name)
    return "\n".join(lines) + "\n", checked


def main():
    libs = sys.argv[1:] or all_libs()
    failed = []
    for lib in libs:
        script, cells = script_for(lib)
        with tempfile.NamedTemporaryFile("w", suffix=".ys", delete=False) as fh:
            fh.write(script)
        res = subprocess.run(["yosys", "-q", "-s", fh.name], capture_output=True, text=True)
        Path(fh.name).unlink()
        if res.returncode:
            failed.append(lib)
            print(f"{lib}: FAILED\n{res.stdout[-3000:]}{res.stderr[-3000:]}")
        else:
            print(f"{lib}: {len(cells)} cell models equivalent to Liberty")
    if failed:
        sys.exit(f"Verilog/Liberty mismatch in: {' '.join(failed)}")


if __name__ == "__main__":
    main()
