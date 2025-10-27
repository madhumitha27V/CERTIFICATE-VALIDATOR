#!/usr/bin/env python3
"""
Root-level app.py for Render deployment
Imports the Flask app from admin directory
"""
import sys
import os

# Add the admin directory to Python path so we can import from it
admin_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'admin')
sys.path.insert(0, admin_path)

# Import the Flask app from admin/app.py
from app import app

# This is what Render/Gunicorn will look for
if __name__ == '__main__':
    # Get port from environment variable for hosting platforms
    port = int(os.environ.get('PORT', 5000))
    # Run with production settings
    app.run(host='0.0.0.0', port=port, debug=False)