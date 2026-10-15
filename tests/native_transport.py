"""Network-only fakes for native one-shot bot senders; never contact a service."""
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest.mock import patch


@contextmanager
def synthetic_bot_network(platform, deliver):
    with ExitStack() as stack:
        if platform == 'discord':
            class Response:
                status = 200
                content = None
                async def __aenter__(self): return self
                async def __aexit__(self, *args): pass
                async def json(self): return {'id': 'synthetic-message-id', 'type': 1}
            class Session:
                def __init__(self, *args, **kwargs): pass
                async def __aenter__(self): return self
                async def __aexit__(self, *args): pass
                def get(self, url, **kwargs): return Response()
                def post(self, url, **kwargs):
                    class Sent(Response):
                        async def __aenter__(self):
                            chat_id = url.split('/channels/', 1)[1].split('/', 1)[0]
                            await deliver(chat_id=chat_id, content=kwargs['json']['content'])
                            return self
                    return Sent()
            stack.enter_context(patch('aiohttp.ClientSession', Session))
        elif platform == 'telegram':
            class Bot:
                async def send_message(self, **kwargs):
                    import re
                    text = re.sub(r'\\(.)', r'\1', kwargs['text'])
                    await deliver(chat_id=str(kwargs['chat_id']), content=text)
                    return SimpleNamespace(message_id='synthetic-message-id')
            stack.enter_context(patch('tools.send_message_senders._telegram_bot', return_value=Bot()))
        yield
