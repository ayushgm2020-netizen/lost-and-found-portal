import unittest
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from matching.matcher import (
    SmartMatcher, calculate_similarity_breakdown, 
    WEIGHT_NAME, WEIGHT_CATEGORY, WEIGHT_DESCRIPTION, WEIGHT_LOCATION, WEIGHT_DATE
)
from app import app
from database.db import query_db, init_db

class SmartRecoverTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def test_factor_weights_sum_to_one(self):
        """Verify weights strictly sum to 1.0 (100%)"""
        total = WEIGHT_NAME + WEIGHT_CATEGORY + WEIGHT_DESCRIPTION + WEIGHT_LOCATION + WEIGHT_DATE
        self.assertAlmostEqual(total, 1.0, places=4)
        self.assertEqual(WEIGHT_NAME, 0.30)
        self.assertEqual(WEIGHT_CATEGORY, 0.20)
        self.assertEqual(WEIGHT_DESCRIPTION, 0.25)
        self.assertEqual(WEIGHT_LOCATION, 0.15)
        self.assertEqual(WEIGHT_DATE, 0.10)

    def test_smart_matcher_identical_items(self):
        """Identical item features should score near 100%"""
        lost = {
            'id': 1, 'institution_id': 1, 'type': 'lost',
            'name': 'Apple AirPods Pro',
            'category': 'Electronics',
            'description': 'White wireless airpods in midnight blue silicone case',
            'location': 'Main Library 2nd Floor',
            'date_event': '2026-11-10',
            'status': 'reported'
        }
        found = {
            'id': 2, 'institution_id': 1, 'type': 'found',
            'name': 'Apple AirPods Pro',
            'category': 'Electronics',
            'description': 'White wireless airpods in midnight blue silicone case',
            'location': 'Main Library 2nd Floor',
            'date_event': '2026-11-10',
            'status': 'reported'
        }

        res = SmartMatcher.evaluate_pair(lost, found)
        self.assertIsNotNone(res)
        self.assertGreaterEqual(res['score'], 90.0)
        self.assertEqual(res['label'], "Strong Possible Match")

    def test_cross_institution_isolation(self):
        """Items from different institutions MUST NOT match"""
        lost = {'id': 1, 'institution_id': 1, 'type': 'lost', 'name': 'MacBook Pro', 'status': 'reported'}
        found = {'id': 2, 'institution_id': 2, 'type': 'found', 'name': 'MacBook Pro', 'status': 'reported'}

        res = SmartMatcher.evaluate_pair(lost, found)
        self.assertIsNone(res)

    def test_same_type_cannot_match(self):
        """Two lost items or two found items cannot match"""
        item1 = {'id': 1, 'institution_id': 1, 'type': 'lost', 'name': 'Wallet', 'status': 'reported'}
        item2 = {'id': 2, 'institution_id': 1, 'type': 'lost', 'name': 'Wallet', 'status': 'reported'}

        res = SmartMatcher.evaluate_pair(item1, item2)
        self.assertIsNone(res)

    def test_recovered_items_excluded_from_matches(self):
        """Recovered or closed items should not generate active matches"""
        lost = {'id': 1, 'institution_id': 1, 'type': 'lost', 'name': 'Key', 'status': 'recovered'}
        found = {'id': 2, 'institution_id': 1, 'type': 'found', 'name': 'Key', 'status': 'reported'}

        res = SmartMatcher.evaluate_pair(lost, found)
        self.assertIsNone(res)

    def test_routes_accessible(self):
        """Test public endpoints return 200 OK"""
        r_home = self.client.get('/')
        self.assertEqual(r_home.status_code, 200)

        r_browse = self.client.get('/items')
        self.assertEqual(r_browse.status_code, 200)

        r_login = self.client.get('/login')
        self.assertEqual(r_login.status_code, 200)

        r_register = self.client.get('/register')
        self.assertEqual(r_register.status_code, 200)

        r_matches = self.client.get('/matches')
        self.assertEqual(r_matches.status_code, 200)

if __name__ == '__main__':
    unittest.main()
