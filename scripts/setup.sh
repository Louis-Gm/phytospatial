#!/bin/bash
# scripts/setup.sh

echo "Initializing phytospatial development environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "Created virtual environment."
fi

source .venv/bin/activate

pip install --upgrade pip
pip install -e .[analysis,dev,docs]

# ensure git hooks are installed
pre-commit install
echo "Setup complete."