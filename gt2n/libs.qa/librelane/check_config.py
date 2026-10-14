#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Load the GT2N LibreLane configuration for every standard-cell library.

Instantiates LibreLane's Classic flow with the example macro configuration
(examples/gt2n-librelane-macro) for each libs.ref/<lib>. This evaluates
libs.tech/librelane/config.tcl and <lib>/config.tcl, type-checks every
PDK variable and checks that every referenced file exists, without running
any EDA tool.

Usage: python3 check_config.py [lib ...]   (requires the librelane package)
"""

import sys
from pathlib import Path

PDK = Path(__file__).resolve().parents[2]
REPO = PDK.parent
DESIGN = REPO / "examples" / "gt2n-librelane-macro" / "librelane" / "config.yaml"


def main():
    from librelane.flows import Flow
    import librelane.flows.classic  # noqa: F401  (registers the flow)

    classic = Flow.factory.get("Classic")
    libs = sys.argv[1:] or sorted(p.name for p in (PDK / "libs.ref").iterdir() if p.is_dir())
    for lib in libs:
        flow = classic(str(DESIGN), pdk=PDK.name, pdk_root=str(REPO), scl=lib)
        cfg = flow.config
        assert cfg["STD_CELL_LIBRARY"] == lib
        assert cfg["WELLTAP_CELL"].endswith(lib[len("gt2_6t_"):])
        print(f"{lib}: OK ({len(cfg)} variables)")


if __name__ == "__main__":
    main()
