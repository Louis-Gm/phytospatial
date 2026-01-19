#!/bin/bash
# scripts/format_check.sh

echo "Checking code style with Black..."
black --check .
BLACK_STATUS=$?

echo "Checking imports with Ruff..."
ruff check .
RUFF_STATUS=$?

if [ $BLACK_STATUS -eq 0 ] && [ $RUFF_STATUS -eq 0 ]; then
    echo "Code style is perfect!"
    exit 0
else
    echo "Style issues detected. Run 'black .' or 'ruff check --fix .' to resolve."
    exit 1
fi