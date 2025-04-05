# Makefile for pixel-toaster

.PHONY: all install-dev lint format check build clean release-gh help

# Variables
PYTHON = python3 # Or specify path to venv python: .venv/bin/python
SRC_DIR = app
MAIN_SCRIPT = main.py
APP_NAME = toast # Desired name for the binary
DIST_DIR = dist
BUILD_DIR = build

# Default target (runs when you just type 'make')
all: help

# Install development dependencies
# It's HIGHLY recommended to use a virtual environment!
# python3 -m venv .venv
# source .venv/bin/activate
# make install-dev
install-dev:
	@echo ">>> Installing development dependencies..."
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

# Run linters and type checker
lint:
	@echo ">>> Running linters and type checker..."
	$(PYTHON) -m flake8 $(MAIN_SCRIPT) $(SRC_DIR)
	$(PYTHON) -m black --check $(MAIN_SCRIPT) $(SRC_DIR)
	$(PYTHON) -m isort --check-only $(MAIN_SCRIPT) $(SRC_DIR)
	$(PYTHON) -m mypy $(MAIN_SCRIPT) $(SRC_DIR)

# Auto-format code
format:
	@echo ">>> Formatting code..."
	$(PYTHON) -m black $(MAIN_SCRIPT) $(SRC_DIR)
	$(PYTHON) -m isort $(MAIN_SCRIPT) $(SRC_DIR)

# Run checks (lint + format check) - useful for CI
check: lint

# Build the executable binary using PyInstaller
# --onefile: Create a single executable file (can be slower to start)
# --name: Name of the output executable
# --distpath: Where to put the final executable
# --workpath: Where PyInstaller does its work
# --clean: Remove PyInstaller cache before building
# Add --add-data if you have non-code files to bundle (e.g., assets)
# Example: --add-data "path/to/asset.txt:."
build: clean
	@echo ">>> Building executable binary..."
	$(PYTHON) -m PyInstaller --name $(APP_NAME) \
	                        --onefile \
	                        --distpath $(DIST_DIR) \
	                        --workpath $(BUILD_DIR) \
	                        --clean \
	                        $(MAIN_SCRIPT)
	@echo ">>> Build complete. Executable is in $(DIST_DIR)/"

# Clean up build artifacts and caches
clean:
	@echo ">>> Cleaning up..."
	rm -rf $(DIST_DIR)/ $(BUILD_DIR)/ $(APP_NAME).spec __pycache__/ */__pycache__/ .mypy_cache

# Basic outline for creating a GitHub Release (requires GitHub CLI 'gh' installed and configured)
# This is a manual guide - full automation might need a script.
release-gh: build
	@echo ">>> Preparing GitHub Release (Manual Steps Required):"
	@echo "1. Ensure build is successful: executable is in $(DIST_DIR)/"
	@echo "2. Determine version (e.g., read from a file, use git tag)."
	@read -p "Enter version tag (e.g., v0.1.0): " VERSION; \
	 if [ -z "$$VERSION" ]; then echo "Error: Version tag cannot be empty."; exit 1; fi; \
	 echo "3. Tag the release: git tag $$VERSION" ;\
	 git tag $$VERSION ;\
	 echo "4. Push the tag: git push origin $$VERSION" ;\
	 git push origin $$VERSION ;\
	 echo "5. Create GitHub release and upload asset:" ;\
	 echo "   gh release create $$VERSION $(DIST_DIR)/$(APP_NAME) --notes \"Release notes for $$VERSION\" --title \"Pixel Toaster $$VERSION\"" ;\
	 gh release create $$VERSION $(DIST_DIR)/$(APP_NAME) --notes "Release notes for $$VERSION" --title "Pixel Toaster $$VERSION"

# Show help message
help:
	@echo "Available commands:"
	@echo "  install-dev   Install development dependencies (use a virtual env!)"
	@echo "  lint          Run linters and type checker"
	@echo "  format        Auto-format code using black and isort"
	@echo "  check         Run lint and format checks (useful for CI)"
	@echo "  build         Build the executable binary in ./dist/"
	@echo "  clean         Remove build artifacts and caches"
	@echo "  release-gh    Build, tag, push tag, and create GitHub release with assets (requires 'gh' CLI)"
	@echo "  help          Show this help message"