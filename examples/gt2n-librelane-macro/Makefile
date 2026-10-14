# SPDX-License-Identifier: BSD-3-Clause
#
# GT2N LibreLane macro example. Run `make help` for the targets. LibreLane and
# its tools come from the Nix shell of this directory (`nix-shell`).

MAKEFILE_DIR := $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))

# The GT2N PDK lives in <repository>/gt2n
PDK_ROOT ?= $(realpath $(MAKEFILE_DIR)/../..)
PDK ?= gt2n
SCL ?= gt2_6t_w31_svt

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

sim: ## RTL simulation with cocotb + Icarus Verilog
	cd cocotb; PDK_ROOT=$(PDK_ROOT) PDK=$(PDK) SCL=$(SCL) python3 gt2n_demo_tb.py
.PHONY: sim

sim-gl: ## Gate-level simulation of final/nl with the GT2N cell models
	cd cocotb; GL=1 PDK_ROOT=$(PDK_ROOT) PDK=$(PDK) SCL=$(SCL) python3 gt2n_demo_tb.py
.PHONY: sim-gl

sim-view: ## View the simulation waveforms
	gtkwave cocotb/sim_build/gt2n_demo.fst
.PHONY: sim-view
