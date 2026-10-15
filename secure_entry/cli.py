"""Explicit local operator helpers; never starts or restarts Hermes or Tailscale."""
import argparse
import json
from pathlib import Path
import tempfile
import threading
import urllib.request
from .broker import Broker
from .native import add_login
from .server import Server
from .service import BLOCKERS


def diagnose():
    from agent.vault_store import VaultStore
    print(json.dumps({'version':'0.2.0','core_overrides':False,'browser_prompts':'native_callback_preview',
                      'native_vault_available':callable(getattr(VaultStore, 'add_item', None)),
                      'missing_contracts':['native_atomic_update','native_transient_password','native_exact_target_commit'],
                      'requires_isolation':'in_process', 'otp_handles':'unsupported_handle_binding',
                      'operations':{'add_login':'supported', 'verification_code':'native_tool_required',
                                    **{k:'unsupported' for k in BLOCKERS}}}))


def demo_action(store, fields):
    if fields != {'identifier':'synthetic@example.invalid','password':'SYNTHETIC-DEMO-ONLY'}:
        return {'status':'failed'}
    return add_login(store, 'https://example.invalid', fields)


def demo(base, port, seconds):
    from agent.vault_store import VaultStore
    with tempfile.TemporaryDirectory(prefix='secure-entry-demo-') as folder:
        store = VaultStore(Path(folder))
        broker = Broker(base)
        request = broker.issue('login', 'https://example.invalid', ('synthetic-profile','synthetic-session'),
                               lambda fields: demo_action(store, fields))
        with Server(broker, port=port):
            print(json.dumps({'mode':'synthetic-only-native-vault-demo','url':broker.url(request),
                              'identifier':'synthetic@example.invalid','password':'SYNTHETIC-DEMO-ONLY',
                              'seconds':seconds,'note':'No live vault. No browser fill. Exits automatically.'}), flush=True)
            threading.Event().wait(seconds)
            print(json.dumps({'demo_final_status':broker.status(request.token)['status'],
                              'synthetic_native_records':len(store.list_items())}), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('diagnose')
    d = sub.add_parser('demo')
    d.add_argument('--public-base-url', default='https://example.invalid:9443')
    d.add_argument('--port', type=int, default=8769)
    d.add_argument('--seconds', type=int, default=600)
    h = sub.add_parser('health')
    h.add_argument('--port', type=int, default=8769)
    args = parser.parse_args(argv)
    if args.command == 'diagnose':
        diagnose()
    elif args.command == 'demo':
        if not 1 <= args.seconds <= 600:
            parser.error('--seconds must be in 1..600')
        demo(args.public_base_url, args.port, args.seconds)
    elif args.command == 'health':
        with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/health', timeout=3) as response:
            print(response.read().decode())


if __name__ == '__main__':
    main()
