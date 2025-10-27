#!/usr/bin/env python3
"""
Root-level app.py for Render deployment
Imports the Flask app from admin directory
"""
import sys
import os

# Get the current directory and admin path
current_dir = os.path.dirname(os.path.abspath(__file__))
admin_path = os.path.join(current_dir, 'admin')

# Change working directory to admin folder so paths work correctly
os.chdir(admin_path)

# Add the admin directory to Python path so we can import from it
sys.path.insert(0, admin_path)

# Import the Flask app from admin/app.py using importlib to avoid circular import
import importlib.util
spec = importlib.util.spec_from_file_location("admin_app", os.path.join(admin_path, "app.py"))
admin_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(admin_module)

# Get the Flask app instance
app = admin_module.app

# Update template and static folder paths to work from root directory
app.template_folder = os.path.join(admin_path, 'templates')
app.static_folder = os.path.join(admin_path, 'static')

# This is what Render/Gunicorn will look for
if __name__ == '__main__':
    # Get port from environment variable for hosting platforms
    port = int(os.environ.get('PORT', 5000))
    # Run with production settings
    app.run(host='0.0.0.0', port=port, debug=False)