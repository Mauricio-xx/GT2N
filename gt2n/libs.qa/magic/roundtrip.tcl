# SPDX-License-Identifier: BSD-3-Clause
# Read a GT2N cell library GDS into Magic and write all cells back out.
# Environment: PDK_ROOT, IN_GDS, OUT_GDS. Run with
#   magic -dnull -noconsole -rcfile $PDK_ROOT/gt2n/libs.tech/magic/gt2n.magicrc roundtrip.tcl
gds read $::env(IN_GDS)
set cells [cellname list allcells]
load RTTOP
set y 0
foreach c $cells {
    if {$c eq "RTTOP" || $c eq "(UNNAMED)"} { continue }
    box 0 $y 0 $y
    getcell $c
    incr y 1000
}
gds write $::env(OUT_GDS)
quit -noprompt
