# SPDX-License-Identifier: BSD-3-Clause
#
# GT2N FSPDN: connect the tap-cell supply pins to the frontside M3 PDN.
#
# In the frontside-PDN router view (gt2_fspdn_tech.lef) the standard-cell
# rails are buried power rails (BPR, a MASTERSLICE layer the router cannot
# use). The only frontside access to the rails is the pair of M1 pins of the
# gt2_6t_tapfspdn_* cells, which tie BPR to M1 inside the cell. pdngen does
# not connect to those pins, so this POST_PDN_TCL hook adds, for every tap
# pin that check_power_grid reports as unconnected:
#
#     tap M1 pin -> V1 -> local M2 jog -> V2 -> nearest same-net M3 stripe
#
# Generalised from the GT2N AES reference run: instead of fixed stripe
# offsets, the M2/M3 stripe positions are read back from the PDN that
# gt2n_pdn_fspdn.tcl (or any user PDN with M2 and M3 stripes) has just built.
#
# Rules followed:
#   * no new M1 is drawn; only the V1 landing on the existing tap pin;
#   * pdngen trims stripes back to their last via, so an M3 stripe may end
#     before the rows at the top/bottom of the core: the stripe is extended
#     along its own track until it covers the jog;
#   * the M2 jog is moved off any global M2 stripe (width + spacing apart);
#   * VDD jogs run to the left, VSS jogs to the right (when such a stripe
#     exists), so the jogs of the adjacent VDD/VSS tap pins move apart;
#   * a jog never shares an M2 track with an overlapping jog of another net
#     (both jogs of a tap near the core edge run to the same side). When no
#     track is clear the script stops instead of drawing a short.
#
# Environment knobs (all optional):
#   GT2N_TAP_M3_NETS    supply nets to repair       (default "VDD VSS")
#   GT2N_TAP_M3_SIDES   preferred side per net      (default "left right")

set ::gt2n_tap_out_dir [file join $::env(REPORTS_DIR) tap_pg_to_m3]
file mkdir $::gt2n_tap_out_dir

proc gt2n_tap_dbu {} {
  return [[ord::get_db_tech] getDbUnitsPerMicron]
}

proc gt2n_tap_um_to_dbu {v} {
  return [expr {int(round(double($v) * [gt2n_tap_dbu]))}]
}

# Collect stripe centre lines of a net on a layer from its special wires.
#   axis x -> vertical stripes (returns x centres), axis y -> horizontal.
proc gt2n_tap_stripe_centres {net_name layer_name axis} {
  set block [ord::get_db_block]
  set net [$block findNet $net_name]
  set centres {}
  if {$net == "NULL"} { return $centres }
  foreach swire [$net getSWires] {
    foreach box [$swire getWires] {
      if {[$box isVia]} { continue }
      if {[[$box getTechLayer] getName] ne $layer_name} { continue }
      set w [expr {[$box xMax] - [$box xMin]}]
      set h [expr {[$box yMax] - [$box yMin]}]
      if {$axis eq "x" && $h > $w} {
        lappend centres [expr {([$box xMin] + [$box xMax]) / 2}]
      } elseif {$axis eq "y" && $w > $h} {
        lappend centres [expr {([$box yMin] + [$box yMax]) / 2}]
      }
    }
  }
  return [lsort -integer -unique $centres]
}

# Vertical extent of the stripes of a net on a layer, keyed by centre x:
# returns a dict  x -> {ylo yhi halfwidth}.
proc gt2n_tap_stripe_extents {net_name layer_name} {
  set block [ord::get_db_block]
  set net [$block findNet $net_name]
  set extents [dict create]
  if {$net == "NULL"} { return $extents }
  foreach swire [$net getSWires] {
    foreach box [$swire getWires] {
      if {[$box isVia]} { continue }
      if {[[$box getTechLayer] getName] ne $layer_name} { continue }
      set w [expr {[$box xMax] - [$box xMin]}]
      set h [expr {[$box yMax] - [$box yMin]}]
      if {$h <= $w} { continue }
      set x [expr {([$box xMin] + [$box xMax]) / 2}]
      if {[dict exists $extents $x]} {
        lassign [dict get $extents $x] lo hi hw
        dict set extents $x [list [expr {min($lo, [$box yMin])}] [expr {max($hi, [$box yMax])}] $hw]
      } else {
        dict set extents $x [list [$box yMin] [$box yMax] [expr {$w / 2}]]
      }
    }
  }
  return $extents
}

proc gt2n_tap_pick_stripe {cx stripes side} {
  set left {}
  set right {}
  foreach s $stripes {
    if {$s <= $cx} { lappend left $s }
    if {$s >= $cx} { lappend right $s }
  }
  if {$side eq "left" && [llength $left]} { return [lindex $left end] }
  if {$side eq "right" && [llength $right]} { return [lindex $right 0] }
  # Fall back to the nearest stripe on either side.
  set best ""
  foreach s $stripes {
    if {$best eq "" || abs($s - $cx) < abs($best - $cx)} { set best $s }
  }
  return $best
}

proc gt2n_tap_clear_of {y others keepout} {
  foreach o $others {
    if {abs($y - $o) < $keepout} { return 0 }
  }
  return 1
}

# Jogs drawn so far, as {net lx ux y}.
set ::gt2n_tap_jogs {}

# True when an M2 jog of net_name from lx to ux on track y keeps keepout
# (track direction) and xgap (along the track) from every jog of another net.
proc gt2n_tap_jog_clear {net_name lx ux y keepout xgap} {
  foreach jog $::gt2n_tap_jogs {
    lassign $jog onet olx oux oy
    if {$onet eq $net_name} { continue }
    if {abs($y - $oy) >= $keepout} { continue }
    if {$lx - $xgap < $oux && $ux + $xgap > $olx} { return 0 }
  }
  return 1
}

proc gt2n_tap_repair_net {net_name side m3_stripes m2_stripes} {
  set m3_extents [gt2n_tap_stripe_extents $net_name M3]
  set extended 0
  set block [ord::get_db_block]
  set tech [ord::get_db_tech]
  set net [$block findNet $net_name]
  if {$net == "NULL"} {
    puts "GT2N_TAP_M3: net $net_name not found, skipping"
    return
  }
  if {![llength $m3_stripes]} {
    error "GT2N_TAP_M3: no M3 stripes found for $net_name; the PDN must have M3 stripes"
  }

  set m2 [$tech findLayer M2]
  set m3 [$tech findLayer M3]
  set v1 [$tech findVia V1_0]
  set v2 [$tech findVia V2_0]
  if {$m2 == "NULL" || $v1 == "NULL" || $v2 == "NULL"} {
    error "GT2N_TAP_M3: cannot find M2, V1_0 or V2_0 in the tech LEF"
  }
  set m2_pitch [$m2 getPitchY]
  if {$m2_pitch <= 0} { set m2_pitch [$m2 getPitch] }
  set m2_offset [$m2 getOffsetY]
  if {$m2_offset <= 0} { set m2_offset [expr {$m2_pitch / 2}] }
  set m2_width [$m2 getWidth]
  set m2_half [expr {$m2_width / 2}]
  # A jog must stay one width + one spacing away from any global M2 stripe.
  set keepout [expr {$m2_width + [$m2 getSpacing]}]
  # Along a track, the V1/V2 M2 pads of two jogs of different nets must keep
  # the M2 spacing: centres at least two pad half-widths + spacing apart.
  set pad_half $m2_half
  foreach box [$v1 getBoxes] {
    if {[$box getTechLayer] == $m2} {
      set pad_half [expr {max($pad_half, ([$box xMax] - [$box xMin]) / 2)}]
    }
  }
  set xgap [expr {2 * $pad_half + [$m2 getSpacing]}]

  set before [file join $::gt2n_tap_out_dir ${net_name}.before.rpt]
  file delete -force $before
  catch {check_power_grid -net $net_name -error_file $before} msg
  puts "GT2N_TAP_M3: $net_name before repair: $msg"

  set added 0
  set moved 0
  if {[file exists $before]} {
    set swire [odb::dbSWire_create $net "ROUTED"]
    set fh [open $before r]
    while {[gets $fh line] >= 0} {
      if {![regexp {bbox = \(([-0-9.]+), ([-0-9.]+)\) - \(([-0-9.]+), ([-0-9.]+)\) on Layer M1} \
              $line -> x1 y1 x2 y2]} {
        continue
      }
      set x1 [gt2n_tap_um_to_dbu $x1]
      set x2 [gt2n_tap_um_to_dbu $x2]
      set y1 [gt2n_tap_um_to_dbu $y1]
      set y2 [gt2n_tap_um_to_dbu $y2]
      set cx [expr {($x1 + $x2) / 2}]
      set cy [expr {($y1 + $y2) / 2}]
      set m3_x [gt2n_tap_pick_stripe $cx $m3_stripes $side]
      set lx [expr {min($cx, $m3_x)}]
      set ux [expr {max($cx, $m3_x)}]
      if {$ux == $lx} { incr ux }

      # Start on the M2 track closest to the pin centre and walk along the pin
      # until the jog is clear of every global M2 stripe and of the jogs of
      # the other nets.
      set n [expr {int(floor(double($cy - $m2_offset) / $m2_pitch + 0.5))}]
      set m2_y [expr {$m2_offset + $n * $m2_pitch}]
      set chosen ""
      foreach step {0 -1 1 -2 2 -3 3 -4 4} {
        set cand [expr {$m2_y + $step * $m2_pitch}]
        if {$cand - $m2_half < $y1 || $cand + $m2_half > $y2} { continue }
        if {[gt2n_tap_clear_of $cand $m2_stripes $keepout] &&
            [gt2n_tap_jog_clear $net_name $lx $ux $cand $keepout $xgap]} {
          set chosen $cand
          break
        }
      }
      if {$chosen eq ""} {
        error "GT2N_TAP_M3: no free M2 track for the $net_name tap pin at ($cx, $cy)"
      } elseif {$chosen != $m2_y} {
        incr moved
      }
      lappend ::gt2n_tap_jogs [list $net_name $lx $ux $chosen]
      odb::dbSBox_create $swire $m2 $lx [expr {$chosen - $m2_half}] $ux [expr {$chosen + $m2_half}] "STRIPE"
      odb::dbSBox_create $swire $v1 $cx $chosen "STRIPE"
      odb::dbSBox_create $swire $v2 $m3_x $chosen "STRIPE"
      # Extend a trimmed M3 stripe along its track until it covers the via.
      if {[dict exists $m3_extents $m3_x]} {
        lassign [dict get $m3_extents $m3_x] lo hi hw
        set need_lo [expr {$chosen - 2 * $m2_width}]
        set need_hi [expr {$chosen + 2 * $m2_width}]
        if {$need_lo < $lo || $need_hi > $hi} {
          set new_lo [expr {min($lo, $need_lo)}]
          set new_hi [expr {max($hi, $need_hi)}]
          if {$new_lo < $lo} {
            odb::dbSBox_create $swire $m3 [expr {$m3_x - $hw}] $new_lo [expr {$m3_x + $hw}] $lo "STRIPE"
          }
          if {$new_hi > $hi} {
            odb::dbSBox_create $swire $m3 [expr {$m3_x - $hw}] $hi [expr {$m3_x + $hw}] $new_hi "STRIPE"
          }
          dict set m3_extents $m3_x [list $new_lo $new_hi $hw]
          incr extended
        }
      }
      incr added
    }
    close $fh
  }

  set after [file join $::gt2n_tap_out_dir ${net_name}.after.rpt]
  file delete -force $after
  set status [catch {check_power_grid -net $net_name -error_file $after} msg]
  puts "GT2N_TAP_M3: $net_name added=$added jogs (moved to another M2 track: $moved, M3 stripes extended: $extended), after repair: $msg"
  if {$status != 0} {
    error "GT2N_TAP_M3: power grid of $net_name still disconnected, see $after"
  }
}

set gt2n_tap_nets {VDD VSS}
if {[info exists ::env(GT2N_TAP_M3_NETS)] && $::env(GT2N_TAP_M3_NETS) ne ""} {
  set gt2n_tap_nets $::env(GT2N_TAP_M3_NETS)
}
set gt2n_tap_sides {left right}
if {[info exists ::env(GT2N_TAP_M3_SIDES)] && $::env(GT2N_TAP_M3_SIDES) ne ""} {
  set gt2n_tap_sides $::env(GT2N_TAP_M3_SIDES)
}

# Global M2 stripes of every supply net are obstacles for the jogs.
set gt2n_m2_all {}
foreach net $gt2n_tap_nets {
  set gt2n_m2_all [concat $gt2n_m2_all [gt2n_tap_stripe_centres $net M2 y]]
}

foreach net $gt2n_tap_nets side $gt2n_tap_sides {
  if {$net eq ""} { continue }
  if {$side eq ""} { set side nearest }
  gt2n_tap_repair_net $net $side [gt2n_tap_stripe_centres $net M3 x] $gt2n_m2_all
}
