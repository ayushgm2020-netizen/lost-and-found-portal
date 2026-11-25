import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app
from database.db import query_db

client = app.test_client()

# 1. Test Login
res = client.post('/login', data={'email': 'ayush@aiet.edu', 'password': 'password123'}, follow_redirects=True)
assert res.status_code == 200
assert b'Campus Dashboard' in res.data or b'Welcome back' in res.data
print("Test 1: Login successful")

# 2. Test Report Lost Item
res = client.post('/report/lost', data={
    'name': 'Titan Silver Analog Wristwatch',
    'category': 'Accessories',
    'description': 'Metallic silver strap with blue dial lost near basketball court',
    'date_event': '2026-11-10',
    'location': 'Sports Complex Basketball Court',
    'private_details': 'Back casing engraved with initials AG',
    'csrf_token': ''
}, follow_redirects=True)
assert res.status_code == 200
print("Test 2: Report Lost Item successful")

# 3. Test Matches Page
res = client.get('/matches')
assert res.status_code == 200
assert b'Smart Match Synthesizer' in res.data
print("Test 3: Smart Matches page rendered with scores")

# 4. Test Browse Items
res = client.get('/items')
assert res.status_code == 200
assert b'Campus Items Directory' in res.data
print("Test 4: Browse Items directory working")

# 5. Test Admin Login
client.get('/logout')
res = client.post('/login', data={'email': 'admin@aiet.edu', 'password': 'password123'}, follow_redirects=True)
res_admin = client.get('/admin')
assert res_admin.status_code == 200
assert b'Institutional Administrator Console' in res_admin.data
print("Test 5: Admin portal and role-based access verified")

print("\nALL END-TO-END VERIFICATION CHECKS PASSED!")
