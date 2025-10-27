#!/usr/bin/env python3
"""
Root-level app.py for Render deployment
Imports the Flask app from admin directory
"""
import sys
import os
import shutil

# Get the current directory and admin path
current_dir = os.path.dirname(os.path.abspath(__file__))
admin_path = os.path.join(current_dir, 'admin')

# Ensure database is in the admin directory (copy from root if exists)
root_db = os.path.join(current_dir, 'database.db')
admin_db = os.path.join(admin_path, 'database.db')

if os.path.exists(root_db) and not os.path.exists(admin_db):
    shutil.copy2(root_db, admin_db)
elif not os.path.exists(admin_db):
    # Create empty database file if it doesn't exist
    open(admin_db, 'a').close()

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

# Initialize database tables
try:
    with app.app_context():
        print("Starting database initialization...")
        
        # Initialize database tables if they don't exist
        if hasattr(admin_module, 'create_block_tables'):
            admin_module.create_block_tables()
            print("Block tables created/verified")
        if hasattr(admin_module, 'create_admin_table'):
            admin_module.create_admin_table()
            print("Admin table created/verified")
        if hasattr(admin_module, 'create_users_table'):
            admin_module.create_users_table()
            print("Users table created/verified")
        
        # Create default admin user if none exists
        import sqlite3
        import hashlib
        try:
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            
            # Check if admin table exists and create admin user
            c.execute("SELECT COUNT(*) FROM admin")
            admin_count = c.fetchone()[0]
            
            if admin_count == 0:
                # Create default admin user (username: admin, password: admin123)
                password_hash = hashlib.sha256('admin123'.encode()).hexdigest()
                c.execute("INSERT INTO admin (username, password) VALUES (?, ?)", ('admin', password_hash))
                conn.commit()
                print("✅ Default admin user created: username=admin, password=admin123")
            else:
                print(f"✅ Admin table already has {admin_count} users")
            
            # Check users table
            c.execute("SELECT COUNT(*) FROM users")
            users_count = c.fetchone()[0]
            print(f"✅ Users table has {users_count} registered users")
            
            # Test database write by creating a test entry
            try:
                c.execute("DELETE FROM users WHERE username = 'test_db_write'")
                c.execute("INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)", 
                         ('test_db_write', 'test@test.com', 'test_hash', 'user'))
                c.execute("DELETE FROM users WHERE username = 'test_db_write'")
                conn.commit()
                print("✅ Database write test successful")
            except Exception as write_test_error:
                print(f"❌ Database write test failed: {write_test_error}")
            
            conn.close()
        except Exception as db_error:
            print(f"❌ Database operations error: {db_error}")
            
        print("✅ Database initialization completed successfully")
except Exception as e:
    print(f"❌ Database initialization error: {e}")

# This is what Render/Gunicorn will look for
if __name__ == '__main__':
    # Get port from environment variable for hosting platforms
    port = int(os.environ.get('PORT', 5000))
    # Run with production settings
    app.run(host='0.0.0.0', port=port, debug=False)