import sqlite3

# Path to your database
db_path = r'C:\Users\dharn\OneDrive\Desktop\SIH\prototype 6\CERTIFICATE - FINAL - SIH\database.db'

# Connect to the database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()



# Delete row with id = 1
cursor.execute("DELETE FROM user_certificates WHERE id = 4;")
conn.commit()


# Close the connection
conn.close()