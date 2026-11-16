##############################################################################
#
# File: Makefile
#
# Purpose:
#       Build automation for invert-film-scans
#
# Copyright notice and license:
#       See LICENSE.md in this directory.
#
# Author:
#       Terry Moore
#
# Notes:
#       Requires GNU Make. Works on macOS (as gmake), Linux, and Windows
#       (via git bash).
#
##############################################################################

# Project-specific prefix for all variables
INVERT_FILM_SCANS_UV := uv

.PHONY: help build test lint clean distclean

##############################################################################
#
# help: Display available make targets
#
##############################################################################
help:
	@printf "%s\n" \
		"Available targets:" \
		"" \
		"* make help      -- prints this message" \
		"* make build     -- builds the package using uv" \
		"* make test      -- runs pytest" \
		"* make lint      -- runs ruff on source and tests" \
		"* make clean     -- removes build artifacts" \
		"* make distclean -- clean, plus removes dist/"

##############################################################################
#
# build: Build the package using uv
#
##############################################################################
build:
	$(INVERT_FILM_SCANS_UV) build

##############################################################################
#
# test: Run the pytest test suite
#
##############################################################################
test:
	$(INVERT_FILM_SCANS_UV) run pytest

##############################################################################
#
# lint: Run ruff on source and test files
#
##############################################################################
lint:
	$(INVERT_FILM_SCANS_UV) run ruff check src tests

##############################################################################
#
# clean: Remove build artifacts
#
##############################################################################
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

##############################################################################
#
# distclean: Clean, plus remove the dist directory
#
##############################################################################
distclean: clean
	rm -rf dist/

#### end of file ####
