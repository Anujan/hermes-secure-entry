import contextlib
import io
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from secure_entry.broker import Broker


class HTTPTests(unittest.TestCase):
    def test_loopback_http_with_private_post_and_security_headers(self):
        from secure_entry.server import Server
        broker = Broker('https://example.ts.net:9443')
        r = broker.issue('code', 'https://example.invalid', ('p', 's'), lambda f: {'status': 'applied'})
        with Server(broker, port=0) as server, contextlib.redirect_stderr(io.StringIO()) as logs:
            root = 'http://127.0.0.1:' + str(server.port)
            with urllib.request.urlopen(root + '/health') as response:
                self.assertEqual(response.read(), b'{"status":"ok","version":"0.1.0"}')
            path = root + '/r/' + r.token
            with urllib.request.urlopen(path) as response:
                page = response.read().decode()
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
                self.assertEqual(response.headers['Referrer-Policy'], 'no-referrer')
                self.assertIn("default-src 'none'", response.headers['Content-Security-Policy'])
                self.assertIn('autocomplete="one-time-code"', page)
            data = urllib.parse.urlencode({'csrf': r.csrf, 'code': 'SYNTHETIC-CODE', 'action': 'submit'}).encode()
            with urllib.request.urlopen(urllib.request.Request(path, data=data, headers={'Origin': 'null'})) as response:
                self.assertNotIn(b'SYNTHETIC-CODE', response.read())
            self.assertEqual(broker.status(r.token)['status'], 'applied')
            self.assertEqual(logs.getvalue(), '')
        with self.assertRaises(ValueError):
            Server(broker, host='0.0.0.0')

    def test_rejects_dns_rebinding_duplicate_fields_oversized_body_and_csrf(self):
        from secure_entry.server import Server
        import http.client
        broker = Broker('https://example.ts.net:9443')
        r = broker.issue('code', 'https://example.invalid', ('p','s'), lambda _: self.fail('invalid request applied'))
        with Server(broker, port=0) as server:
            path = '/r/' + r.token
            cases = [
                ('GET', path, None, {'Host':'attacker.invalid'}, 421),
                ('GET', path + '?leak=x', None, {}, 404),
                ('POST', path, 'x', {'Content-Length':'16385','Content-Type':'application/x-www-form-urlencoded'}, 400),
                ('POST', path, 'csrf=a&csrf=b&code=SYNTHETIC&action=submit', {'Content-Type':'application/x-www-form-urlencoded'}, 400),
                ('POST', path, 'csrf=bad&code=SYNTHETIC&action=submit', {'Content-Type':'application/x-www-form-urlencoded'}, 403),
            ]
            for method, url, data, headers, expected in cases:
                connection = http.client.HTTPConnection('127.0.0.1', server.port, timeout=2)
                connection.request(method, url, body=data, headers=headers)
                response = connection.getresponse()
                self.assertEqual(response.status, expected)
                response.read()
                connection.close()
        self.assertEqual(broker.status(r.token)['status'], 'cancelled')

    def test_csrf_expiry_cancellation_failure_and_concurrent_replay(self):
        now = [0]
        broker = Broker('https://example.ts.net:9443', clock=lambda: now[0])
        calls = []
        r = broker.issue('code', 'https://example.invalid', ('p','s'), lambda f: calls.append(1) or {'status':'applied'})
        self.assertEqual(broker.submit(r.token, {'csrf':'bad'})['status'], 'csrf_rejected')
        fields = {'csrf':r.csrf, 'code':'SYNTHETIC', 'action':'submit'}
        threads = [threading.Thread(target=broker.submit, args=(r.token, fields)) for _ in range(12)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(calls, [1])
        r = broker.issue('code', 'https://example.invalid', ('p','s'), lambda _: self.fail('expired action'))
        now[0] = 601
        self.assertEqual(broker.submit(r.token, {'csrf':r.csrf})['status'], 'expired')
        r = broker.issue('code', 'https://example.invalid', ('p','s'), lambda _: self.fail('cancelled action'))
        self.assertEqual(broker.submit(r.token, {'csrf':r.csrf, 'action':'cancel'})['status'], 'cancelled')
        def fail(_): raise RuntimeError('SYNTHETIC-SECRET-IN-ERROR')
        r = broker.issue('code', 'https://example.invalid', ('p','s'), fail)
        self.assertEqual(broker.submit(r.token, {'csrf':r.csrf, 'code':'SYNTHETIC', 'action':'submit'}), {'status':'failed'})
        self.assertNotIn('SYNTHETIC-SECRET-IN-ERROR', broker.page(r.token))
