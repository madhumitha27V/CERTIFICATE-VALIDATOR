import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime
import hashlib

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import re
import json

# Set Tesseract-OCR path (Windows local vs Linux hosting)
tesseract_cmd = os.environ.get('TESSERACT_CMD', r'F:\Tesseract-OCR\tesseract.exe')
pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

app = Flask(__name__)
app.secret_key = 'user_portal_secret_key_2025'

UPLOAD_FOLDER = 'static/uploads/'
ALLOWED_EXTENSIONS = {'jpeg', 'jpg', 'png', 'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Database configuration with environment support
ADMIN_DB_PATH = os.environ.get('ADMIN_DATABASE_PATH', 'F:/CERTIFICATE - FINAL - SIH/admin/database.db')
USER_DB_PATH = os.environ.get('USER_DATABASE_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db'))
print(f"🗄️  User app using admin database: {ADMIN_DB_PATH}")
print(f"🗄️  User app using user database: {USER_DB_PATH}")

# --- Helper Functions ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    """Verify password against hash"""
    return hashlib.sha256(password.encode()).hexdigest() == hashed

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_admin_db():
    """Connect to admin database for certificate verification"""
    try:
        return sqlite3.connect(ADMIN_DB_PATH)
    except sqlite3.Error:
        return None

def get_user_db():
    """Connect to user database"""
    return sqlite3.connect(USER_DB_PATH)

def preprocess_image(image):
    """Preprocess image for better OCR accuracy"""
    # Convert to grayscale
    image = image.convert('L')
    
    # Resize image if too small (OCR works better on larger images)
    width, height = image.size
    if width < 1000:
        scale_factor = 1000 / width
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Enhance contrast
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.5)
    
    # Enhance sharpness
    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(2.5)
    
    # Enhance brightness slightly
    enhancer = ImageEnhance.Brightness(image)
    image = enhancer.enhance(1.2)
    
    # Apply noise reduction
    image = image.filter(ImageFilter.MedianFilter(size=3))
    
    return image

def extract_certificate_data(text):
    """Extract certificate data from OCR text using the same logic as admin"""
    data = {}
    
    # Clean the text
    text = re.sub(r'\s{2,}', ' ', text.strip())
    text_lower = text.lower()
    
    # Extract student name
    name_patterns = [
        r'Name\s*[:\-]?\s*([A-Z][A-Z\s]+?)(?:\s+Register|\s+Fr|\s+[a-z])',
        r'ame\s*[:\-]?\s*([A-Z][A-Z\s]+?)(?:\s+Register|\s+Fr|\s+[a-z])',
        r'([A-Z]{3,}\s+[A-Z]{1,2})(?:\s+om\s+FR|\s+Register)',
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            name = re.sub(r'[^\w\s]', '', name).strip()
            name = re.sub(r'\b(om|FR|Register|Number|Date|Birth|Gender)\b', '', name, flags=re.IGNORECASE).strip()
            name = re.sub(r'\s+', ' ', name)
            if len(name) > 2:
                data['student_name'] = name.title()
                break
    
    # Extract register number
    register_patterns = [
        r'Register.*?Number\s*[:\-]?\s*([A-Z0-9]+)',
        r'Registration.*?No\s*[:\-]?\s*([A-Z0-9]+)',
        r'Reg.*?No\s*[:\-]?\s*([A-Z0-9]+)',
        r'([0-9]{2}[A-Z]{2,3}[0-9]{3,4})',
    ]
    
    for pattern in register_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            reg_no = match.group(1).strip()
            if len(reg_no) >= 6:
                data['register_number'] = reg_no.upper()
                break
    
    # Extract college/institution name
    college_patterns = [
        r'(KONGU ENGINEERING COLLEGE)',
        r'([A-Z\s]+ENGINEERING COLLEGE)',
        r'([A-Z\s]+UNIVERSITY)',
        r'([A-Z\s]+COLLEGE)',
        r'([A-Z\s]+INSTITUTE)'
    ]
    
    for pattern in college_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data['college_name'] = match.group(1).strip().title()
            break
    
    # Extract session/semester info
    session_patterns = [
        r'(JANUARY\s+2024|JAN\s+2024)',
        r'(MAY\s+2024)',
        r'(NOVEMBER\s+2024|NOV\s+2024)'
    ]
    
    for pattern in session_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            session_text = match.group(1).upper()
            if 'JAN' in session_text:
                data['session'] = 'jan2024'
            elif 'MAY' in session_text:
                data['session'] = 'may2024'
            elif 'NOV' in session_text:
                data['session'] = 'nov2024'
            break
    
    # Extract GPA/CGPA
    gpa_patterns = [
        r'GPA\s*[:\-]?\s*([0-9]+\.?[0-9]*)',
        r'CGPA\s*[:\-]?\s*([0-9]+\.?[0-9]*)',
    ]
    
    for pattern in gpa_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            gpa_value = float(match.group(1))
            if 0 <= gpa_value <= 10:
                data['gpa'] = gpa_value
                break
    
    return data

def verify_certificate_in_admin_db(certificate_data):
    """Verify if certificate exists in admin database"""
    admin_conn = get_admin_db()
    if not admin_conn:
        return {'status': 'error', 'message': 'Cannot connect to verification database'}
    
    try:
        cursor = admin_conn.cursor()
        sessions = ['jan2024', 'may2024', 'nov2024']
        
        for session_name in sessions:
            table_name = f'block_{session_name}'
            
            # Check if table exists
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
            if not cursor.fetchone():
                continue
            
            # Search for matching records
            search_conditions = []
            search_params = []
            
            if certificate_data.get('student_name'):
                search_conditions.append("student_name LIKE ?")
                search_params.append(f"%{certificate_data['student_name']}%")
            
            if certificate_data.get('register_number'):
                search_conditions.append("register_number LIKE ?")
                search_params.append(f"%{certificate_data['register_number']}%")
            
            if search_conditions:
                query = f"SELECT * FROM {table_name} WHERE " + " OR ".join(search_conditions)
                cursor.execute(query, search_params)
                results = cursor.fetchall()
                
                if results:
                    # Get column names
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = [column[1] for column in cursor.fetchall()]
                    
                    # Convert to dictionary
                    verified_records = []
                    for result in results:
                        record = dict(zip(columns, result))
                        verified_records.append(record)
                    
                    admin_conn.close()
                    return {
                        'status': 'verified',
                        'message': f'Certificate found in {session_name.upper()} session',
                        'records': verified_records,
                        'session': session_name
                    }
        
        admin_conn.close()
        return {
            'status': 'not_found',
            'message': 'Certificate not found in verification database'
        }
        
    except Exception as e:
        admin_conn.close()
        return {
            'status': 'error',
            'message': f'Verification error: {str(e)}'
        }

def create_user_tables():
    """Create user-specific tables"""
    conn = get_user_db()
    cursor = conn.cursor()
    
    # Users table for user portal
    cursor.execute('''CREATE TABLE IF NOT EXISTS portal_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP,
        is_active BOOLEAN DEFAULT 1
    )''')
    
    # User certificates table
    cursor.execute('''CREATE TABLE IF NOT EXISTS user_certificates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        filename TEXT NOT NULL,
        original_filename TEXT NOT NULL,
        upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        extracted_data TEXT,
        verification_status TEXT DEFAULT 'pending',
        verification_result TEXT,
        FOREIGN KEY (user_id) REFERENCES portal_users (id)
    )''')
    
    # Verification requests table
    cursor.execute('''CREATE TABLE IF NOT EXISTS verification_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        search_query TEXT NOT NULL,
        search_type TEXT NOT NULL,
        request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        result TEXT,
        FOREIGN KEY (user_id) REFERENCES portal_users (id)
    )''')
    
    conn.commit()
    conn.close()

# Initialize database
create_user_tables()

# --- Routes ---
@app.route('/')
def index():
    """Landing page for users"""
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        full_name = request.form.get('full_name', '').strip()
        
        # Validation
        if not all([username, email, password, confirm_password]):
            flash('All fields are required.', 'danger')
            return render_template('signup.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('signup.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('signup.html')
        
        # Hash password
        password_hash = hash_password(password)
        
        conn = get_user_db()
        cursor = conn.cursor()
        try:
            cursor.execute('''INSERT INTO portal_users (username, email, password_hash, full_name) 
                            VALUES (?, ?, ?, ?)''', (username, email, password_hash, full_name))
            conn.commit()
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError as e:
            if 'username' in str(e):
                flash('Username already exists. Please choose a different one.', 'danger')
            elif 'email' in str(e):
                flash('Email already registered. Please use a different email.', 'danger')
            else:
                flash('Registration failed. Please try again.', 'danger')
        except Exception as e:
            flash(f'Registration error: {str(e)}', 'danger')
        finally:
            conn.close()
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Please enter both username and password.', 'danger')
            return render_template('login.html')
        
        conn = get_user_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, username, password_hash, email, full_name FROM portal_users WHERE username=? AND is_active=1', (username,))
        user = cursor.fetchone()
        
        if user and verify_password(password, user[2]):
            # Login successful
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['email'] = user[3]
            session['full_name'] = user[4] or user[1]
            
            # Update last login
            cursor.execute('UPDATE portal_users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user[0],))
            conn.commit()
            
            flash(f'Welcome back, {session["full_name"]}!', 'success')
            conn.close()
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
        
        conn.close()
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard"""
    conn = get_user_db()
    cursor = conn.cursor()
    
    user_id = session['user_id']
    
    # Get user statistics
    cursor.execute('SELECT COUNT(*) FROM user_certificates WHERE user_id = ?', (user_id,))
    total_uploads = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM user_certificates WHERE user_id = ? AND verification_status = "verified"', (user_id,))
    verified_certificates = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM verification_requests WHERE user_id = ?', (user_id,))
    verification_requests = cursor.fetchone()[0]
    
    # Get recent uploads
    cursor.execute('''SELECT original_filename, upload_date, verification_status 
                     FROM user_certificates WHERE user_id = ? 
                     ORDER BY upload_date DESC LIMIT 5''', (user_id,))
    recent_uploads = cursor.fetchall()
    
    conn.close()
    
    stats = {
        'total_uploads': total_uploads,
        'verified_certificates': verified_certificates,
        'pending_certificates': total_uploads - verified_certificates,
        'verification_requests': verification_requests
    }
    
    return render_template('dashboard.html', stats=stats, recent_uploads=recent_uploads)

@app.route('/upload_certificate', methods=['GET', 'POST'])
@login_required
def upload_certificate():
    if request.method == 'POST':
        # Check if file was uploaded
        if 'file' not in request.files:
            flash('No file selected. Please choose a file to upload.', 'danger')
            return render_template('upload_certificate.html')
            
        file = request.files['file']
        
        if not file or file.filename == '':
            flash('Please select a file to upload.', 'danger')
            return render_template('upload_certificate.html')
        
        if not allowed_file(file.filename):
            flash('Invalid file type. Please upload JPG, PNG, or PDF files only.', 'danger')
            return render_template('upload_certificate.html')
        
        try:
            # Save file
            filename = secure_filename(file.filename)
            # Add timestamp to avoid conflicts
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
            filename = timestamp + filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Extract data using OCR
            extracted_data = {}
            verification_result = {}
            
            if file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                try:
                    image = Image.open(filepath)
                    processed_image = preprocess_image(image)
                    
                    # OCR extraction
                    ocr_configs = ['--psm 6', '--psm 4', '--psm 3']
                    text = None
                    
                    for config in ocr_configs:
                        try:
                            text = pytesseract.image_to_string(processed_image, config=config)
                            if text and len(text.strip()) > 50:
                                break
                        except:
                            continue
                    
                    if text and len(text.strip()) > 20:
                        extracted_data = extract_certificate_data(text)
                        
                        # Verify against admin database
                        if extracted_data:
                            verification_result = verify_certificate_in_admin_db(extracted_data)
                        else:
                            verification_result = {
                                'status': 'insufficient_data',
                                'message': 'Could not extract enough data from certificate'
                            }
                    else:
                        verification_result = {
                            'status': 'ocr_failed',
                            'message': 'Could not read text from image. Please ensure image is clear and try again.'
                        }
                        
                except Exception as e:
                    verification_result = {
                        'status': 'processing_error',
                        'message': f'Error processing image: {str(e)}'
                    }
            else:
                verification_result = {
                    'status': 'unsupported_format',
                    'message': 'PDF processing not yet supported. Please upload JPG or PNG images.'
                }
            
            # Save to database
            conn = get_user_db()
            cursor = conn.cursor()
            
            status = verification_result.get('status', 'pending')
            verification_status = 'verified' if status == 'verified' else 'pending'
            
            cursor.execute('''INSERT INTO user_certificates 
                            (user_id, filename, original_filename, extracted_data, verification_status, verification_result)
                            VALUES (?, ?, ?, ?, ?, ?)''',
                          (session['user_id'], filename, file.filename, 
                           json.dumps(extracted_data), verification_status, json.dumps(verification_result)))
            conn.commit()
            certificate_id = cursor.lastrowid
            conn.close()
            
            if verification_result.get('status') == 'verified':
                flash('Certificate uploaded and verified successfully!', 'success')
            elif verification_result.get('status') == 'not_found':
                flash('Certificate uploaded but not found in verification database.', 'warning')
            else:
                flash(f'Certificate uploaded. {verification_result.get("message", "")}', 'info')
            
            return redirect(url_for('view_certificate', cert_id=certificate_id))
            
        except Exception as e:
            flash(f'Upload failed: {str(e)}', 'danger')
    
    return render_template('upload_certificate.html')

@app.route('/verify_certificate', methods=['GET', 'POST'])
@login_required
def verify_certificate():
    if request.method == 'POST':
        search_query = request.form.get('search_query', '').strip()
        search_type = request.form.get('search_type', 'name')
        
        if not search_query:
            flash('Please enter search criteria.', 'danger')
            return render_template('verify_certificate.html')
        
        # Prepare search data
        search_data = {}
        if search_type == 'name':
            search_data['student_name'] = search_query
        elif search_type == 'register':
            search_data['register_number'] = search_query
        
        # Verify in admin database
        verification_result = verify_certificate_in_admin_db(search_data)
        
        # Save verification request
        conn = get_user_db()
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO verification_requests (user_id, search_query, search_type, result)
                         VALUES (?, ?, ?, ?)''',
                      (session['user_id'], search_query, search_type, json.dumps(verification_result)))
        conn.commit()
        conn.close()
        
        return render_template('verify_certificate.html', 
                             search_performed=True, 
                             search_query=search_query,
                             search_type=search_type,
                             result=verification_result)
    
    return render_template('verify_certificate.html')

@app.route('/my_certificates')
@login_required
def my_certificates():
    conn = get_user_db()
    cursor = conn.cursor()
    
    cursor.execute('''SELECT id, original_filename, upload_date, verification_status, extracted_data, verification_result
                     FROM user_certificates WHERE user_id = ? 
                     ORDER BY upload_date DESC''', (session['user_id'],))
    certificates = cursor.fetchall()
    
    conn.close()
    
    # Parse JSON data
    parsed_certificates = []
    for cert in certificates:
        try:
            extracted_data = json.loads(cert[4]) if cert[4] else {}
            verification_result = json.loads(cert[5]) if cert[5] else {}
        except:
            extracted_data = {}
            verification_result = {}
        
        parsed_certificates.append({
            'id': cert[0],
            'filename': cert[1],
            'upload_date': cert[2],
            'status': cert[3],
            'extracted_data': extracted_data,
            'verification_result': verification_result
        })
    
    return render_template('my_certificates.html', certificates=parsed_certificates)

@app.route('/certificate/<int:cert_id>')
@login_required
def view_certificate(cert_id):
    conn = get_user_db()
    cursor = conn.cursor()
    
    cursor.execute('''SELECT * FROM user_certificates 
                     WHERE id = ? AND user_id = ?''', (cert_id, session['user_id']))
    certificate = cursor.fetchone()
    
    if not certificate:
        flash('Certificate not found.', 'danger')
        return redirect(url_for('my_certificates'))
    
    # Parse JSON data
    try:
        extracted_data = json.loads(certificate[4]) if certificate[4] else {}
        verification_result = json.loads(certificate[6]) if certificate[6] else {}
    except:
        extracted_data = {}
        verification_result = {}
    
    cert_data = {
        'id': certificate[0],
        'filename': certificate[2],
        'original_filename': certificate[3],
        'upload_date': certificate[4], 
        'extracted_data': extracted_data,
        'verification_status': certificate[5],
        'verification_result': verification_result
    }
    
    conn.close()
    return render_template('view_certificate.html', certificate=cert_data)

# --- API Routes ---
@app.route('/api/stats')
@login_required
def api_stats():
    conn = get_user_db()
    cursor = conn.cursor()
    
    user_id = session['user_id']
    
    cursor.execute('SELECT COUNT(*) FROM user_certificates WHERE user_id = ?', (user_id,))
    total_uploads = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM user_certificates WHERE user_id = ? AND verification_status = "verified"', (user_id,))
    verified = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM verification_requests WHERE user_id = ?', (user_id,))
    requests = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'total_uploads': total_uploads,
        'verified_certificates': verified,
        'pending_certificates': total_uploads - verified,
        'verification_requests': requests
    })

def init_user_database():
    """Initialize user database tables at startup"""
    try:
        create_user_tables()
        print("✅ User database tables initialized successfully")
    except Exception as e:
        print(f"❌ User database initialization error: {e}")

if __name__ == '__main__':
    init_user_database()
    app.run(debug=True, port=5001)