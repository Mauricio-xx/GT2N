# SPDX-License-Identifier: BSD-3-Clause
#
# Write the CDL netlist of a placed-and-routed GT2N design for LVS.
#
#   ODB=<design.odb> CELL_CDL=<library.cdl> OUT=<design.cdl> openroad -exit write_cdl.tcl
#
# Filler cells are left out: the GT2N LVS deck flattens them into the top
# cell of the layout (they have no devices).

read_db $::env(ODB)
write_cdl -masters [list $::env(CELL_CDL)] $::env(OUT)
