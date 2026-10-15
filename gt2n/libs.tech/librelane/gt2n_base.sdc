# SPDX-License-Identifier: BSD-3-Clause
#
# GT2N default SDC for LibreLane (PNR_SDC_FILE / SIGNOFF_SDC_FILE).
#
# The GT2N Liberty files use ps / ohm / pF. LibreLane passes CLOCK_PERIOD and
# the other constraints in ns, and its STA steps switch the command units to
# ns/kOhm before reading this file. LibreLane applies LAYERS_RC and VIAS_R
# (ohm and pF per um, ohm) with set_layer_rc after reading this file, in the
# command units then in effect. Switch the command units to ns and ohm here,
# so every OpenROAD step reads the constraints in ns and the parasitics in
# ohm, then apply LibreLane's generic base SDC.
set_cmd_units -time ns -capacitance pF -current mA -voltage V -resistance ohm -distance um
source $::env(SCRIPTS_DIR)/base.sdc
