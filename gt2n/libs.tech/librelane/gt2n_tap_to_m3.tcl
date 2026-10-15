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
#     tap M1 pin -> V1 -> local M2 jog -> V2 -> same-net M3 stripe
#
# The stripe is the nearest one on the preferred side of the net (VDD left,
# VSS right, so the jogs of the two pins of a tap move apart), then the
# nearest one on the other side, then the next ones alternately.
#
# Generalised from the GT2N AES reference run: instead of fixed stripe
# offsets, the M2/M3 stripe positions are read back from the PDN that
# gt2n_pdn_fspdn.tcl (or any user PDN with M2 and M3 stripes) has just built.
#
# The script first checks the taps themselves and stops the flow when a
# buried power rail would float: there must be tap cells, and every BPR rail
# segment (the y of a row boundary, over the merged x extent of the rows
# sharing it) must touch one. Neither check_power_grid nor any other
# LibreLane check sees BPR, so such a rail would otherwise go unnoticed.
#
# Rules followed:
#   * no new M1 is drawn; only the V1 landing on the existing tap pin, with
#     its M1 enclosure inside the pin;
#   * pdngen trims stripes back to their last via and splits them around
#     macros and obstructions: a stripe segment is used where it covers the
#     V2, or extended along its own track from the nearest segment end;
#   * no jog, via or extension touches a PDN obstruction (dbObstruction, e.g.
#     LibreLane PDN_OBSTRUCTIONS) on its layer, or a placed block macro plus
#     the PDN macro halo of gt2n_pdn_fspdn.tcl;
#   * every jog keeps the M2 rules to all other M2 of the supply nets (global
#     stripes and other jogs): 12 nm spacing across tracks (M2.3), 17 nm tip
#     to tip on a track (M2.4, LEF58_EOLKEEPOUT) and 15 nm corner to corner
#     (M2.5, LEF58_CORNERSPACING); jogs of the same net on the same track may
#     overlap; an M3 extension closes gaps below the 20 nm M3 tip-to-tip
#     spacing (M3.4) to the next stripe segment;
#   * when no stripe and M2 track is clear the script stops instead of
#     drawing a violation or a short.
#
# After each successful repair the PSM markers of the checks are deleted, so
# later check_power_grid calls (LibreLane's own one after pdngen) report only
# real problems instead of the stale pre-repair markers.
#
# Environment knobs (all optional):
#   GT2N_TAP_M3_NETS    supply nets to repair       (default "VDD VSS")
#   GT2N_TAP_M3_SIDES   preferred side per net      (default "left right")

set ::gt2n_tap_out_dir [file join $::env(REPORTS_DIR) tap_pg_to_m3]
file mkdir $::gt2n_tap_out_dir

# Tap cells of every GT2N library (WELLTAP_CELL and ENDCAP_CELL).
set ::gt2n_tap_master_pattern gt2_6t_tapfspdn_*
# M2 rules (um) beyond the tech LEF SPACING: M2.4 and M2.5.
set ::gt2n_tap_m2_tip_um 0.017
set ::gt2n_tap_m2_corner_um 0.015
# M3.4: tip-to-tip spacing of M3 on a track (um).
set ::gt2n_tap_m3_tip_um 0.020
# Stripe candidates tried per side.
set ::gt2n_tap_max_stripes 4

proc gt2n_tap_dbu {} {
  return [[ord::get_db_tech] getDbUnitsPerMicron]
}

proc gt2n_tap_um_to_dbu {v} {
  return [expr {int(round(double($v) * [gt2n_tap_dbu]))}]
}

proc gt2n_tap_um {v} {
  return [format %.4f [expr {double($v) / [gt2n_tap_dbu]}]]
}

# Merge {lo hi} intervals that overlap or touch.
proc gt2n_tap_merge {intervals} {
  set out {}
  foreach iv [lsort -integer -index 0 $intervals] {
    lassign $iv lo hi
    if {[llength $out] && $lo <= [lindex $out end 1]} {
      lset out end 1 [expr {max([lindex $out end 1], $hi)}]
    } else {
      lappend out [list $lo $hi]
    }
  }
  return $out
}

# Stop when the design has no tap cell or a BPR rail segment touches none.
proc gt2n_tap_check_rails {} {
  set block [ord::get_db_block]
  set taps [dict create]
  set ntaps 0
  foreach inst [$block getInsts] {
    if {![string match $::gt2n_tap_master_pattern [[$inst getMaster] getName]]} { continue }
    if {![$inst isPlaced]} { continue }
    set b [$inst getBBox]
    foreach y [list [$b yMin] [$b yMax]] {
      dict lappend taps $y [list [$b xMin] [$b xMax]]
    }
    incr ntaps
  }
  if {$ntaps == 0} {
    error "GT2N_TAP_M3: no placed $::gt2n_tap_master_pattern cell, the buried power rails of every cell would float (set WELLTAP_CELL and ENDCAP_CELL to the tapfspdn cell)"
  }
  set rails [dict create]
  foreach row [$block getRows] {
    set b [$row getBBox]
    foreach y [list [$b yMin] [$b yMax]] {
      dict lappend rails $y [list [$b xMin] [$b xMax]]
    }
  }
  set nseg 0
  set floating {}
  dict for {y intervals} $rails {
    foreach seg [gt2n_tap_merge $intervals] {
      incr nseg
      lassign $seg lo hi
      set tapped 0
      if {[dict exists $taps $y]} {
        foreach t [dict get $taps $y] {
          if {[lindex $t 0] < $hi && [lindex $t 1] > $lo} { set tapped 1; break }
        }
      }
      if {!$tapped} { lappend floating [list $y $lo $hi] }
    }
  }
  foreach f [lrange $floating 0 4] {
    lassign $f y lo hi
    puts "GT2N_TAP_M3: no tap cell on the BPR rail at y=[gt2n_tap_um $y], x=[gt2n_tap_um $lo]..[gt2n_tap_um $hi] um"
  }
  if {[llength $floating]} {
    error "GT2N_TAP_M3: [llength $floating] of $nseg BPR rail segments have no tap cell (set ENDCAP_CELL to the tapfspdn cell or lower FP_TAPCELL_DIST)"
  }
  puts "GT2N_TAP_M3: $ntaps tap cells, all $nseg BPR rail segments tapped"
}

# Areas the hookup must not touch, as {layer xlo ylo xhi yhi} ("*" = every
# layer): PDN obstructions, and placed block macros plus the PDN macro halo.
proc gt2n_tap_keepouts {} {
  set block [ord::get_db_block]
  set out {}
  foreach obs [$block getObstructions] {
    set b [$obs getBBox]
    set layer [$b getTechLayer]
    if {$layer == "NULL"} { continue }
    lappend out [list [$layer getName] [$b xMin] [$b yMin] [$b xMax] [$b yMax]]
  }
  if {[info exists ::gt2n_pdn_macro_halo]} {
    lassign $::gt2n_pdn_macro_halo hx hy
  } else {
    set hx 10
    set hy 10
    if {[info exists ::env(PDN_HORIZONTAL_HALO)]} { set hx $::env(PDN_HORIZONTAL_HALO) }
    if {[info exists ::env(PDN_VERTICAL_HALO)]} { set hy $::env(PDN_VERTICAL_HALO) }
  }
  set hx [gt2n_tap_um_to_dbu $hx]
  set hy [gt2n_tap_um_to_dbu $hy]
  foreach inst [$block getInsts] {
    if {![[$inst getMaster] isBlock] || ![$inst isPlaced]} { continue }
    set b [$inst getBBox]
    lappend out [list * [expr {[$b xMin] - $hx}] [expr {[$b yMin] - $hy}] \
                     [expr {[$b xMax] + $hx}] [expr {[$b yMax] + $hy}]]
  }
  return $out
}

proc gt2n_tap_free {layer xlo ylo xhi yhi} {
  foreach k $::gt2n_tap_keepouts {
    lassign $k klayer kxlo kylo kxhi kyhi
    if {$klayer ne "*" && $klayer ne $layer} { continue }
    if {$xlo < $kxhi && $xhi > $kxlo && $ylo < $kyhi && $yhi > $kylo} { return 0 }
  }
  return 1
}

# Shapes of a tech via, as {layer xlo ylo xhi yhi} around its origin.
proc gt2n_tap_via_boxes {via} {
  set out {}
  foreach box [$via getBoxes] {
    lappend out [list [[$box getTechLayer] getName] [$box xMin] [$box yMin] [$box xMax] [$box yMax]]
  }
  return $out
}

proc gt2n_tap_via_box {boxes layer} {
  foreach b $boxes {
    if {[lindex $b 0] eq $layer} { return [lrange $b 1 end] }
  }
  error "GT2N_TAP_M3: via has no $layer shape"
}

proc gt2n_tap_via_free {boxes x y} {
  foreach b $boxes {
    lassign $b layer xlo ylo xhi yhi
    if {![gt2n_tap_free $layer [expr {$x + $xlo}] [expr {$y + $ylo}] [expr {$x + $xhi}] [expr {$y + $yhi}]]} {
      return 0
    }
  }
  return 1
}

# M2 metal of the supply nets, binned by y: global stripes and the jogs drawn
# so far, as {net xlo ylo xhi yhi}.
array unset ::gt2n_tap_m2_bins
set ::gt2n_tap_m2_bin 96

proc gt2n_tap_m2_add {net xlo ylo xhi yhi} {
  for {set i [expr {$ylo / $::gt2n_tap_m2_bin}]} {$i <= $yhi / $::gt2n_tap_m2_bin} {incr i} {
    lappend ::gt2n_tap_m2_bins($i) [list $net $xlo $ylo $xhi $yhi]
  }
}

# True when new M2 metal of net keeps the M2 rules to all registered M2.
proc gt2n_tap_m2_clear {net xlo ylo xhi yhi} {
  set reach $::gt2n_tap_m2_rule(reach)
  set seen [dict create]
  for {set i [expr {($ylo - $reach) / $::gt2n_tap_m2_bin}]} \
      {$i <= ($yhi + $reach) / $::gt2n_tap_m2_bin} {incr i} {
    if {![info exists ::gt2n_tap_m2_bins($i)]} { continue }
    foreach s $::gt2n_tap_m2_bins($i) {
      if {[dict exists $seen $s]} { continue }
      dict set seen $s 1
      lassign $s onet oxlo oylo oxhi oyhi
      set dx [expr {max($oxlo - $xhi, $xlo - $oxhi)}]
      set dy [expr {max($oylo - $yhi, $ylo - $oyhi)}]
      if {$dx <= 0 && $dy <= 0} {
        # Touching or overlapping: only metal of the same net on the same
        # track merges into one rectangle.
        if {$onet eq $net && $oylo == $ylo && $oyhi == $yhi} { continue }
        return 0
      } elseif {$dy <= 0} {
        if {$dx < $::gt2n_tap_m2_rule(tip)} { return 0 }
      } elseif {$dx <= 0} {
        if {$dy < $::gt2n_tap_m2_rule(space)} { return 0 }
      } elseif {$dx * $dx + $dy * $dy < $::gt2n_tap_m2_rule(corner) ** 2} {
        return 0
      }
    }
  }
  return 1
}

# Vertical stripes of a net on a layer: dict x -> {halfwidth {lo hi} ...}
# with the segments of each track merged.
proc gt2n_tap_stripe_segments {net_name layer_name} {
  set block [ord::get_db_block]
  set net [$block findNet $net_name]
  set segs [dict create]
  set hws [dict create]
  if {$net == "NULL"} { return $segs }
  foreach swire [$net getSWires] {
    foreach box [$swire getWires] {
      if {[$box isVia]} { continue }
      if {[[$box getTechLayer] getName] ne $layer_name} { continue }
      set w [expr {[$box xMax] - [$box xMin]}]
      if {[$box yMax] - [$box yMin] <= $w} { continue }
      set x [expr {([$box xMin] + [$box xMax]) / 2}]
      dict lappend segs $x [list [$box yMin] [$box yMax]]
      dict set hws $x [expr {$w / 2}]
    }
  }
  set out [dict create]
  dict for {x intervals} $segs {
    dict set out $x [concat [list [dict get $hws $x]] [gt2n_tap_merge $intervals]]
  }
  return $out
}

# Stripe x positions (stripes sorted) in the order they are tried for a pin
# at cx.
proc gt2n_tap_stripe_order {cx stripes side} {
  set n $::gt2n_tap_max_stripes
  set i [lsearch -sorted -integer -bisect $stripes $cx]
  set left [lreverse [lrange $stripes [expr {max(0, $i - $n + 1)}] $i]]
  set right [lrange $stripes [expr {$i + 1}] [expr {$i + $n}]]
  if {$side eq "left"} {
    set first $left
    set second $right
  } elseif {$side eq "right"} {
    set first $right
    set second $left
  } else {
    set out {}
    foreach s [concat $left $right] { lappend out [list $s [expr {abs($s - $cx)}]] }
    set res {}
    foreach p [lsort -integer -index 1 $out] { lappend res [lindex $p 0] }
    return $res
  }
  set out {}
  for {set k 0} {$k < $n} {incr k} {
    if {$k < [llength $first]} { lappend out [lindex $first $k] }
    if {$k < [llength $second]} { lappend out [lindex $second $k] }
  }
  return $out
}

# M3 shapes needed to reach a V2 at (x, y) from the stripe segments segs
# (halfwidth first): {} when a segment covers the V2 pad, else the extension
# boxes; returns "blocked" when the extension is not possible.
proc gt2n_tap_m3_extension {x segs ylo yhi} {
  set hw [lindex $segs 0]
  set best ""
  foreach seg [lrange $segs 1 end] {
    lassign $seg lo hi
    if {$lo <= $ylo && $hi >= $yhi} { return {} }
    set d [expr {max($lo - $yhi, $ylo - $hi)}]
    if {$best eq "" || $d < [lindex $best 0]} { set best [list $d $lo $hi] }
  }
  lassign $best d lo hi
  if {$hi <= $ylo} {
    set elo $hi
    set ehi $yhi
  } elseif {$lo >= $yhi} {
    set elo $ylo
    set ehi $lo
  } else {
    # The segment covers part of the V2 pad.
    set elo $ylo
    set ehi $yhi
  }
  # Close a gap to the next segment that would be below the M3 tip-to-tip
  # spacing.
  foreach seg [lrange $segs 1 end] {
    lassign $seg slo shi
    if {$slo > $ehi && $slo - $ehi < $::gt2n_tap_m3_tip} { set ehi $slo }
    if {$shi < $elo && $elo - $shi < $::gt2n_tap_m3_tip} { set elo $shi }
  }
  if {![gt2n_tap_free M3 [expr {$x - $hw}] $elo [expr {$x + $hw}] $ehi]} { return blocked }
  return [list [list [expr {$x - $hw}] $elo [expr {$x + $hw}] $ehi]]
}

proc gt2n_tap_clear_psm_markers {} {
  set category [[ord::get_db_block] findMarkerCategory PSM]
  if {$category != "NULL"} { odb::dbMarkerCategory_destroy $category }
}

proc gt2n_tap_repair_net {net_name side} {
  set block [ord::get_db_block]
  set tech [ord::get_db_tech]
  set net [$block findNet $net_name]
  if {$net == "NULL"} {
    puts "GT2N_TAP_M3: net $net_name not found, skipping"
    return
  }
  set m3_segs [gt2n_tap_stripe_segments $net_name M3]
  if {![dict size $m3_segs]} {
    error "GT2N_TAP_M3: no M3 stripes found for $net_name; the PDN must have M3 stripes"
  }
  set stripes [lsort -integer [dict keys $m3_segs]]

  set m2 [$tech findLayer M2]
  set m3 [$tech findLayer M3]
  set v1 [$tech findVia V1_0]
  set v2 [$tech findVia V2_0]
  if {$m2 == "NULL" || $m3 == "NULL" || $v1 == "NULL" || $v2 == "NULL"} {
    error "GT2N_TAP_M3: cannot find M2, M3, V1_0 or V2_0 in the tech LEF"
  }
  set v1_boxes [gt2n_tap_via_boxes $v1]
  set v2_boxes [gt2n_tap_via_boxes $v2]
  lassign [gt2n_tap_via_box $v1_boxes M1] - v1_m1_ylo - v1_m1_yhi
  lassign [gt2n_tap_via_box $v1_boxes M2] v1_m2_xlo v1_m2_ylo v1_m2_xhi v1_m2_yhi
  lassign [gt2n_tap_via_box $v2_boxes M2] v2_m2_xlo v2_m2_ylo v2_m2_xhi v2_m2_yhi
  lassign [gt2n_tap_via_box $v2_boxes M3] - v2_m3_ylo - v2_m3_yhi
  set m2_half [expr {[$m2 getWidth] / 2}]

  # Jogs on the M2 routing tracks (tech LEF pitch/offset without tracks).
  set grid [$block findTrackGrid $m2]
  set track_ys {}
  if {$grid != "NULL"} { set track_ys [$grid getGridY] }
  if {[llength $track_ys] >= 2} {
    set m2_offset [lindex $track_ys 0]
    set m2_pitch [expr {[lindex $track_ys 1] - [lindex $track_ys 0]}]
  } else {
    set m2_pitch [$m2 getPitchY]
    if {$m2_pitch <= 0} { set m2_pitch [$m2 getPitch] }
    set m2_offset [$m2 getOffsetY]
    if {$m2_offset <= 0} { set m2_offset [expr {$m2_pitch / 2}] }
  }

  # Before the repair every tap pin is unconnected: keep the expected PSM
  # warnings and error out of the log (they are in the report file).
  set before [file join $::gt2n_tap_out_dir ${net_name}.before.rpt]
  file delete -force $before
  foreach id {38 39 69} { suppress_message PSM $id }
  catch {check_power_grid -net $net_name -error_file $before} msg
  foreach id {38 39 69} { unsuppress_message PSM $id }
  puts "GT2N_TAP_M3: $net_name before repair: $msg"

  set added 0
  set moved 0
  set extended 0
  set far 0
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
      set n [expr {int(floor(double($cy - $m2_offset) / $m2_pitch + 0.5))}]
      set m2_y [expr {$m2_offset + $n * $m2_pitch}]

      # Try the stripes in order of preference and, for each, the M2 tracks
      # along the pin from its centre outwards.
      set chosen ""
      set order [gt2n_tap_stripe_order $cx $stripes $side]
      foreach sx $order {
        foreach step {0 -1 1 -2 2 -3 3 -4 4} {
          set cand [expr {$m2_y + $step * $m2_pitch}]
          if {$cand + $v1_m1_ylo < $y1 || $cand + $v1_m1_yhi > $y2} { continue }
          set xlo [expr {min($cx + $v1_m2_xlo, $sx + $v2_m2_xlo)}]
          set xhi [expr {max($cx + $v1_m2_xhi, $sx + $v2_m2_xhi)}]
          set ylo [expr {$cand + min(-$m2_half, $v1_m2_ylo, $v2_m2_ylo)}]
          set yhi [expr {$cand + max($m2_half, $v1_m2_yhi, $v2_m2_yhi)}]
          if {![gt2n_tap_free M2 $xlo $ylo $xhi $yhi]} { continue }
          if {![gt2n_tap_via_free $v1_boxes $cx $cand]} { continue }
          if {![gt2n_tap_via_free $v2_boxes $sx $cand]} { continue }
          if {![gt2n_tap_m2_clear $net_name $xlo $ylo $xhi $yhi]} { continue }
          set ext [gt2n_tap_m3_extension $sx [dict get $m3_segs $sx] \
                       [expr {$cand + $v2_m3_ylo}] [expr {$cand + $v2_m3_yhi}]]
          if {$ext eq "blocked"} { continue }
          set chosen [list $sx $cand $xlo $ylo $xhi $yhi $ext]
          break
        }
        if {$chosen ne ""} { break }
      }
      if {$chosen eq ""} {
        if {![gt2n_tap_free * $cx $cy [expr {$cx + 1}] [expr {$cy + 1}]]} {
          error "GT2N_TAP_M3: the $net_name tap pin at ([gt2n_tap_um $cx], [gt2n_tap_um $cy]) um lies inside a macro plus its PDN halo; keep PDN_HORIZONTAL_HALO/PDN_VERTICAL_HALO no larger than FP_MACRO_HORIZONTAL_HALO/FP_MACRO_VERTICAL_HALO (the row halo)"
        }
        error "GT2N_TAP_M3: no clear M2 jog from the $net_name tap pin at ([gt2n_tap_um $cx], [gt2n_tap_um $cy]) um to any of [llength $order] M3 stripes (blocked by M2 stripes, other jogs, PDN obstructions or a macro halo)"
      }
      lassign $chosen sx cand xlo ylo xhi yhi ext
      if {$cand != $m2_y} { incr moved }
      if {$sx != [lindex $order 0]} { incr far }
      gt2n_tap_m2_add $net_name $xlo $ylo $xhi $yhi
      set lx [expr {min($cx, $sx)}]
      set ux [expr {max($cx, $sx)}]
      if {$ux > $lx} {
        odb::dbSBox_create $swire $m2 $lx [expr {$cand - $m2_half}] $ux [expr {$cand + $m2_half}] "STRIPE"
      }
      odb::dbSBox_create $swire $v1 $cx $cand "STRIPE"
      odb::dbSBox_create $swire $v2 $sx $cand "STRIPE"
      if {[llength $ext]} {
        set segs [dict get $m3_segs $sx]
        set intervals [lrange $segs 1 end]
        foreach box $ext {
          lassign $box exlo eylo exhi eyhi
          odb::dbSBox_create $swire $m3 $exlo $eylo $exhi $eyhi "STRIPE"
          lappend intervals [list $eylo $eyhi]
        }
        dict set m3_segs $sx [concat [list [lindex $segs 0]] [gt2n_tap_merge $intervals]]
        incr extended
      }
      incr added
    }
    close $fh
  }

  # The markers of the check before the repair would otherwise be reported
  # again by every later check_power_grid, connected or not.
  gt2n_tap_clear_psm_markers
  set after [file join $::gt2n_tap_out_dir ${net_name}.after.rpt]
  file delete -force $after
  set status [catch {check_power_grid -net $net_name -error_file $after} msg]
  puts "GT2N_TAP_M3: $net_name added=$added jogs (moved to another M2 track: $moved, to another stripe: $far, M3 stripes extended: $extended), after repair: $msg"
  if {$status != 0} {
    set insts {}
    if {[file exists $after]} {
      set fh [open $after r]
      set insts [lsort -unique [regexp -all -inline {inst:[^\s]+} [read $fh]]]
      close $fh
    }
    set some [join [lrange $insts 0 4] ", "]
    error "GT2N_TAP_M3: power grid of $net_name still disconnected ([llength $insts] unconnected instances: $some), see $after"
  }
  gt2n_tap_clear_psm_markers
}

set gt2n_tap_nets {VDD VSS}
if {[info exists ::env(GT2N_TAP_M3_NETS)] && $::env(GT2N_TAP_M3_NETS) ne ""} {
  set gt2n_tap_nets $::env(GT2N_TAP_M3_NETS)
}
set gt2n_tap_sides {left right}
if {[info exists ::env(GT2N_TAP_M3_SIDES)] && $::env(GT2N_TAP_M3_SIDES) ne ""} {
  set gt2n_tap_sides $::env(GT2N_TAP_M3_SIDES)
}

gt2n_tap_check_rails

set ::gt2n_tap_keepouts [gt2n_tap_keepouts]
set gt2n_m2 [[ord::get_db_tech] findLayer M2]
array set ::gt2n_tap_m2_rule [list \
  space  [$gt2n_m2 getSpacing] \
  tip    [gt2n_tap_um_to_dbu $::gt2n_tap_m2_tip_um] \
  corner [gt2n_tap_um_to_dbu $::gt2n_tap_m2_corner_um]]
set ::gt2n_tap_m2_rule(reach) [expr {max($::gt2n_tap_m2_rule(space), $::gt2n_tap_m2_rule(tip), $::gt2n_tap_m2_rule(corner))}]
set ::gt2n_tap_m3_tip [gt2n_tap_um_to_dbu $::gt2n_tap_m3_tip_um]

# The M2 of every supply net (global stripes) constrains the jogs.
foreach net $gt2n_tap_nets {
  set gt2n_net [[ord::get_db_block] findNet $net]
  if {$gt2n_net == "NULL"} { continue }
  foreach swire [$gt2n_net getSWires] {
    foreach box [$swire getWires] {
      if {[$box isVia] || [[$box getTechLayer] getName] ne "M2"} { continue }
      gt2n_tap_m2_add $net [$box xMin] [$box yMin] [$box xMax] [$box yMax]
    }
  }
}

foreach net $gt2n_tap_nets side $gt2n_tap_sides {
  if {$net eq ""} { continue }
  if {$side eq ""} { set side nearest }
  gt2n_tap_repair_net $net $side
}
