#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Check the wire and via resistance LibreLane's OpenROAD steps estimate with.

LibreLane passes LAYERS_RC and VIAS_R to set_layer_rc unchanged, in the
command units in effect at that point: after the PnR SDC (gt2n_base.sdc) has
been read, and in the STA steps after their own switch to kOhm. The GT2N
values are in ohm/um and ohm, so the SDC must leave the resistance unit at
ohm. A kOhm unit makes every estimate 1000 times too large.

For each library given (default gt2_6t_w31_svt), the script loads the
Classic flow configuration of the example macro, builds a one-buffer ODB
and runs rc_units.tcl as a LibreLane OpenROAD step, once as a PnR step and
once with the STA unit switch first. It then checks that M2, V1 and the
signal-wire average equal the configured LAYERS_RC/VIAS_R values in ohm, and
that the max slew limit equals MAX_TRANSITION_CONSTRAINT.

Usage: python3 check_rc_units.py [lib ...]   (requires librelane and openroad)
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PDK = HERE.parents[1]
REPO = PDK.parent
DESIGN = REPO / "examples" / "gt2n-librelane-macro" / "librelane" / "config.yaml"

NETLIST = """\
module gt2n_rc_top (input clk, input a, output y);
  {buf} u0 (.A(a), .Y(y));
endmodule
"""

ODB_TCL = """\
read_lef {tech_lef}
read_lef {cell_lef}
read_verilog {netlist}
link_design gt2n_rc_top
initialize_floorplan -site {site} -die_area "0 0 5 5" -core_area "0.504 0.576 4.496 4.424"
write_db {odb}
"""


def make_odb(cfg, lib, tmp):
    flavor = lib[len("gt2_6t_"):]
    netlist = tmp / "gt2n_rc_top.v"
    netlist.write_text(NETLIST.format(buf=f"gt2_6t_buf_x1_{flavor}"))
    odb = tmp / "gt2n_rc_top.odb"
    script = tmp / "make_odb.tcl"
    script.write_text(ODB_TCL.format(
        tech_lef=cfg["TECH_LEFS"]["*"], cell_lef=cfg["CELL_LEFS"][0],
        netlist=netlist, site=cfg["PLACE_SITE"], odb=odb))
    subprocess.run(["openroad", "-exit", "-no_splash", str(script)], check=True,
                   stdout=subprocess.DEVNULL)
    return odb


def close(a, b):
    return abs(a - b) <= 1e-6 * max(abs(a), abs(b))


def check_lib(classic, lib):
    from librelane.common import Path as ViewPath
    from librelane.state import DesignFormat, State
    from librelane.steps.openroad import OpenROADStep

    class RCUnitsReplay(OpenROADStep):
        id = "GT2N.RCUnitsReplay"
        name = "GT2N RC units replay"
        outputs = []

        def get_script_path(self):
            return str(HERE / "rc_units.tcl")

    flow = classic(str(DESIGN), pdk=PDK.name, pdk_root=str(REPO), scl=lib)
    cfg = flow.config
    corner = cfg["DEFAULT_CORNER"]
    rc = next(v for k, v in cfg["LAYERS_RC"].items() if k == "*")
    vias = next(v for k, v in cfg["VIAS_R"].items() if k == "*")
    m2_ohm_per_um = float(rc["M2"]["res"])
    v1_ohm = float(vias["V1"]["res"])
    res_range = [float(v["res"]) for v in rc.values()]
    max_tran_ns = float(cfg["MAX_TRANSITION_CONSTRAINT"])

    errors = []
    with tempfile.TemporaryDirectory(prefix="gt2n_rc_") as d:
        tmp = Path(d)
        odb = make_odb(cfg, lib, tmp)
        for mode in ("pnr", "sta"):
            os.environ["_GT2N_RC_MODE"] = mode
            state_in = State({DesignFormat.ODB: ViewPath(odb)})
            step = RCUnitsReplay(config=cfg, state_in=state_in)
            step_dir = tmp / mode
            step_dir.mkdir()
            state = step.start(step_dir=str(step_dir))
            m = {k: float(v) for k, v in state.metrics.items() if k.startswith("gt2n__rc__")}
            sfx = f"__corner:{corner}"
            wire = m[f"gt2n__rc__wire_signal_resistance_ohm_per_m{sfx}"] * 1e-6
            m2 = m[f"gt2n__rc__resistance_si{sfx}:layer:M2"] * 1e-6
            v1 = m[f"gt2n__rc__resistance_si{sfx}:layer:V1"]
            slew = m[f"gt2n__rc__max_slew_limit_s{sfx}"] * 1e9
            unit = m[f"gt2n__rc__resistance_unit_scale{sfx}"]
            print(f"{lib} {mode}: resistance unit {unit:g} ohm, signal wire "
                  f"{wire:.4g} ohm/um, M2 {m2:.6g} ohm/um, V1 {v1:.6g} ohm, "
                  f"max slew {slew:.4g} ns")
            if not close(m2, m2_ohm_per_um):
                errors.append(f"{mode}: M2 {m2:g} ohm/um, configured {m2_ohm_per_um:g}")
            if not close(v1, v1_ohm):
                errors.append(f"{mode}: V1 {v1:g} ohm, configured {v1_ohm:g}")
            if not min(res_range) <= wire <= max(res_range):
                errors.append(f"{mode}: signal wire {wire:g} ohm/um outside the configured "
                              f"{min(res_range):g}..{max(res_range):g}")
            if not close(slew, max_tran_ns):
                errors.append(f"{mode}: max slew limit {slew:g} ns, "
                              f"MAX_TRANSITION_CONSTRAINT {max_tran_ns:g}")
    return errors


def main():
    from librelane.flows import Flow
    import librelane.flows.classic  # noqa: F401  (registers the flow)
    from librelane.logging import set_log_level

    set_log_level("WARNING")
    classic = Flow.factory.get("Classic")
    failed = False
    for lib in sys.argv[1:] or ["gt2_6t_w31_svt"]:
        errors = check_lib(classic, lib)
        for error in errors:
            print(f"{lib}: ERROR: {error}")
        print(f"{lib}: {'FAIL' if errors else 'OK'}")
        failed |= bool(errors)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
