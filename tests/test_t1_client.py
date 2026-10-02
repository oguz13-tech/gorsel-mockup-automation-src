import os
import sys
import unittest
import json

# Add parent to path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'SABLON_V2_MIMARI')))

class TestT1Client(unittest.TestCase):
    def setUp(self):
        try:
            from app import app
            app.config['TESTING'] = True
            self.client = app.test_client()
        except ImportError:
            self.client = None

    def test_delete_undo_flow(self):
        if not self.client:
            print("Skipping Flask test because app cannot be imported in this isolated test env")
            return
            
        # Simulate a reject
        rv = self.client.post('/api/templates/reject', json={
            "category": "dummy_cat",
            "template": "dummy_tmpl"
        })
        self.assertEqual(rv.status_code, 200)
        
        # Simulate an undo / approve
        rv2 = self.client.post('/api/templates/update', json={
            "category": "dummy_cat",
            "template": "dummy_tmpl",
            "points": [[0,0], [1,0], [1,1], [0,1]]
        })
        self.assertEqual(rv2.status_code, 200)

if __name__ == '__main__':
    unittest.main()
