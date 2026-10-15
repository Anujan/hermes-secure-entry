import json
import tempfile
import unittest
from pathlib import Path


class NativeTests(unittest.TestCase):
    def test_standalone_add_uses_real_native_encrypted_vault(self):
        from agent.vault_store import VaultStore
        from secure_entry.native import add_login, validate_origin
        with tempfile.TemporaryDirectory() as directory:
            store = VaultStore(Path(directory))
            result = add_login(store, 'https://example.invalid', {'identifier':'synthetic-user', 'password':'SYNTHETIC-ONLY-PASSWORD'})
            self.assertEqual(result['status'], 'saved')
            self.assertEqual(store.get_meta(result['handle']).origin, 'https://example.invalid')
            self.assertEqual(store.resolve_secret(result['handle'])['password'], 'SYNTHETIC-ONLY-PASSWORD')
            self.assertNotIn(b'SYNTHETIC-ONLY-PASSWORD', (Path(directory) / 'vault.json.enc').read_bytes())
        for bad in ['example.invalid', 'https://example.invalid/path', 'https://a@b.invalid', 'http://example.invalid', 'https://example.invalid/#x']:
            with self.assertRaises(ValueError): validate_origin(bad)

    def test_committed_add_with_failed_readback_is_not_retryable_failure(self):
        from agent.vault_store import VaultStore
        from secure_entry.native import add_login
        from secure_entry.broker import Broker
        for mode in ('raises', 'missing'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                class ReadbackFailure(VaultStore):
                    def get_meta(self, handle):
                        if mode == 'raises': raise OSError('SYNTHETIC-SECRET-IN-ERROR')
                        return None
                store = ReadbackFailure(Path(directory))
                broker = Broker('https://example.invalid')
                request = broker.issue('login', 'https://example.invalid', ('synthetic',),
                                       lambda fields: add_login(store, 'https://example.invalid', fields))
                result = broker.submit(request.token, {'csrf':request.csrf, 'action':'submit',
                                      'identifier':'synthetic-user', 'password':'SYNTHETIC-PASSWORD'})
                self.assertEqual(result['status'], 'commit_unknown')
                self.assertTrue(result['handle'])
                self.assertEqual(result['identifier'], 'synthetic-user')
                reopened = VaultStore(Path(directory))
                self.assertEqual(len(reopened.list_items()), 1)
                self.assertEqual(reopened.get_meta(result['handle']).identifier, 'synthetic-user')
                self.assertEqual(broker.submit(request.token, {'csrf':request.csrf, 'action':'submit',
                                 'identifier':'synthetic-user', 'password':'SYNTHETIC-PASSWORD'}), result)
                self.assertEqual(len(reopened.list_items()), 1)
                page = broker.page(request.token)
                self.assertIn('Inspect the native vault', page)
                self.assertNotIn('Request a new link', page)
                self.assertNotIn('SYNTHETIC-', page + json.dumps(result))

    def test_photon_owner_requires_bound_dm_and_default_home(self):
        from gateway.session_context import set_session_vars, clear_session_vars
        from hermes_constants import get_hermes_home
        from secure_entry.native import owner
        home = str(get_hermes_home())
        for platform, chat_type, sid in [('webhook','dm','s'), ('photon','group','s'), ('photon','dm','')]:
            tokens = set_session_vars(platform=platform, chat_id='synthetic-chat', chat_type=chat_type,
                                      user_id='synthetic-user', session_key='synthetic-key', session_id=sid)
            try:
                with self.assertRaises(ValueError): owner(home)
            finally: clear_session_vars(tokens)
        tokens = set_session_vars(platform='photon', chat_id='synthetic-chat', chat_type='dm',
                                  user_id='synthetic-user', session_key='synthetic-key', session_id='synthetic-session')
        try:
            bound = owner(home)
            self.assertIn('synthetic-session', bound)
            with self.assertRaises(ValueError): owner(home + '-other')
        finally: clear_session_vars(tokens)
