# SPDX-License-Identifier: BSD-3-Clause
#
# GT2N LibreLane macro example. Run `make help` for the targets. LibreLane and
# its tools come from the Nix shell of this directory (`nix-shell`).

MAKEFILE_DIR := $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))

# The GT2N PDK lives in <repository>/gt2n
PDK_ROOT ?= $(realpath $(MAKEFILE_DIR)/../..)
PDK ?= gt2n
SCL ?= gt2_6t_w31_svt

DESIGN = gt2n_demo
SCL_DIR = $(PDK_ROOT)/$(PDK)/libs.ref/$(SCL)
LVS_DECK = $(PDK_ROOT)/$(PDK)/libs.tech/klayout/tech/lvs/gt2n.lylvs
LVS_DIR = $(MAKEFILE_DIR)/final/lvs

LIBRELANE = librelane librelane/config.yaml --pdk $(PDK) --pdk-root $(PDK_ROOT) --manual-pdk --scl $(SCL)

.DEFAULT_GOAL := help

help: ## Show this help message
	@echo 'Usage: make [target] [SCL=gt2_6t_<w13|w31>_<elvt|ulvt|lvt|svt|hvt>]'
	@echo ''
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'
.PHONY: help

librelane: ## Run the LibreLane Classic flow and copy the views to final/
	$(LIBRELANE) --save-views-to final/
.PHONY: librelane

librelane-nodrc: ## Run LibreLane without the DRC steps
	$(LIBRELANE) --save-views-to final/ --skip KLayout.DRC --skip Magic.DRC
.PHONY: librelane-nodrc

librelane-openroad: ## Open the last run in the OpenROAD GUI
	$(LIBRELANE) --last-run --flow OpenInOpenROAD
.PHONY: librelane-openroad

librelane-klayout: ## Open the last run in KLayout
	$(LIBRELANE) --last-run --flow OpenInKLayout
.PHONY: librelane-klayout

lvs: ## Transistor-level LVS of final/ with the GT2N KLayout deck
	mkdir -p $(LVS_DIR)
	ODB=$(MAKEFILE_DIR)/final/odb/$(DESIGN).odb CELL_CDL=$(SCL_DIR)/cdl/$(SCL).cdl OUT=$(LVS_DIR)/$(DESIGN).cdl \
	  openroad -exit $(MAKEFILE_DIR)/scripts/write_cdl.tcl
	cat $(LVS_DIR)/$(DESIGN).cdl $(SCL_DIR)/cdl/$(SCL).cdl > $(LVS_DIR)/$(DESIGN).schematic.cdl
	klayout -b -r $(LVS_DECK) -rd lvs_mode=transistor \
	  -rd input=$(MAKEFILE_DIR)/final/gds/$(DESIGN).gds -rd topcell=$(DESIGN) \
	  -rd schematic=$(LVS_DIR)/$(DESIGN).schematic.cdl \
	  -rd report=$(LVS_DIR)/$(DESIGN).lvsdb -rd target_netlist=$(LVS_DIR)/$(DESIGN).extracted.cir \
	  | tee $(LVS_DIR)/$(DESIGN).lvs.log
	grep -q "Congratulations! Netlists match" $(LVS_DIR)/$(DESIGN).lvs.log
.PHONY: lvs

sim: ## RTL simulation with cocotb + Icarus Verilog
	cd cocotb; PDK_ROOT=$(PDK_ROOT) PDK=$(PDK) SCL=$(SCL) python3 gt2n_demo_tb.py
.PHONY: sim

sim-gl: ## Gate-level simulation of final/nl with the GT2N cell models
	cd cocotb; GL=1 PDK_ROOT=$(PDK_ROOT) PDK=$(PDK) SCL=$(SCL) python3 gt2n_demo_tb.py
.PHONY: sim-gl

sim-view: ## View the simulation waveforms
	gtkwave cocotb/sim_build/gt2n_demo.fst
.PHONY: sim-view
