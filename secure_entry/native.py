"""Narrow native API adapter. Never resolves existing passwords or bypasses approval context."""
from pathlib import Path
from urllib.parse import urlsplit


class MissingSessionID(ValueError):
    pass


class MissingSessionBinding(ValueError):
    pass


def validate_origin(origin):
    from agent.vault_store import normalize_origin
    parsed = urlsplit(origin)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ('', '/')
            or normalize_origin(origin) != origin):
        raise ValueError('An exact HTTPS origin without path is required')
    return origin


def owner(expected_home):
    from hermes_constants import get_hermes_home
    from gateway.session_context import get_session_env
    from tools.approval_context import (_is_cron_approval_context, _is_single_query_approval_context,
                                        _is_unattended_platform_approval_context)
    from agent.delegation_context import is_delegated_child_context
    if (_is_cron_approval_context() or _is_single_query_approval_context()
            or _is_unattended_platform_approval_context() or is_delegated_child_context()):
        raise ValueError('Secure entry requires the originating human Photon conversation')
    home = str(Path(get_hermes_home()).resolve())
    values = tuple(get_session_env('HERMES_SESSION_' + key, '') for key in
                   ('PLATFORM', 'CHAT_TYPE', 'CHAT_ID', 'USER_ID', 'KEY', 'ID'))
    if (home != str(Path(expected_home).resolve()) or values[0] != 'photon'
            or values[1] != 'dm'):
        raise ValueError('Secure entry requires a bound Photon DM and matching profile')
    if not values[-1]:
        raise MissingSessionID('Missing session ID binding')
    if not all(values[2:]):
        raise MissingSessionBinding('Missing session binding')
    return (home, *values)


def dispatch_message(ctx, name, args):
    """Use native delivery, including snapshots without a registered send tool.

    The native CLI also calls send_message_tool directly. Select BEFORE sending,
    never retry another route after an ambiguous delivery error.
    """
    if name != 'send_message':
        raise ValueError('only native message delivery is supported')
    from tools.registry import registry
    if registry.get_entry(name) is not None:
        return ctx.dispatch_tool(name, args)
    from tools.send_message_tool import send_message_tool
    return send_message_tool(args)


def add_login(store, origin, fields):
    from agent.redact import register_vault_redaction_value
    validate_origin(origin)
    register_vault_redaction_value(fields['password'])
    identifier = fields['identifier'].strip()
    id_type = 'email' if '@' in identifier else 'phone' if identifier.lstrip('+').isdigit() else 'username'
    # Once native add begins, exceptions do not prove that no write occurred.
    result = {'status':'commit_unknown', 'identifier':identifier}
    try:
        meta = store.add_item('login', urlsplit(origin).netloc,
                              {'identifier': identifier, 'identifier_type': id_type, 'password': fields['password']}, origin=origin)
        result['handle'] = meta.id
        # Read back only metadata. Never resolve a secret to verify a write.
        saved = store.get_meta(meta.id)
        if saved and saved.origin == origin and saved.identifier == identifier:
            result['status'] = 'saved'
    except Exception:
        pass  # No secret-bearing exception text; never advise a blind retry.
    return result
