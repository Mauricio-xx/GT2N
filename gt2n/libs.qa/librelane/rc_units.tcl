# SPDX-License-Identifier: BSD-3-Clause
#
# Replay of the unit handling of LibreLane's OpenROAD steps, run by
# check_rc_units.py as a LibreLane step (so the environment is LibreLane's).
#
#   _GT2N_RC_MODE=pnr  as gpl.tcl, cts.tcl, grt.tcl, repair_design.tcl ...:
#                      read_current_odb (Liberty, ODB, PNR_SDC_FILE), set_rc.tcl
#   _GT2N_RC_MODE=sta  as sta/corner.tcl: set_cmd_units ... -resistance kOhm
#                      first, then the same
#
# Prints the resulting parasitics in SI units as metrics.

source $::env(SCRIPTS_DIR)/openroad/common/io.tcl

if { $::env(_GT2N_RC_MODE) eq "sta" } {
    set_cmd_units -time ns -capacitance pF -current mA -voltage V -resistance kOhm -distance um
}
read_current_odb
source $::env(SCRIPTS_DIR)/openroad/common/set_rc.tcl

set tech [ord::get_db_tech]
foreach corner [sta::corners] {
    set name [$corner name]
    puts "%OL_METRIC_F gt2n__rc__resistance_unit_scale__corner:$name [sta::unit_scale resistance]"
    puts "%OL_METRIC_F gt2n__rc__wire_signal_resistance_ohm_per_m__corner:$name [est::wire_signal_resistance $corner]"
    foreach layer {M2 V1} {
        set r [est::layer_resistance [$tech findLayer $layer] $corner]
        puts "%OL_METRIC_F gt2n__rc__resistance_si__corner:$name:layer:$layer $r"
    }
    # Worst-slack max slew check, returned in command units.
    set limit [expr {[sta::max_slew_check_limit] * [sta::unit_scale time]}]
    puts "%OL_METRIC_F gt2n__rc__max_slew_limit_s__corner:$name $limit"
}
