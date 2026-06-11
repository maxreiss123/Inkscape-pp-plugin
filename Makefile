# Inkscape Presentation Plugin -- build / install helpers
#
# The installable unit is src/pp. It is copied (or symlinked) into the Inkscape
# user extensions directory. Override the destination with INKSCAPE_EXT.

INKSCAPE_EXT ?= $(HOME)/.config/inkscape/extensions
PKG := src/pp
DEST := $(INKSCAPE_EXT)/pp

.PHONY: help install symlink uninstall test lint package windows-bundle clean

help:
	@echo "Targets:"
	@echo "  make install     Copy the plugin into $(INKSCAPE_EXT)"
	@echo "  make symlink     Symlink the plugin (dev workflow)"
	@echo "  make uninstall   Remove the installed/linked plugin"
	@echo "  make test        Run the pytest suite"
	@echo "  make lint        Run ruff"
	@echo "  make package         Build dist/inkscape-pp-plugin.zip"
	@echo "  make windows-bundle  Build dist/inkscape-pp-plugin-windows.zip (plugin + installers)"
	@echo "Override INKSCAPE_EXT to change the install location."

install:
	mkdir -p "$(INKSCAPE_EXT)"
	rm -rf "$(DEST)"
	cp -r "$(PKG)" "$(DEST)"
	@echo "Installed to $(DEST). Restart Inkscape and look under Extensions > Presentation."

symlink:
	mkdir -p "$(INKSCAPE_EXT)"
	rm -rf "$(DEST)"
	ln -s "$(CURDIR)/$(PKG)" "$(DEST)"
	@echo "Symlinked $(DEST) -> $(CURDIR)/$(PKG)."

uninstall:
	rm -rf "$(DEST)"
	@echo "Removed $(DEST)."

test:
	python3 -m pytest

lint:
	python3 -m ruff check src tests

package:
	mkdir -p dist
	cd src && zip -r ../dist/inkscape-pp-plugin.zip pp \
		-x '*/__pycache__/*' '*.pyc'
	@echo "Built dist/inkscape-pp-plugin.zip"

# A single download for Windows users: the plugin under src/pp plus the
# double-click installers under install/. Extract, then run install/install-windows.bat.
windows-bundle:
	mkdir -p dist
	rm -f dist/inkscape-pp-plugin-windows.zip
	zip -r dist/inkscape-pp-plugin-windows.zip src/pp install README.md LICENSE \
		-x '*/__pycache__/*' '*.pyc'
	@echo "Built dist/inkscape-pp-plugin-windows.zip"

clean:
	rm -rf dist
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
