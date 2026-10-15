# SPDX-License-Identifier: BSD-3-Clause
#
# GT2N open-source PDK: generation and regression targets.
#
#   make help
#
# Generated collateral is committed; `make generate` refreshes it from the
# legacy GT2N files at the repository root and `make check-generated` fails
# when the committed copies are stale.

PYTHON ?= python3
YOSYS ?= yosys
KLAYOUT ?= klayout
IVERILOG ?= iverilog
VVP ?= vvp

PDK_DIR := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
SCRIPTS := $(PDK_DIR)/scripts
QA := $(PDK_DIR)/libs.qa
RUN_DIR ?= $(QA)/run
LIBS := $(notdir $(wildcard $(PDK_DIR)/libs.ref/gt2_6t_*))

.DEFAULT_GOAL := help

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-22s %s\n", $$1, $$2}'
.PHONY: help

#-----------------------------------------------------------------------------
# Generation
#-----------------------------------------------------------------------------
libs-ref: ## Copy LEF/Liberty/GDS/CDL from the legacy tree and derive Verilog/SPICE/docs
	$(PYTHON) $(SCRIPTS)/sync_libs_ref.py
	$(PYTHON) $(SCRIPTS)/gen_verilog.py
	$(PYTHON) $(SCRIPTS)/gen_spice.py
	$(PYTHON) $(SCRIPTS)/gen_doc.py
.PHONY: libs-ref

libs-tech: ## Regenerate the LibreLane and Magic technology files
	$(PYTHON) $(SCRIPTS)/gen_librelane.py
	$(PYTHON) $(SCRIPTS)/gen_magic_tech.py
.PHONY: libs-tech

generate: libs-ref libs-tech ## Regenerate everything
.PHONY: generate

check-generated: ## Fail if any generated file is out of date
	$(PYTHON) $(SCRIPTS)/sync_libs_ref.py --check
	$(PYTHON) $(SCRIPTS)/gen_verilog.py --check
	$(PYTHON) $(SCRIPTS)/gen_spice.py --check
	$(PYTHON) $(SCRIPTS)/gen_doc.py --check
	$(PYTHON) $(SCRIPTS)/gen_librelane.py --check
	$(PYTHON) $(SCRIPTS)/gen_magic_tech.py --check
.PHONY: check-generated

#-----------------------------------------------------------------------------
# Regression (libs.qa)
#-----------------------------------------------------------------------------
test-views: ## Cell/pin consistency of lib, lef, gds, cdl, spice, verilog
	$(PYTHON) $(QA)/stdcells/check_views.py
.PHONY: test-views

test-verilog: ## Yosys SAT equivalence of the Verilog models vs Liberty
	$(PYTHON) $(QA)/stdcells/check_verilog.py
.PHONY: test-verilog

test-dff: ## Icarus testbench of every flip-flop model (UDP and GT2N_NO_UDP)
	@mkdir -p $(RUN_DIR)
	@set -e; for lib in $(LIBS); do for x in x1 x2 x4; do for def in "" -DGT2N_NO_UDP; do \
	  cell=gt2_6t_dffasync_$${x}_$${lib#gt2_6t_}; \
	  $(IVERILOG) -g2005 $$def -DCELL=$$cell -o $(RUN_DIR)/tb_dff.vvp $(QA)/stdcells/tb_dffasync.v \
	    $(PDK_DIR)/libs.ref/$$lib/verilog/$$lib.v; \
	  $(VVP) -n $(RUN_DIR)/tb_dff.vvp | grep -q "^PASS" || { echo "FAIL $$cell $$def"; exit 1; }; \
	  echo "PASS $$cell $$def"; done; done; done
.PHONY: test-dff

test-drc: ## KLayout DRC (full mode) of every standard-cell library
	$(PYTHON) $(QA)/stdcells/run_drc.py --workdir $(RUN_DIR)/drc
.PHONY: test-drc

test-drc-rules: ## KLayout DRC deck against known-bad/known-good rule fixtures
	$(PYTHON) $(QA)/drc/run_drc_rules.py --workdir $(RUN_DIR)/drc_rules
.PHONY: test-drc-rules

test-lvs: ## KLayout transistor-level LVS of every standard cell
	$(PYTHON) $(QA)/stdcells/run_lvs.py --workdir $(RUN_DIR)/lvs
.PHONY: test-lvs

test-lvs-cases: ## Positive and negative LVS cases built from libs.ref cells
	$(PYTHON) $(QA)/lvs/run_lvs_tests.py --workdir $(RUN_DIR)/lvs_tests
.PHONY: test-lvs-cases

test-magic: ## GDS -> Magic -> GDS round trip of every library, Magic connectivity and abstract-LEF checks
	$(PYTHON) $(QA)/magic/run_roundtrip.py --workdir $(RUN_DIR)/magic
	$(PYTHON) $(QA)/magic/run_connect.py --workdir $(RUN_DIR)/magic-connect
.PHONY: test-magic

test-librelane-config: ## Load the LibreLane configuration of every library; RC units seen by OpenROAD
	$(PYTHON) $(QA)/librelane/check_config.py
	$(PYTHON) $(QA)/librelane/check_rc_units.py
.PHONY: test-librelane-config

test-fast: check-generated test-views test-verilog test-dff test-drc-rules ## Quick checks
.PHONY: test-fast

test: test-fast test-drc test-lvs test-lvs-cases test-magic test-librelane-config ## All regressions
.PHONY: test

clean: ## Remove regression outputs
	rm -rf $(RUN_DIR)
.PHONY: clean
