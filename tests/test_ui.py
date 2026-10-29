import os
from pathlib import Path
import tempfile
import unittest
from streamlit.testing.v1 import AppTest
ROOT=Path(__file__).resolve().parents[1]
class UserFlows(unittest.TestCase):
    def test_brand_switch_demo_and_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            old=os.environ.get('CAMPAIGNLENS_DB');os.environ['CAMPAIGNLENS_DB']=str(Path(tmp)/'db')
            try:
                app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=20).run()
                self.assertFalse(app.exception)
                next(b for b in app.button if b.label=='Calculate & compare').click().run()
                self.assertFalse(app.exception)
                self.assertEqual(app.metric[0].value,'₹486.27')
                next(b for b in app.button if b.label=='Run offline five-role demo').click().run()
                self.assertFalse(app.exception)
                self.assertEqual(len(app.session_state['active']['reviews']),5)
                next(b for b in app.button if b.label=='Save immutable review snapshot').click().run()
                self.assertFalse(app.exception)
                self.assertTrue(app.session_state['saved_id'])
                app.sidebar.selectbox[0].set_value('Boutique clothing').run()
                self.assertFalse(app.exception)
                with self.assertRaises(KeyError):
                    app.session_state['active']
                next(b for b in app.button if b.label=='Calculate & compare').click().run()
                self.assertFalse(app.exception)
                self.assertEqual(app.session_state['active']['bundle']['brand']['category'],'boutique_apparel')
                self.assertNotEqual(app.metric[0].value,'₹486.27')
            finally:
                if old is None:os.environ.pop('CAMPAIGNLENS_DB',None)
                else:os.environ['CAMPAIGNLENS_DB']=old
