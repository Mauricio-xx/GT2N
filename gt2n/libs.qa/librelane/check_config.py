#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Load the GT2N LibreLane configuration for every standard-cell library.

Instantiates LibreLane's Classic flow with the example macro configuration
(examples/gt2n-librelane-macro) for each libs.ref/<lib>. This evaluates
libs.tech/librelane/config.tcl and <lib>/config.tcl, type-checks the PDK
variables LibreLane reads and checks that every referenced file exists,
without running any EDA tool.

LibreLane silently drops PDK-configuration keys that are not PDK variables
(pdk=True) of the flow, so the script also evaluates the raw PDK and library
Tcl files and fails on any key that is neither a PDK variable of the Classic
flow and its steps nor listed in OTHER_PDK_VARIABLES below.

Usage: python3 check_config.py [lib ...]   (requires the librelane package)
"""

import sys
from pathlib import Path

PDK = Path(__file__).resolve().parents[2]
REPO = PDK.parent
DESIGN = REPO / "examples" / "gt2n-librelane-macro" / "librelane" / "config.yaml"

# PDK variables of LibreLane steps that are not part of the Classic flow.
OTHER_PDK_VARIABLES = {
    "KLAYOUT_LVS_SCRIPT": "KLayout.LVS",
    "KLAYOUT_LVS_OPTIONS": "KLayout.LVS",
}


def raw_pdk_keys(lib):
    """Keys set by config.tcl and <lib>/config.tcl, evaluated as LibreLane does."""
    from librelane.common import TclUtils
    from librelane.config.pdk_compat import migrate_old_config

    tech = PDK / "libs.tech" / "librelane"
    initial = {"PDK_ROOT": str(REPO), "PDK": PDK.name, "STD_CELL_LIBRARY": lib}
    env = TclUtils._eval_env(dict(initial), (tech / "config.tcl").read_text())
    env = TclUtils._eval_env(env, (tech / lib / "config.tcl").read_text())
    env = migrate_old_config(env)
    return sorted(k for k in env if k not in ("PDK_ROOT", "PDK"))


def check_keys(lib, variables):
    from librelane.steps import Step

    pdk_vars = {v.name for v in variables if v.pdk}
    flow_vars = {v.name for v in variables}
    deprecated = {}
    for v in variables:
        for old in v.deprecated_names:
            deprecated[old if isinstance(old, str) else old[0]] = v.name
    errors = []
    for name, step_id in OTHER_PDK_VARIABLES.items():
        step = Step.factory.get(step_id)
        if step is not None and any(v.name == name and v.pdk for v in step.config_vars):
            pdk_vars.add(name)
        else:
            errors.append(f"{name} is not a PDK variable of {step_id}")
    for key in raw_pdk_keys(lib):
        if key in pdk_vars:
            continue
        if key in deprecated:
            errors.append(f"{key} is a deprecated name of {deprecated[key]}")
        elif key in flow_vars:
            errors.append(f"{key} is a design variable; LibreLane ignores it in a PDK configuration")
        else:
            errors.append(f"{key} is not a LibreLane variable")
    return errors


def main():
    from librelane.flows import Flow
    import librelane.flows.classic  # noqa: F401  (registers the flow)

    classic = Flow.factory.get("Classic")
    libs = sys.argv[1:] or sorted(p.name for p in (PDK / "libs.ref").iterdir() if p.is_dir())
    failed = False
    for lib in libs:
        flow = classic(str(DESIGN), pdk=PDK.name, pdk_root=str(REPO), scl=lib)
        cfg = flow.config
        assert cfg["STD_CELL_LIBRARY"] == lib
        assert cfg["WELLTAP_CELL"].endswith(lib[len("gt2_6t_"):])
        errors = check_keys(lib, flow.get_all_config_variables())
        for error in errors:
            print(f"{lib}: ERROR: {error}")
        failed |= bool(errors)
        print(f"{lib}: {'FAIL' if errors else 'OK'} ({len(cfg)} variables)")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
