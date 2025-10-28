#!/bin/bash
set -e

echo "🔄 Installing system dependencies..."
apt-get update
apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    libleptonica-dev \
    pkg-config

echo "🔍 Verifying Tesseract installation..."
tesseract --version
which tesseract

echo "🔄 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Build completed successfully!"