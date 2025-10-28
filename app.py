#!/usr/bin/env python3
"""
Root-level app.py for Render deployment
Imports the Flask app from admin directory
"""
import sys
import os
import shutil
import sqlite3

# Get the current directory and admin path
current_dir = os.path.dirname(os.path.abspath(__file__))
admin_path = os.path.join(current_dir, 'admin')

# Set up separate database paths for admin and user
persistent_data_dir = '/opt/render/project/src/data'
if os.path.exists(persistent_data_dir):
    # Running on Render with persistent disk
    admin_database_path = os.path.join(persistent_data_dir, 'admin_database.db')
    user_database_path = os.path.join(persistent_data_dir, 'user_database.db')
    print(f"🔄 Using persistent admin database: {admin_database_path}")
    print(f"🔄 Using persistent user database: {user_database_path}")
    
    # Set environment variables
    os.environ['ADMIN_DATABASE_PATH'] = admin_database_path
    os.environ['USER_DATABASE_PATH'] = user_database_path
    os.environ['TESSERACT_CMD'] = 'tesseract'  # Linux system tesseract
    database_path = admin_database_path  # For initialization (admin app)
else:
    # Running locally - separate databases
    admin_database_path = os.path.join(admin_path, 'database.db')
    user_database_path = os.path.join(current_dir, 'user', 'database.db')
    print(f"🔄 Using local admin database: {admin_database_path}")
    print(f"🔄 Using local user database: {user_database_path}")
    database_path = admin_database_path  # For initialization

# Ensure database directory exists
try:
    os.makedirs(os.path.dirname(database_path), exist_ok=True)
    print(f"✅ Database directory created/verified: {os.path.dirname(database_path)}")
except Exception as dir_error:
    print(f"❌ Failed to create database directory: {dir_error}")

# Create empty database file if it doesn't exist
if not os.path.exists(database_path):
    try:
        open(database_path, 'a').close()
        print(f"✅ Created new database file: {database_path}")
    except Exception as file_error:
        print(f"❌ Failed to create database file: {file_error}")
else:
    # Check if we can write to existing database
    try:
        test_conn = sqlite3.connect(database_path)
        test_conn.close()
        print(f"✅ Database file exists and accessible: {database_path}")
    except Exception as access_error:
        print(f"❌ Database file exists but not accessible: {access_error}")

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
            conn = sqlite3.connect(database_path)
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
            
            # Show final database info
            c.execute("SELECT COUNT(*) FROM users")
            total_users = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM admin")
            total_admins = c.fetchone()[0]
            print(f"📊 Final database status - Users: {total_users}, Admins: {total_admins}")
            print(f"📁 Database location: {database_path}")
            
            conn.close()
        except Exception as db_error:
            print(f"❌ Database operations error: {db_error}")
            
        print("✅ Admin database initialization completed successfully")
        
        # Initialize User Database
        print("🔄 Initializing user database...")
        try:
            # Ensure user database directory exists
            os.makedirs(os.path.dirname(user_database_path), exist_ok=True)
            
            # Create user database if it doesn't exist
            if not os.path.exists(user_database_path):
                open(user_database_path, 'a').close()
                print(f"✅ Created user database: {user_database_path}")
            
            # Initialize user database tables
            user_conn = sqlite3.connect(user_database_path)
            user_c = user_conn.cursor()
            
            # Create user tables
            user_c.execute('''CREATE TABLE IF NOT EXISTS portal_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )''')
            
            user_c.execute('''CREATE TABLE IF NOT EXISTS user_certificates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                extracted_data TEXT,
                verification_status TEXT DEFAULT 'pending',
                verification_result TEXT,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES portal_users (id)
            )''')
            
            user_conn.commit()
            
            # Check user database status
            user_c.execute("SELECT COUNT(*) FROM portal_users")
            user_count = user_c.fetchone()[0]
            print(f"✅ User database initialized - Users: {user_count}")
            
            user_conn.close()
            
        except Exception as user_db_error:
            print(f"❌ User database initialization error: {user_db_error}")
        
        print("✅ All databases initialization completed successfully")
except Exception as e:
    print(f"❌ Database initialization error: {e}")

# This is what Render/Gunicorn will look for
if __name__ == '__main__':
    # Get port from environment variable for hosting platforms
    port = int(os.environ.get('PORT', 5000))
    # Run with production settings
    app.run(host='0.0.0.0', port=port, debug=False)