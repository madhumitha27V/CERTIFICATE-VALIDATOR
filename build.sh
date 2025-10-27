#!/bin/bash
set -e

echo "Installing system dependencies..."
apt-get update
apt-get install -y tesseract-ocr tesseract-ocr-eng

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Build completed successfully!"