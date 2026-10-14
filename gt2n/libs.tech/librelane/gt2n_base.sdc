# SPDX-License-Identifier: BSD-3-Clause
#
# GT2N default SDC for LibreLane (PNR_SDC_FILE / SIGNOFF_SDC_FILE).
#
# The GT2N Liberty files use ps / ohm / pF, while LibreLane passes CLOCK_PERIOD
# and the other constraints in ns and kOhm (it only switches the STA steps to
# those units). Switch the command units first so every OpenROAD step reads
# the same values, then apply LibreLane's generic base SDC.
set_cmd_units -time ns -capacitance pF -current mA -voltage V -resistance kOhm -distance um
source $::env(SCRIPTS_DIR)/base.sdc
