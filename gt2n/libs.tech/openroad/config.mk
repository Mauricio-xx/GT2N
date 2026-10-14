# SPDX-License-Identifier: BSD-3-Clause
#
# GT2N platform for OpenROAD-flow-scripts (ORFS).
#
# This directory is a self-contained ORFS platform. Point a design at it with
#
#     export PLATFORM     = gt2n
#     export PLATFORM_DIR = $(PDK_ROOT)/gt2n/libs.tech/openroad
#
# (or symlink it as flow/platforms/gt2n inside an ORFS checkout). Library
# collateral is taken from ../../libs.ref, KLayout collateral from
# ../klayout/tech.
#
# Library selection (override in the design config.mk, before or after the
# platform is included):
#   GT2N_WIDTH      nanosheet width flavour: w13 | w31                (w31)
#   GT2N_VT         main threshold voltage: elvt|ulvt|lvt|svt|hvt    (svt)
#   GT2N_EXTRA_VTS  extra VT libraries for multi-VT optimisation      ()
#   GT2N_CORNER     Liberty corner directory name                     (tt)
#   GT2N_PDN        fspdn  : frontside M2/M3.. mesh + tap-to-M3 hookup (default)
#                   bspdn  : backside-PDN proxy (router view without PG,
#                            backside grid added after GDS stream-out with
#                            scripts/add_bspdn_signoff_grid.rb)

export PLATFORM ?= gt2n
export PROCESS = 2

export GT2N_PDK_DIR := $(abspath $(PLATFORM_DIR)/../..)
export GT2N_LIBS_REF := $(GT2N_PDK_DIR)/libs.ref
export GT2N_KLAYOUT_TECH := $(GT2N_PDK_DIR)/libs.tech/klayout/tech

export GT2N_WIDTH ?= w31
export GT2N_VT ?= svt
export GT2N_EXTRA_VTS ?=
export GT2N_CORNER ?= tt
export GT2N_PDN ?= fspdn

GT2N_FLAVOR = $(GT2N_WIDTH)_$(GT2N_VT)
GT2N_LIB = gt2_6t_$(GT2N_FLAVOR)
GT2N_EXTRA_LIBS = $(foreach vt,$(GT2N_EXTRA_VTS),gt2_6t_$(GT2N_WIDTH)_$(vt))
GT2N_ALL_LIBS = $(GT2N_LIB) $(GT2N_EXTRA_LIBS)

#-----------------------------------------------------------------------------
# Tech / libraries
#-----------------------------------------------------------------------------
# Both PDN styles route on the frontside router view of the stack, where BPR
# is a MASTERSLICE layer and the backside layers are absent. The full
# front+backside stack is libs.ref/<lib>/lef/gt2_tech.lef.
export TECH_LEF ?= $(GT2N_LIBS_REF)/$(GT2N_LIB)/lef/gt2_fspdn_tech.lef
export SC_LEF ?= $(GT2N_LIBS_REF)/$(GT2N_LIB)/lef/$(GT2N_LIB).lef
export ADDITIONAL_LEFS += $(foreach l,$(GT2N_EXTRA_LIBS),$(GT2N_LIBS_REF)/$(l)/lef/$(l).lef)
export LIB_FILES ?= $(foreach l,$(GT2N_ALL_LIBS),$(wildcard $(GT2N_LIBS_REF)/$(l)/lib/$(l)_$(GT2N_CORNER)_*.lib))
export GDS_FILES ?= $(foreach l,$(GT2N_ALL_LIBS),$(GT2N_LIBS_REF)/$(l)/gds/$(l).gds)
export CDL_FILE ?= $(foreach l,$(GT2N_ALL_LIBS),$(GT2N_LIBS_REF)/$(l)/cdl/$(l).cdl)

# Physical-only cells are never mapped by synthesis/resizing.
export DONT_USE_CELLS += gt2_6t_decapcc_* gt2_6t_tap* gt2_6t_filler_*

export FILL_CELLS ?= gt2_6t_filler_$(GT2N_FLAVOR)

#-----------------------------------------------------------------------------
# Yosys
#-----------------------------------------------------------------------------
export TIEHI_CELL_AND_PORT ?= gt2_6t_tiehigh_$(GT2N_FLAVOR) Y
export TIELO_CELL_AND_PORT ?= gt2_6t_tielow_$(GT2N_FLAVOR) Y
export MIN_BUF_CELL_AND_PORTS ?= gt2_6t_buf_x1_$(GT2N_FLAVOR) A Y
export ABC_DRIVER_CELL ?= gt2_6t_buf_x1_$(GT2N_FLAVOR)
# Liberty capacitance unit is pF; ABC_LOAD_IN_FF is in fF.
export ABC_LOAD_IN_FF ?= 5
# The libraries have no latches, clock-gating cells or adders to map.
export LATCH_MAP_FILE ?=
export CLKGATE_MAP_FILE ?=
export ADDER_MAP_FILE ?=

#-----------------------------------------------------------------------------
# Floorplan
#-----------------------------------------------------------------------------
export PLACE_SITE ?= gt2_6t
export IO_PLACER_H ?= M2
export IO_PLACER_V ?= M3
export MAKE_TRACKS ?= $(PLATFORM_DIR)/make_tracks_fspdn.tcl

export TAPCELL_TCL ?= $(PLATFORM_DIR)/tapcell.tcl
export TAPCELL_DISTANCE ?= 28

ifeq ($(GT2N_PDN),bspdn)
export TAP_CELL_NAME ?= gt2_6t_tapbspdn_$(GT2N_FLAVOR)
export PDN_TCL ?= $(PLATFORM_DIR)/pdn_bspdn_proxy.tcl
else
export TAP_CELL_NAME ?= gt2_6t_tapfspdn_$(GT2N_FLAVOR)
export PDN_TCL ?= $(GT2N_PDK_DIR)/libs.tech/librelane/gt2n_pdn_fspdn.tcl
export POST_PDN_TCL ?= $(GT2N_PDK_DIR)/libs.tech/librelane/gt2n_tap_to_m3.tcl
export PRE_IO_PLACEMENT_TCL ?= $(PLATFORM_DIR)/pre_io_avoid_pdn_stripes.tcl
endif

#-----------------------------------------------------------------------------
# Place
#-----------------------------------------------------------------------------
export PLACE_DENSITY ?= 0.58
export CELL_PAD_IN_SITES_GLOBAL_PLACEMENT ?= 1
export CELL_PAD_IN_SITES_DETAIL_PLACEMENT ?= 0

#-----------------------------------------------------------------------------
# Route
#-----------------------------------------------------------------------------
export MIN_ROUTING_LAYER ?= M1
export MIN_CLK_ROUTING_LAYER ?= M3
export MAX_ROUTING_LAYER ?= M9
export ROUTING_LAYER_ADJUSTMENT ?= 0.25
export FASTROUTE_TCL ?= $(PLATFORM_DIR)/fastroute.tcl

# setRC.tcl picks the frontside-only or full-stack RC set from TECH_LEF.
export LAYER_PARASITICS_FILE ?= $(PLATFORM_DIR)/setRC.tcl
export RCX_RULES ?= $(GT2N_PDK_DIR)/libs.tech/librelane/openrcx/gt2n_rcx_patterns.rules

#-----------------------------------------------------------------------------
# Power / IR drop
#-----------------------------------------------------------------------------
export PWR_NETS_VOLTAGES ?= VDD 0.7
export GND_NETS_VOLTAGES ?= VSS 0.0
export IR_DROP_LAYER ?= M1
export PRE_FINAL_REPORT_TCL ?= $(PLATFORM_DIR)/scripts/pre_final_report.tcl

#-----------------------------------------------------------------------------
# KLayout: GDS stream-out, DRC, LVS
#-----------------------------------------------------------------------------
export KLAYOUT_TECH_FILE ?= $(GT2N_KLAYOUT_TECH)/gt2n.lyt
export GDS_LAYER_MAP ?= $(GT2N_KLAYOUT_TECH)/gt2n.map
export KLAYOUT_DRC_FILE ?= $(GT2N_KLAYOUT_TECH)/drc/gt2n.lydrc
export KLAYOUT_LVS_FILE ?= $(GT2N_KLAYOUT_TECH)/lvs/gt2n.lylvs
export KLAYOUT_DRC_MODE ?= route
export KLAYOUT_LVS_MODE ?= abstract
export FILL_CONFIG ?= $(PLATFORM_DIR)/fill.json
