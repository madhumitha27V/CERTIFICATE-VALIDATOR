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
import csv

# Set Tesseract-OCR path for Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

app = Flask(__name__)
app.secret_key = 'user_portal_secret_key_2025'

UPLOAD_FOLDER = 'static/uploads/'
ALLOWED_EXTENSIONS = {'jpeg', 'jpg', 'png', 'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Database path
ADMIN_DB_PATH = 'C:/Users/dharn/OneDrive/Desktop/SIH/prototype 6/CERTIFICATE - FINAL - SIH/database.db'
USER_DB_PATH = 'database.db'

# --- Database Helper Functions ---
def get_admin_db():
    """Connect to admin database for certificate verification"""
    try:
        return sqlite3.connect(ADMIN_DB_PATH)
    except sqlite3.Error:
        return None

def get_user_db():
    """Connect to user database"""
    return sqlite3.connect(USER_DB_PATH)

# --- General Helper Functions ---
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

# --- OCR and Verification Logic ---
def preprocess_image(image):
    """Preprocess image for better OCR accuracy"""
    image = image.convert('L')
    width, height = image.size
    if width < 1000:
        scale_factor = 1000 / width
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.5)
    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(2.5)
    enhancer = ImageEnhance.Brightness(image)
    image = enhancer.enhance(1.2)
    image = image.filter(ImageFilter.MedianFilter(size=3))
    return image

def extract_certificate_data(text):
    """Extract certificate data from OCR text based on observed patterns."""
    data = {}
    text_upper = text.upper()
    
    # Flexible pattern for student name (handles optional colon and varied spacing)
    name_pattern = r'NAME\s*:?\s*([A-Z\s.V]+)'
    name_match = re.search(name_pattern, text_upper)
    if name_match:
        # Extract the full line and then clean it
        full_match = name_match.group(1)
        # Split by newline and take the first part, which should be the name line
        name_line = full_match.split('\n')[0]
        # Remove common noise words and characters
        name = re.sub(r'\b(SE|RSE|PS|EA|OY)\b', '', name_line)
        name = re.sub(r'[^\w\s]', '', name).strip()
        name = ' '.join(name.split())  # Normalize whitespace
        data['student_name'] = name.title()

    # Flexible pattern for registration number (handles optional colon or semicolon)
    reg_pattern = r'REGISTER\s+NUMBER\s*[:;]?\s*(\d+)'
    reg_match = re.search(reg_pattern, text_upper)
    if reg_match:
        data['register_number'] = reg_match.group(1).strip()
            
    return data if 'student_name' in data and 'register_number' in data else None

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
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
            if not cursor.fetchone():
                continue
            
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
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = [column[1] for column in cursor.fetchall()]
                    verified_records = [dict(zip(columns, result)) for result in results]
                    admin_conn.close()
                    return {
                        'status': 'verified',
                        'message': f'Certificate found in {session_name.upper()} session',
                        'records': verified_records
                    }
        
        admin_conn.close()
        return {'status': 'not_found', 'message': 'Certificate not found in verification database'}
    except Exception as e:
        if admin_conn:
            admin_conn.close()
        return {'status': 'error', 'message': f'Verification error: {str(e)}'}

# --- Database Initialization ---
def create_user_tables():
    """Create user-specific tables"""
    conn = get_user_db()
    cursor = conn.cursor()
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

create_user_tables()

# --- Main Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        full_name = request.form.get('full_name', '').strip()
        
        if not all([username, email, password, full_name]):
            flash('All fields are required.', 'danger')
            return render_template('signup.html')
        if request.form.get('confirm_password') != password:
            flash('Passwords do not match.', 'danger')
            return render_template('signup.html')
        
        password_hash = hash_password(password)
        conn = get_user_db()
        try:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO portal_users (username, email, password_hash, full_name) VALUES (?, ?, ?, ?)', 
                           (username, email, password_hash, full_name))
            conn.commit()
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists.', 'danger')
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
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['email'] = user[3]
            session['full_name'] = user[4] or user[1]
            
            cursor.execute('UPDATE portal_users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user[0],))
            conn.commit()
            conn.close()
            
            flash(f'Welcome back, {session["full_name"]}!', 'success')
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
    conn = get_user_db()
    cursor = conn.cursor()
    user_id = session['user_id']
    
    cursor.execute('SELECT COUNT(*) FROM user_certificates WHERE user_id = ?', (user_id,))
    total_uploads = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM user_certificates WHERE user_id = ? AND verification_status = "verified"', (user_id,))
    verified_certificates = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM verification_requests WHERE user_id = ?', (user_id,))
    verification_requests = cursor.fetchone()[0]
    
    cursor.execute('SELECT original_filename, upload_date, verification_status FROM user_certificates WHERE user_id = ? ORDER BY upload_date DESC LIMIT 5', (user_id,))
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
        if 'file' not in request.files or not request.files['file'].filename:
            flash('No file selected.', 'danger')
            return render_template('upload_certificate.html')
            
        file = request.files['file']
        if not allowed_file(file.filename):
            flash('Invalid file type. Please upload JPG, PNG, or PDF.', 'danger')
            return render_template('upload_certificate.html')
        
        try:
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
            saved_filename = timestamp + filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], saved_filename)
            file.save(filepath)
            
            extracted_data, verification_result = {}, {}
            if file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                try:
                    image = Image.open(filepath)
                    processed_image = preprocess_image(image)
                    text = pytesseract.image_to_string(processed_image, config='--psm 6')
                    
                    # --- Start Debug Logging ---
                    print("--- OCR DEBUG START ---")
                    print(f"File: {saved_filename}")
                    print("--- EXTRACTED TEXT ---")
                    print(text)
                    print("--- OCR DEBUG END ---")
                    # --- End Debug Logging ---
                    
                    if text and len(text.strip()) > 10:
                        extracted_data = extract_certificate_data(text)
                        if extracted_data:
                            verification_result = verify_certificate_in_admin_db(extracted_data)
                        else:
                            verification_result = {'status': 'insufficient_data', 'message': 'Could not extract key details from certificate.'}
                    else:
                        verification_result = {'status': 'ocr_failed', 'message': 'Could not read text from image.'}
                except Exception as e:
                    verification_result = {'status': 'processing_error', 'message': f'Error processing image: {str(e)}'}
            else:
                verification_result = {'status': 'unsupported_format', 'message': 'PDF processing not yet supported.'}
            
            conn = get_user_db()
            cursor = conn.cursor()
            status = verification_result.get('status', 'pending')
            verification_status = 'verified' if status == 'verified' else 'pending'
            
            cursor.execute('INSERT INTO user_certificates (user_id, filename, original_filename, extracted_data, verification_status, verification_result) VALUES (?, ?, ?, ?, ?, ?)',
                          (session['user_id'], saved_filename, filename, json.dumps(extracted_data), verification_status, json.dumps(verification_result)))
            conn.commit()
            certificate_id = cursor.lastrowid
            conn.close()
            
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
        
        search_data = {'student_name' if search_type == 'name' else 'register_number': search_query}
        verification_result = verify_certificate_in_admin_db(search_data)
        
        conn = get_user_db()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO verification_requests (user_id, search_query, search_type, result) VALUES (?, ?, ?, ?)',
                      (session['user_id'], search_query, search_type, json.dumps(verification_result)))
        conn.commit()
        conn.close()
        
        return render_template('verify_certificate.html', search_performed=True, result=verification_result)
    
    return render_template('verify_certificate.html')

@app.route('/my_certificates')
@login_required
def my_certificates():
    conn = get_user_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, original_filename, upload_date, verification_status FROM user_certificates WHERE user_id = ? ORDER BY upload_date DESC', (session['user_id'],))
    certificates = cursor.fetchall()
    conn.close()
    
    parsed_certificates = [{'id': c[0], 'filename': c[1], 'upload_date': c[2], 'status': c[3]} for c in certificates]
    return render_template('my_certificates.html', certificates=parsed_certificates)

@app.route('/certificate/<int:cert_id>')
@login_required
def view_certificate(cert_id):
    conn = get_user_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM user_certificates WHERE id = ? AND user_id = ?', (cert_id, session['user_id']))
    cert = cursor.fetchone()
    conn.close()
    
    if not cert:
        flash('Certificate not found.', 'danger')
        return redirect(url_for('my_certificates'))
    
    cert_data = {
        'id': cert[0], 'user_id': cert[1], 'filename': cert[2], 'original_filename': cert[3],
        'upload_date': cert[4], 'extracted_data': json.loads(cert[5] or '{}'),
        'verification_status': cert[6], 'verification_result': json.loads(cert[7] or '{}')
    }
    return render_template('view_certificate.html', certificate=cert_data)

# --- Bulk Verification Routes ---
# @app.route('/upload_csv', methods=['GET', 'POST'])
# @login_required
# def upload_csv():
#     if request.method == 'POST':
#         if 'file' not in request.files or not request.files['file'].filename:
#             flash('No file selected.', 'danger')
#             return render_template('upload_csv.html')
#         file = request.files['file']
#         if not file.filename.lower().endswith('.csv'):
#             flash('Invalid file type. Please upload a CSV file.', 'danger')
#             return render_template('upload_csv.html')
        
#         filename = secure_filename(file.filename)
#         save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
#         file.save(save_path)
#         flash('CSV file uploaded successfully! You can now verify it.', 'success')
#         return redirect(url_for('verify_bulk_csv', csv_file=filename))
#     return render_template('upload_csv.html')

# @app.route('/verify_bulk_csv', methods=['GET', 'POST'])
# @login_required
# def verify_bulk_csv():
#     results = []
#     if request.method == 'POST':
#         if 'file' not in request.files:
#             flash('No file part', 'danger')
#             return redirect(request.url)
#         file = request.files['file']
#         if file.filename == '':
#             flash('No selected file', 'danger')
#             return redirect(request.url)
#         if file and file.filename.lower().endswith('.csv'):
#             try:
#                 stream = file.stream.read().decode("utf-8")
#                 reader = csv.DictReader(stream.splitlines())
#                 for row in reader:
#                     search_data = {}
#                     if 'student_name' in row and row['student_name']:
#                         search_data['student_name'] = row['student_name']
#                     if 'register_number' in row and row['register_number']:
#                         search_data['register_number'] = row['register_number']
                    
#                     if not search_data:
#                         results.append({'row': row, 'status': 'skipped', 'message': 'Missing key data.'})
#                     else:
#                         verification = verify_certificate_in_admin_db(search_data)
#                         results.append({'row': row, 'verification': verification})
#             except Exception as e:
#                 flash(f'Error processing CSV: {str(e)}', 'danger')
    
#     # This part is for rendering the page, including when it's a GET request
#     stats = {'total_uploads': 0, 'verified_certificates': 0, 'pending_certificates': 0, 'verification_requests': 0}
#     return render_template('verify_bulk_csv.html', results=results, stats=stats)

if __name__ == '__main__':
    app.run(debug=True, port=5001)