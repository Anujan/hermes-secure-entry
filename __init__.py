"""Windows-native Hermes secure-entry plugin. No core overrides or startup sockets."""
from .secure_entry.service import Service


def register(ctx):
    from hermes_constants import get_hermes_home
    service = Service(ctx.get_config('public_base_url', default='https://example.invalid:9443'),
                      str(get_hermes_home()), port=ctx.get_config('port', default=8769))
    definitions = [
        ('secure_entry_request', service.request,
         'Request a private one-use form to ADD a website login to the native encrypted Hermes vault without a browser. '
         'Photon DM only. Does not sign in. Update, transient sign-in, save-and-sign-in, and verification-code operations '
         'currently return unsupported_native_contract WITHOUT collecting secrets. Never pass credentials in tool arguments.',
         {'operation': {'type':'string', 'enum':['add_login','update_login','sign_in_once','save_and_sign_in','verification_code']},
          'origin': {'type':'string','description':'Exact HTTPS website origin, without path or trailing slash. Visible to the user before entry.'}},
         ['operation','origin']),
        ('secure_entry_status', service.status, 'Read metadata-only request status in the same originating Photon DM session.',
         {'request_id':{'type':'string'}}, ['request_id']),
        ('secure_entry_cancel', service.cancel, 'Cancel a pending secure-entry request in the same originating Photon DM session.',
         {'request_id':{'type':'string'}}, ['request_id']),
    ]
    for name, handler, description, properties, required in definitions:
        ctx.register_tool(name=name, toolset='secure_entry', handler=handler,
                          schema={'name':name, 'description':description,
                                  'parameters':{'type':'object','properties':properties,'required':required,'additionalProperties':False}})
    ctx.register_hook('agent_loop_stopped', service.stopped)
    ctx.register_hook('on_session_end', service.ended)
    ctx.register_hook('on_session_reset', service.reset)
    ctx.on_unload(service.close)
