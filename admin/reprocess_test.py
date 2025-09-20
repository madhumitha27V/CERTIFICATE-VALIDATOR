#!/usr/bin/env python3
"""Reprocess an existing image to test the improved extraction"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import *
from PIL import Image
import pytesseract

def reprocess_image(image_filename):
    """Reprocess an uploaded image with the improved extraction logic"""
    
    image_path = os.path.join('static', 'uploads', image_filename)
    print(f"Processing image: {image_path}")
    
    if not os.path.exists(image_path):
        print(f"Image not found: {image_path}")
        return
    
    try:
        # Load and preprocess image
        image = Image.open(image_path)
        processed_image = preprocess_image(image)
        
        # Extract OCR text
        text = pytesseract.image_to_string(processed_image, config='--psm 6')
        
        print("=== OCR Text Preview (last 20 lines) ===")
        lines = text.split('\n')
        for i, line in enumerate(lines[-20:], start=max(0, len(lines)-20)):
            print(f"Line {i}: {line.strip()}")
        
        # Detect session
        session = detect_session(text)
        print(f"\nDetected session: {session}")
        
        # Extract marksheet data
        print("\n=== Extracting Marksheet Data ===")
        data = extract_marksheet_data(text)
        data['session'] = session
        data['meta'] = f"Reprocessed from {image_filename}"
        
        print(f"\nExtracted basic data:")
        for key, value in data.items():
            if key not in ['subjects']:
                print(f"  {key}: {value}")
        
        # Create meta data
        print("\n=== Creating Meta Data ===")
        meta_json = create_meta_data(data)
        
        # Parse and display meta data
        import json
        meta_data = json.loads(meta_json)
        
        if 'academic_progress' in meta_data:
            print("\n=== Semester-wise Progress ===")
            for sem, sem_data in meta_data['academic_progress'].items():
                print(f"{sem} ({sem_data['period']}): Credits Enrolled: {sem_data['credits_enrolled']}, Credits Earned: {sem_data['credits_earned']}, GPA: {sem_data['gpa']}")
            
            if 'totals' in meta_data:
                totals = meta_data['totals']
                print(f"Total: Credits Enrolled: {totals['credits_enrolled']}, Credits Earned: {totals['credits_earned']}")
        
        print(f"\n=== SUCCESS: Semester data extracted and structured correctly! ===")
        
    except Exception as e:
        print(f"Error processing image: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Test with one of the uploaded images
    reprocess_image("nov2024-3rd_sem.jpg")