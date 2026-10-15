"""Owner isolation is shared by add-login, status, cancel, and bridge scopes."""
import contextvars
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from gateway.session_context import set_session_vars, reset_session_vars
from hermes_constants import get_hermes_home, profile_name_for_home
from agent.vault_store import VaultStore
from secure_entry.service import Service


class OwnerIsolationTests(unittest.TestCase):
    def bind(self, **changes):
        values = dict(platform='discord', chat_type='dm', chat_id='123456789012345678',
                      user_id='223456789012345678', session_key='synthetic-key',
                      session_id='synthetic-session', profile=profile_name_for_home(get_hermes_home()) or '',
                      cron_session='')
        values.update(changes)
        return set_session_vars(**values)

    def tearDown(self):
        reset_session_vars()

    def test_process_environment_alone_cannot_issue_add_login(self):
        env = {'HERMES_SESSION_' + k: v for k, v in dict(PLATFORM='photon', CHAT_TYPE='dm',
               CHAT_ID='synthetic-chat', USER_ID='synthetic-owner', KEY='synthetic-key', ID='synthetic-session').items()}
        service = Service('https://example.invalid', str(get_hermes_home()), port=0)
        self.addCleanup(service.close)
        def attempt():
            reset_session_vars()
            result = json.loads(service.request({'origin':'https://example.invalid'}))
            self.assertEqual(result.get('error_type'), 'missing_session_binding')
            self.assertFalse(service.broker.requests)
        with patch.dict(os.environ, env):
            contextvars.copy_context().run(attempt)

    def test_add_login_metadata_and_cancel_are_scoped_to_every_owner_component(self):
        for platform in ('photon', 'discord', 'telegram'):
            with self.subTest(platform=platform), tempfile.TemporaryDirectory() as folder:
                self.bind(platform=platform)
                store = VaultStore(Path(folder))
                service = Service('https://example.invalid', str(get_hermes_home()), port=0, store_factory=lambda: store)
                try:
                    result = json.loads(service.request({'origin':'https://example.invalid'}))
                    self.assertEqual(result['status'], 'pending')
                    rid = {'request_id':result['request_id']}
                    for changes in ({'platform':other} for other in ('photon','discord','telegram') if other != platform):
                        self.assert_inaccessible(service, rid, changes)
                    for changes in ({'chat_id':'different-chat'}, {'user_id':'different-user'},
                                    {'session_key':'different-key'}, {'session_id':'different-session'},
                                    {'profile':'different-profile'}, {'chat_type':'group'}, {'cron_session':'1'}):
                        self.assert_inaccessible(service, rid, changes)
                    self.assertEqual(json.loads(service.status(rid))['status'], 'pending')
                    self.assertEqual(json.loads(service.cancel(rid))['status'], 'cancelled')
                finally:
                    service.close()

    def assert_inaccessible(self, service, rid, changes):
        from gateway.session_context import get_session_env
        values = {name: get_session_env('HERMES_SESSION_' + key, '') for name, key in
                  (('platform','PLATFORM'), ('chat_type','CHAT_TYPE'), ('chat_id','CHAT_ID'),
                   ('user_id','USER_ID'), ('session_key','KEY'), ('session_id','ID'), ('profile','PROFILE'))}
        values.update(changes)
        def attempt():
            self.bind(**values)
            self.assertEqual(json.loads(service.status(rid))['status'], 'unavailable')
            self.assertEqual(json.loads(service.cancel(rid))['status'], 'unavailable')
        contextvars.copy_context().run(attempt)

    def test_unenumerated_transports_and_non_dm_chats_never_collect(self):
        for changes in ([{'platform':p} for p in ('slack','signal','whatsapp','matrix','email','api_server','webhook','unknown','Discord')]
                        + [{'chat_type':t} for t in ('group','channel','thread','forum','', 'private')]):
            def attempt():
                self.bind(**changes)
                service = Service('https://example.invalid', str(get_hermes_home()), port=0)
                try:
                    result = json.loads(service.request({'origin':'https://example.invalid'}))
                    self.assertNotIn('url', result)
                    self.assertIsNone(service.server)
                finally:
                    service.close()
            with self.subTest(changes=changes):
                contextvars.copy_context().run(attempt)
