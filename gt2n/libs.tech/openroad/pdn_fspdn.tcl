# SPDX-License-Identifier: BSD-3-Clause
#
# GT2N frontside power delivery network (FSPDN) for OpenROAD pdngen.
#
# Derived from the GT2N AES reference run (pdn_no_bpr_m2m3_rdl_dense.tcl):
#   * no BPR/followpin rails and no full-chip M1 stripes: the cell rails are
#     buried (BPR) and reach the frontside only through the tapfspdn cells,
#     which post_pdn_tap_to_m3.tcl hooks up to the M3 stripes below;
#   * alternating VDD/VSS M2/M3 stripes (GT2N_PDN_LOW_PITCH same-net pitch),
#     then a coarser mesh up to GT2N_PDN_TOP_LAYER.
#
# Knobs (environment, all optional):
#   GT2N_PDN_LOW_PITCH   same-net pitch of the M2/M3 stripes in um (6.0)
#   GT2N_PDN_LOW_OFFSET  offset of the first M2/M3 stripe in um     (3.0)
#   GT2N_PDN_TOP_LAYER   last mesh layer: M5, M9, M11, M13 or RDL  (RDL)
# pre_io_avoid_pdn_stripes.tcl reads the same LOW_* knobs to keep IO pins
# off the M2/M3 stripes.

proc gt2n_pdn_env {name default} {
  if {[info exists ::env($name)] && $::env($name) ne ""} { return $::env($name) }
  return $default
}

set low_pitch  [gt2n_pdn_env GT2N_PDN_LOW_PITCH 6.0]
set low_offset [gt2n_pdn_env GT2N_PDN_LOW_OFFSET 3.0]
set top_layer  [gt2n_pdn_env GT2N_PDN_TOP_LAYER RDL]

# layer width pitch offset (um). Upper layers use conservative widths
# relative to the tech LEF minimums (M10/M11 0.056, M12/M13 0.36, RDL 1.6).
set mesh [list \
  [list M2  0.012 $low_pitch $low_offset] \
  [list M3  0.014 $low_pitch $low_offset] \
  [list M4  0.028 8.0  4.0] \
  [list M5  0.028 8.0  4.0] \
  [list M6  0.076 12.0 6.0] \
  [list M7  0.076 12.0 6.0] \
  [list M8  0.076 12.0 6.0] \
  [list M9  0.076 12.0 6.0] \
  [list M10 0.224 8.0  4.0] \
  [list M11 0.224 8.0  4.0] \
  [list M12 0.720 12.0 6.0] \
  [list M13 0.720 12.0 6.0] \
  [list RDL 1.600 12.8 0.8] \
]

set layers {}
foreach entry $mesh {
  lappend layers [lindex $entry 0]
  if {[lindex $entry 0] eq $top_layer} { break }
}
if {[lindex $layers end] ne $top_layer} {
  error "GT2N_PDN_TOP_LAYER=$top_layer is not one of M5..M13 or RDL"
}

####################################
# global connections
####################################
add_global_connection -net {VDD} -inst_pattern {.*} -pin_pattern {^(vdd|VDD|VPWR)$} -power
add_global_connection -net {VSS} -inst_pattern {.*} -pin_pattern {^(vss|VSS|VGND)$} -ground
global_connect

####################################
# voltage domain and core grid
####################################
set_voltage_domain -name {CORE} -power {VDD} -ground {VSS}
define_pdn_grid -name {grid} -voltage_domains {CORE} -pins [list $top_layer]

foreach entry $mesh {
  lassign $entry layer width pitch offset
  if {[lsearch -exact $layers $layer] < 0} { break }
  set extra {}
  # The M3 and top stripes reach the core boundary so that edge taps and
  # the top-level supply pins have something to land on.
  if {$layer eq "M3" || $layer eq $top_layer} { set extra {-extend_to_boundary} }
  add_pdn_stripe -grid {grid} -layer $layer -width $width -pitch $pitch -offset $offset {*}$extra
}

for {set i 0} {$i < [llength $layers] - 1} {incr i} {
  add_pdn_connect -grid {grid} -layers [list [lindex $layers $i] [lindex $layers [expr {$i + 1}]]]
}
