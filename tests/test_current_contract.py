"""Hermes 0.22.1 action-dispatch contract; synthetic data only."""
import contextvars
import json
import unittest


from gateway.session_context import set_session_vars, clear_session_vars
from hermes_constants import get_hermes_home, profile_name_for_home
from agent.vault_backends import unlock
from secure_entry.service import Service


class CurrentContractTests(unittest.TestCase):
    def setUp(self):
        self.tokens = set_session_vars(platform='photon', chat_type='dm', chat_id='synthetic-chat',
            user_id='synthetic-owner', session_key='synthetic-key', session_id='synthetic-session',
            profile=profile_name_for_home(get_hermes_home()) or '', cron_session='')
        self.service = Service('https://example.invalid', str(get_hermes_home()), port=0)
        self.service.configure_bridge(lambda *a: None, isolation='in_process')
        self.addCleanup(clear_session_vars, self.tokens)
        self.addCleanup(self.service.close)

    def call(self, args, native):
        return self.service.middleware(tool_name='browser_vault', args=args,
            next_call=native, session_id='synthetic-session')

    def test_current_registered_code_action_installs_scoped_native_callbacks(self):
        callbacks = []
        def native(args):
            callbacks.append(unlock.get_code_prompt_callback())
            return json.dumps({'success': False, 'error_type': 'no_code_field'})
        result = json.loads(self.call({'action': 'enter_code'}, native))
        self.assertTrue(callable(callbacks[0]))
        self.assertEqual(result['error_type'], 'no_code_field')
        self.assertIsNone(unlock.get_code_prompt_callback())
        self.assertIsNone(unlock.get_unlock_prompt_callback())

    def test_current_code_handle_is_refused_before_native_resolution(self):
        called = []
        result = json.loads(self.call({'action': 'enter_code', 'handle': 'vault_synthetic'},
            lambda a: called.append(a)))
        self.assertFalse(called)
        self.assertEqual(result['status'], 'unsupported_handle_binding')

    def test_current_list_and_unlock_install_callbacks_without_rewriting_native_args(self):
        for action in ('list', 'unlock'):
            seen = []
            args = {'action': action, 'backend': 'bitwarden'}
            def native(received):
                self.assertIs(received, args)
                seen.append(callable(unlock.get_unlock_prompt_callback()))
                return json.dumps({'success': True, 'items': []})
            self.call(args, native)
            self.assertEqual(seen, [True])

    def test_current_action_denies_missing_task_local_owner(self):
        called = []
        result = contextvars.Context().run(self.call, {'action': 'enter_code'}, lambda a: called.append(a))
        self.assertFalse(called)
        self.assertFalse(json.loads(result)['success'])

    def test_unrelated_current_actions_are_not_intercepted(self):
        for action in ('fill', 'save_login', 'invalid', None):
            args = {'action': action}
            self.assertEqual(self.call(args, lambda a: 'native-result'), 'native-result')
        self.assertIsNone(unlock.get_code_prompt_callback())

    def test_current_unconfigured_service_refuses_before_native_execution(self):
        service = Service('https://example.invalid', str(get_hermes_home()), port=0)
        self.addCleanup(service.close)
        called = []
        result = service.middleware(tool_name='browser_vault', args={'action': 'unlock'},
            next_call=lambda a: called.append(a), session_id='synthetic-session')
        self.assertFalse(called)
        self.assertEqual(json.loads(result)['error_type'], 'bridge_unavailable')
