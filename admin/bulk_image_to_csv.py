import os
import csv
from PIL import Image
import pytesseract
from app import preprocess_image, extract_marksheet_data, detect_session

# Directory containing images
dir_path = 'C:/Users/dharn/Downloads/bulk'
# Output CSV file
csv_path = 'static/uploads/bulk_certificates.csv'

# List to hold extracted data
data_rows = []

# Loop through all image files in the directory
for filename in os.listdir(dir_path):
    if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        img_path = os.path.join(dir_path, filename)
        try:
            image = Image.open(img_path)
            processed_image = preprocess_image(image)
            text = pytesseract.image_to_string(processed_image, config='--psm 6')
            session = detect_session(text)
            extracted = extract_marksheet_data(text)
            extracted['session'] = session if session else ''
            extracted['source_image'] = filename
            data_rows.append(extracted)
            print(f"Extracted data from {filename}")
        except Exception as e:
            print(f"Error processing {filename}: {e}")

# Determine all possible fieldnames
fieldnames = set()
for row in data_rows:
    fieldnames.update(row.keys())
fieldnames = list(fieldnames)

# Write to CSV
with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    for row in data_rows:
        writer.writerow(row)

print(f"Bulk extraction complete. CSV saved to {csv_path}")
