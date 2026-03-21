#!/usr/bin/env bash
set -e

echo "Installing / upgrading build dependencies..."
pip install --upgrade pyinstaller rumps requests

echo ""
echo "Building OpenAIUsageTray.app..."
python -m PyInstaller \
    --windowed \
    --name OpenAIUsageTray \
    --hidden-import rumps \
    --hidden-import requests \
    --collect-all rumps \
    main.py

echo ""
if [ -d "dist/OpenAIUsageTray.app" ]; then
    echo "Build succeeded: dist/OpenAIUsageTray.app"
else
    echo "Build FAILED — check output above."
    exit 1
fi
