import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class CLITests(unittest.TestCase):
    def test_diagnose_exposes_limitations_without_touching_live_vault(self):
        from secure_entry.cli import diagnose
        out = io.StringIO()
        with patch('sys.stdout', out): diagnose()
        result = json.loads(out.getvalue())
        self.assertEqual(result['browser_prompts'], 'native_callback_preview')
        self.assertEqual(result['operations']['verification_code'], 'native_tool_required')
        self.assertEqual(result['otp_handles'], 'unsupported_handle_binding')
        self.assertFalse(result['core_overrides'])
        self.assertIn('native_atomic_update', result['missing_contracts'])

    def test_demo_only_accepts_known_synthetic_values(self):
        from secure_entry.cli import demo_action
        from agent.vault_store import VaultStore
        with tempfile.TemporaryDirectory() as path:
            store = VaultStore(Path(path))
            self.assertEqual(demo_action(store, {'identifier':'not-a-demo','password':'not-a-demo'})['status'], 'failed')
            self.assertFalse(store.has_items())
            result = demo_action(store, {'identifier':'synthetic@example.invalid','password':'SYNTHETIC-DEMO-ONLY'})
            self.assertEqual(result['status'], 'saved')
            self.assertIsNotNone(store.get_meta(result['handle']))
