# SPDX-License-Identifier: BSD-3-Clause
#
# Write the CDL netlist of a placed-and-routed GT2N design for LVS.
#
#   ODB=<design.odb> CELL_CDL=<library.cdl> OUT=<design.cdl> openroad -exit write_cdl.tcl
#
# The filler instances are written too: the GT2N filler LEF macros are CLASS
# CORE, not CORE SPACER, so -include_fillers makes no difference. The filler
# cell has no devices; the LVS deck merges the filler instances into the top
# cell of the layout and the empty filler subcircuit of the schematic is
# flattened away.

read_db $::env(ODB)
write_cdl -masters [list $::env(CELL_CDL)] $::env(OUT)
