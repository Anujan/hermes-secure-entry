import unittest
from urllib.parse import urlsplit


class BrokerTests(unittest.TestCase):
    def test_one_use_request_never_returns_secret(self):
        from secure_entry.broker import Broker
        broker = Broker('https://example.ts.net:9443')
        seen = []
        request = broker.issue('login', 'https://example.invalid', ('profile', 'session'),
                               lambda fields: seen.append(fields['password']) or {'status': 'saved'})
        page = broker.page(request.token)
        self.assertIn('autocomplete="current-password"', page)
        self.assertIn('for="password"', page)
        self.assertGreaterEqual(len(request.token), 43)
        self.assertNotEqual(request.token, request.csrf)
        result = broker.submit(request.token, {'csrf': request.csrf, 'identifier': 'synthetic-user',
                                                'password': 'SYNTHETIC-TEST-ONLY', 'action': 'submit'})
        self.assertEqual(result['status'], 'saved')
        self.assertEqual(seen, ['SYNTHETIC-TEST-ONLY'])
        self.assertNotIn('SYNTHETIC-TEST-ONLY', broker.page(request.token))
        self.assertEqual(broker.submit(request.token, {'csrf': request.csrf})['status'], 'saved')
        self.assertEqual(len(seen), 1)


    def test_cancel_cannot_acknowledge_before_an_inflight_action_commits(self):
        import threading
        from secure_entry.broker import Broker
        broker = Broker('https://example.ts.net:9443')
        started, proceed, cancelled = threading.Event(), threading.Event(), threading.Event()
        committed = []
        def apply(fields):
            started.set()
            proceed.wait(2)
            committed.append(True)
            return {'status': 'saved'}
        r = broker.issue('login', 'https://example.invalid', ('p','s'), apply)
        submit = threading.Thread(target=broker.submit, args=(r.token, {'csrf':r.csrf, 'identifier':'synthetic','password':'SYNTHETIC','action':'submit'}))
        submit.start()
        self.assertTrue(started.wait(2))
        def cancel():
            broker.cancel_owner(('p','s'))
            cancelled.set()
        stop = threading.Thread(target=cancel)
        stop.start()
        try:
            self.assertFalse(cancelled.wait(.05), 'Cancellation acknowledged while native side effect can still commit')
        finally:
            proceed.set()
            submit.join(2)
            stop.join(2)
        self.assertEqual(broker.status(r.token)['status'], 'saved')

    def test_bounded_retention_and_reject_oversize_fields(self):
        from secure_entry.broker import Broker
        broker = Broker('https://example.ts.net:9443', capacity=2)
        first = broker.issue('login', 'https://example.invalid', ('p','s'), lambda _: {'status':'saved'})
        broker.issue('code', 'https://example.invalid', ('p','s'), lambda _: {'status':'applied'})
        with self.assertRaises(ValueError):
            broker.issue('code', 'https://example.invalid', ('p','s'), lambda _: None)
        self.assertEqual(broker.submit(first.token, {'csrf':first.csrf, 'identifier':'x'*321,'password':'SYNTHETIC','action':'submit'})['status'], 'invalid_input')
        broker.cancel_owner(('p','s'))
        broker.issue('code', 'https://example.invalid', ('p','s'), lambda _: None)
        self.assertEqual(len(broker.requests), 2)

if __name__ == '__main__':
    unittest.main()
