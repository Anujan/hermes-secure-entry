"""Windows private Link output inbox. No model-supplied file paths or stdout.

ACLs are established before Link creates the file, not repaired after a leak.
A no-sharing, no-follow, delete-on-close kernel handle consumes each file once.
"""

import json
import re
import secrets
from pathlib import Path
from urllib.parse import urlsplit
from contextlib import contextmanager


class PrivateFileRefused(ValueError):
    """Only fixed categories cross the private-artifact boundary."""

    CATEGORIES = frozenset({
        "closed", "windows_api", "directory_open", "directory_info",
        "directory_reparse", "windows_acl", "owner", "file_open", "file_info",
        "filetype", "linkcount", "size", "read", "json", "object",
        "request_match", "merchant_origin", "card_type", "card_number_type",
        "card_number_format", "cvc_type_format", "expiry_type_range",
        "billing_type", "billing_field_type", "billing_field_format",
        "private_file_failed",
    })

    def __init__(self, category):
        super().__init__("private_file_refused")
        self.category = category if category in self.CATEGORIES else "private_file_failed"


@contextmanager
def _handle(handle):
    try:
        yield handle
    finally:
        handle.Close()


def _windows():
    import win32api
    import win32con
    import win32file
    import win32security
    import pywintypes

    return win32api, win32con, win32file, win32security, pywintypes


def _identity():
    api, con, _, sec, _ = _windows()
    with _handle(
        sec.OpenProcessToken(api.GetCurrentProcess(), con.TOKEN_QUERY)
    ) as token:
        return sec.GetTokenInformation(token, sec.TokenUser)[0]


def _check_acl(handle):
    _, con, _, sec, _ = _windows()
    sd = sec.GetSecurityInfo(
        handle,
        sec.SE_FILE_OBJECT,
        sec.OWNER_SECURITY_INFORMATION | sec.DACL_SECURITY_INFORMATION,
    )
    allowed = {sec.ConvertSidToStringSid(_identity()), "S-1-5-18"}
    acl = sd.GetSecurityDescriptorDacl()
    if sec.ConvertSidToStringSid(sd.GetSecurityDescriptorOwner()) not in allowed:
        raise PrivateFileRefused("owner")
    if acl is None:
        raise PrivateFileRefused("windows_acl")
    for i in range(acl.GetAceCount()):
        header, mask, sid = acl.GetAce(i)
        if (
            header[0] != con.ACCESS_ALLOWED_ACE_TYPE
            or sec.ConvertSidToStringSid(sid) not in allowed
        ):
            raise PrivateFileRefused("windows_acl")


class PrivateCard:
    def __init__(self, root):
        self.directory = Path(root) / ("link-payment-" + secrets.token_hex(24))
        self.path = self.directory / "card.json"
        self.closed = False

    def __enter__(self):
        _, con, file, sec, types = _windows()
        acl = sec.ACL()
        flags = con.OBJECT_INHERIT_ACE | con.CONTAINER_INHERIT_ACE
        for sid in (_identity(), sec.ConvertStringSidToSid("S-1-5-18")):
            acl.AddAccessAllowedAceEx(sec.ACL_REVISION, flags, 0x1F01FF, sid)
        sd = sec.SECURITY_DESCRIPTOR()
        sd.SetSecurityDescriptorOwner(_identity(), False)
        sd.SetSecurityDescriptorDacl(True, acl, False)
        sd.SetSecurityDescriptorControl(sec.SE_DACL_PROTECTED, sec.SE_DACL_PROTECTED)
        attrs = types.SECURITY_ATTRIBUTES()
        attrs.SECURITY_DESCRIPTOR = sd
        file.CreateDirectory(str(self.directory), attrs)
        return self

    def consume(self, request_id, merchant_origin):
        category = "windows_api"
        try:
            _, con, file, _, _ = _windows()
            if self.closed:
                raise PrivateFileRefused("closed")
            category = "directory_open"
            with _handle(
                file.CreateFile(
                    str(self.directory),
                    con.READ_CONTROL,
                    0,
                    None,
                    con.OPEN_EXISTING,
                    con.FILE_FLAG_BACKUP_SEMANTICS | file.FILE_FLAG_OPEN_REPARSE_POINT,
                    None,
                )
            ) as directory:
                category = "directory_info"
                if (
                    file.GetFileInformationByHandle(directory)[0]
                    & con.FILE_ATTRIBUTE_REPARSE_POINT
                ):
                    raise PrivateFileRefused("directory_reparse")
                category = "windows_acl"
                _check_acl(directory)
                category = "file_open"
                with _handle(
                    file.CreateFile(
                        str(self.path),
                        con.GENERIC_READ | con.DELETE | con.READ_CONTROL,
                        0,
                        None,
                        con.OPEN_EXISTING,
                        file.FILE_FLAG_OPEN_REPARSE_POINT
                        | con.FILE_FLAG_DELETE_ON_CLOSE,
                        None,
                    )
                ) as handle:
                    category = "file_info"
                    info = file.GetFileInformationByHandle(handle)
                    category = "windows_acl"
                    _check_acl(handle)
                    if (
                        info[0]
                        & (
                            con.FILE_ATTRIBUTE_REPARSE_POINT
                            | con.FILE_ATTRIBUTE_DIRECTORY
                        )
                    ):
                        raise PrivateFileRefused("filetype")
                    if info[7] != 1:
                        raise PrivateFileRefused("linkcount")
                    if info[5] or info[6] > 16384:
                        raise PrivateFileRefused("size")
                    category = "read"
                    _, raw = file.ReadFile(handle, 16385)
                    category = "json"
                    data = json.loads(raw)
                    if not isinstance(data, dict):
                        raise PrivateFileRefused("object")
                    if data.get("spend_request_id") != request_id:
                        raise PrivateFileRefused("request_match")
                    category = "merchant_origin"
                    if _origin(data.get("merchant_url", "")) != merchant_origin:
                        raise PrivateFileRefused("merchant_origin")
                    card = data.get("card", {})
                    if not isinstance(card, dict):
                        raise PrivateFileRefused("card_type")
                    if not isinstance(card.get("number"), str):
                        raise PrivateFileRefused("card_number_type")
                    if not re.fullmatch(r"[0-9]{12,19}", card["number"]):
                        raise PrivateFileRefused("card_number_format")
                    if "cvc" in card and (
                        not isinstance(card["cvc"], str)
                        or not re.fullmatch(r"[0-9]{3,4}", card["cvc"])
                    ):
                        raise PrivateFileRefused("cvc_type_format")
                    if (
                        type(card.get("exp_month")) is not int
                        or not 1 <= card["exp_month"] <= 12
                        or type(card.get("exp_year")) is not int
                        or not 2026 <= card["exp_year"] <= 2100
                    ):
                        raise PrivateFileRefused("expiry_type_range")
                    result = {
                        k: card[k]
                        for k in ("number", "cvc", "exp_month", "exp_year")
                        if k in card
                    }
                    if "billing_address" in card:
                        billing = card["billing_address"]
                        if not isinstance(billing, dict):
                            raise PrivateFileRefused("billing_type")
                        if any(not isinstance(v, str) for v in billing.values()):
                            raise PrivateFileRefused("billing_field_type")
                        if any(
                            len(v) > 256
                            or any(ord(c) < 32 for c in v)
                            for v in billing.values()
                        ):
                            raise PrivateFileRefused("billing_field_format")
                        result["billing_address"] = {
                            k: v
                            for k, v in billing.items()
                            if k
                            in (
                                "name",
                                "line1",
                                "line2",
                                "city",
                                "state",
                                "postal_code",
                                "country",
                            )
                        }
                    return result
        except PrivateFileRefused:
            raise
        except Exception:
            raise PrivateFileRefused(category) from None

    def __exit__(self, *exc):
        self.closed = True
        self.path.unlink(missing_ok=True)
        self.directory.rmdir()


def _origin(url):
    p = urlsplit(url)
    if p.scheme != "https" or not p.hostname or p.username or p.password:
        raise ValueError("private_file_refused")
    return "https://" + p.netloc
