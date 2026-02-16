#!/bin/bash
set -euo pipefail

# DESCRIPTION
# Generate GIF recordings from VHS tape files for documentation.

# USAGE
# ./bin/generate_gifs.sh              # Generate all GIFs
# ./bin/generate_gifs.sh oneshot      # Generate a specific GIF

TAPES_DIR="docs/static"

if ! command -v vhs &> /dev/null; then
    echo "Error: VHS is not installed. See https://github.com/charmbracelet/vhs"
    exit 1
fi

if [ $# -eq 0 ]; then
    for tape in "$TAPES_DIR"/*.tape; do
        echo "Recording: $tape"
        vhs "$tape"
    done
else
    tape="$TAPES_DIR/$1.tape"
    if [ ! -f "$tape" ]; then
        echo "Error: $tape not found"
        exit 1
    fi
    echo "Recording: $tape"
    vhs "$tape"
fi
