"""Fixed diagnostics must not disclose identity, request data or exceptions."""
import contextvars
import json
import unittest
from unittest.mock import Mock, patch
from gateway.session_context import set_session_vars, clear_session_vars
from hermes_constants import get_hermes_home, profile_name_for_home
from secure_entry.service import Service


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.tokens = set_session_vars(platform='photon', chat_type='dm', chat_id='PRIVATE-CHAT',
            user_id='PRIVATE-USER', session_key='PRIVATE-KEY', session_id='PRIVATE-ID',
            profile=profile_name_for_home(get_hermes_home()) or '', cron_session='')
        self.service = Service('https://example.invalid', str(get_hermes_home()), port=0,
                               store_factory=Mock(return_value=object()))

    def tearDown(self):
        self.service.close()
        clear_session_vars(self.tokens)

    def test_missing_session_binding_is_fixed_and_never_acquires_store(self):
        for field, expected in [('session_id', 'missing_session_id'), ('session_key', 'missing_session_binding'),
                                ('chat_id', 'missing_session_binding'), ('user_id', 'missing_session_binding')]:
            with self.subTest(field=field):
                def run():
                    values = dict(platform='photon', chat_type='dm', chat_id='PRIVATE-CHAT',
                        user_id='PRIVATE-USER', session_key='PRIVATE-KEY', session_id='PRIVATE-ID',
                        profile=profile_name_for_home(get_hermes_home()) or '', cron_session='')
                    values[field] = ''
                    set_session_vars(**values)
                    with patch.dict('os.environ', {'HERMES_SESSION_' + {'session_id':'ID', 'session_key':'KEY',
                                         'chat_id':'CHAT_ID', 'user_id':'USER_ID'}[field]: ''}):
                        result = json.loads(self.service.request({'origin':'https://PRIVATE.invalid'}))
                    self.assertEqual(result, {'status':'unavailable', 'error_type':expected})
                contextvars.copy_context().run(run)
        self.service.store_factory.assert_not_called()
        self.assertIsNone(self.service.server)
        self.assertFalse(self.service.ids)
        self.assertFalse(self.service.broker.requests)

    def test_listener_bind_failure_is_fixed_and_issues_no_capability(self):
        import socket
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            self.service.port = listener.getsockname()[1]
            result = json.loads(self.service.request({'origin':'https://example.invalid'}))
        self.assertEqual(result, {'status':'unavailable', 'error_type':'listener_binding_failed'})
        self.assertFalse(self.service.ids)
        self.assertFalse(self.service.broker.requests)

    def test_unloaded_service_is_distinct_before_owner_acquisition(self):
        self.service.close()
        with patch('secure_entry.service.owner') as owner:
            result = json.loads(self.service.request({'origin':'https://PRIVATE.invalid'}))
        self.assertEqual(result, {'status':'unavailable', 'error_type':'service_unloaded'})
        owner.assert_not_called()

    def test_unexpected_exception_has_no_raw_text_or_request_fields(self):
        self.service.store_factory.side_effect = RuntimeError('PRIVATE-SECRET')
        result = json.loads(self.service.request({'origin':'https://PRIVATE.invalid', 'password':'PRIVATE-SECRET'}))
        self.assertEqual(result, {'status':'unavailable', 'error_type':'service_unavailable'})

    def test_bridge_missing_id_refuses_native_execution(self):
        self.service.configure_bridge(Mock(), 'in_process')
        called = Mock()
        def run():
            set_session_vars(platform='photon', chat_type='dm', chat_id='PRIVATE-CHAT',
                user_id='PRIVATE-USER', session_key='PRIVATE-KEY', session_id='', cron_session='')
            with patch.dict('os.environ', {'HERMES_SESSION_ID':''}):
                return self.service.middleware(tool_name='browser_vault', args={'action':'enter_code'},
                    next_call=called, session_id='PRIVATE-ID')
        result = json.loads(contextvars.copy_context().run(run))
        self.assertEqual(result, {'success':False, 'status':'unavailable', 'error_type':'missing_session_id'})
        called.assert_not_called()
        self.service.bridge.dispatch.assert_not_called()

    def test_bridge_listener_failure_survives_native_prompt_refusal(self):
        import socket
        from agent.vault_backends import unlock
        self.service.configure_bridge(Mock(), 'in_process')
        def native(args):
            self.assertIsNone(unlock.get_code_prompt_callback()('PRIVATE-SITE', 'PRIVATE-HINT'))
            return json.dumps({'success':False, 'error_type':'prompt_unavailable', 'error':'PRIVATE-SECRET'})
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            self.service.port = listener.getsockname()[1]
            result = json.loads(self.service.middleware(tool_name='browser_vault', args={'action':'enter_code'},
                next_call=native, session_id='PRIVATE-ID'))
        self.assertEqual(result, {'success':False, 'status':'refused', 'authenticated':False,
                                 'error_type':'listener_binding_failed'})
        self.service.bridge.dispatch.assert_not_called()
        self.assertFalse(self.service.broker.requests)
        self.assertIsNone(unlock.get_code_prompt_callback())

    def test_bridge_outer_failure_is_fixed_not_exception_text(self):
        self.service.configure_bridge(Mock(), 'in_process')
        called = Mock()
        with patch.object(self.service.bridge, 'middleware', side_effect=RuntimeError('PRIVATE-SECRET')):
            result = json.loads(self.service.middleware(tool_name='browser_vault', args={'action':'enter_code'}, next_call=called))
        self.assertEqual(result, {'success':False, 'status':'unavailable', 'error_type':'bridge_unavailable'})
        called.assert_not_called()

    def test_bridge_task_local_id_cannot_be_replaced_by_process_env(self):
        self.service.configure_bridge(Mock(), 'in_process')
        called = Mock()
        env = {'HERMES_SESSION_'+key:value for key,value in dict(PLATFORM='photon', CHAT_TYPE='dm',
            CHAT_ID='PRIVATE-CHAT', USER_ID='PRIVATE-USER', KEY='PRIVATE-KEY', ID='PRIVATE-ID').items()}
        with patch.dict('os.environ', env):
            result = json.loads(contextvars.Context().run(self.service.middleware,
                tool_name='browser_vault', args={'action':'enter_code'}, next_call=called, session_id='PRIVATE-ID'))
        self.assertEqual(result, {'success':False, 'status':'unavailable', 'error_type':'missing_session_binding'})
        called.assert_not_called()

    def test_bridge_other_admission_failure_has_fixed_category(self):
        self.service.configure_bridge(Mock(), 'in_process')
        called = Mock()
        result = json.loads(self.service.middleware(tool_name='browser_vault', args={'action':'enter_code'},
            next_call=called, session_id='WRONG-PRIVATE-ID'))
        self.assertEqual(result, {'success':False, 'status':'unavailable', 'error_type':'admission_unavailable'})
        called.assert_not_called()
        self.service.bridge.dispatch.assert_not_called()

    def test_bridge_unloaded_and_unconfigured_are_distinct(self):
        called = Mock()
        result = json.loads(self.service.middleware(tool_name='browser_vault', args={'action':'enter_code'}, next_call=called))
        self.assertEqual(result, {'success':False, 'status':'unavailable', 'error_type':'bridge_unavailable'})
        self.service.configure_bridge(Mock(), 'in_process')
        self.service.close()
        result = json.loads(self.service.middleware(tool_name='browser_vault', args={'action':'enter_code'}, next_call=called))
        self.assertEqual(result, {'success':False, 'status':'unavailable', 'error_type':'service_unloaded'})
        called.assert_not_called()
