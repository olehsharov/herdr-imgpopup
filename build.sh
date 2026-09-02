#!/bin/sh
# Herdr runs this once at install time. A plugin-local venv keeps Pillow off the
# user's system python.
set -e
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet "Pillow>=9.0"
