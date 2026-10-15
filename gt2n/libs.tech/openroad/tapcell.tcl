set tapcell_distance 14
if {[info exists ::env(TAPCELL_DISTANCE)] && $::env(TAPCELL_DISTANCE) ne ""} {
  set tapcell_distance $::env(TAPCELL_DISTANCE)
}

# The tap cell is also the endcap, so every row segment (rows narrower than
# the tap distance, rows cut by macros) ties its BPR rails to a tap;
# gt2n_tap_to_m3.tcl stops the flow when a rail segment has none.
tapcell \
  -distance $tapcell_distance \
  -tapcell_master "$::env(TAP_CELL_NAME)" \
  -endcap_master "$::env(TAP_CELL_NAME)"
