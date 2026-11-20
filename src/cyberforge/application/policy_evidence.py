"""Machine-authorized Windows policy source for real learner information."""

import ctypes
import re
from ctypes import wintypes

from cyberforge.analytics.advisory_authorization import AdvisoryPolicyEvidenceV1

_MACHINE_KEY = r"SOFTWARE\Policies\CyberForge\TopicAdvisoryV1"
_TRUSTED_OWNERS = {"BA", "SY", "S-1-5-32-544", "S-1-5-18"}
_READ_ONLY_MASK = 0x20019


def trusted_registry_dacl(sddl: str) -> bool:
    owner, separator, acl = sddl.partition("D:")
    if not separator or not owner.startswith("O:") or owner[2:] not in _TRUSTED_OWNERS:
        return False
    flags, _, inner = acl.partition("(")
    if not re.fullmatch(r"(?:P|AR|AI)*", flags) or not inner:
        return False
    entries = re.findall(r"\(([^()]*)\)", "(" + inner)
    if "".join(f"({entry})" for entry in entries) != "(" + inner:
        return False
    for entry in entries:
        fields = entry.split(";")
        if len(fields) != 6:
            return False
        kind, ace_flags, rights, object_type, inherited_type, sid = fields
        if (
            kind not in {"A", "D"}
            or object_type
            or inherited_type
            or not re.fullmatch(r"(?:OI|CI|IO|ID|NP)*", ace_flags)
        ):
            return False
        if kind == "D" or "IO" in ace_flags or sid in _TRUSTED_OWNERS:
            continue
        if rights in {"KR", "GR"}:
            continue
        if re.fullmatch(r"0x[0-9a-fA-F]+", rights):
            if not int(rights, 16) & ~_READ_ONLY_MASK:
                continue
        return False
    return True


def _registry_sddl(handle: int) -> str:
    api = ctypes.WinDLL("advapi32", use_last_error=True)
    free = ctypes.WinDLL("kernel32").LocalFree
    pointer = ctypes.c_void_p
    pointer_ref = ctypes.POINTER(pointer)
    free.argtypes = (pointer,)
    free.restype = pointer
    get = api.GetSecurityInfo
    get.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        pointer_ref,
        pointer_ref,
        pointer_ref,
        pointer_ref,
        pointer_ref,
    )
    get.restype = wintypes.DWORD
    convert = api.ConvertSecurityDescriptorToStringSecurityDescriptorW
    convert.argtypes = (
        pointer,
        wintypes.DWORD,
        wintypes.DWORD,
        pointer_ref,
        ctypes.POINTER(wintypes.DWORD),
    )
    convert.restype = wintypes.BOOL
    security = pointer()
    result = pointer()
    status = get(handle, 4, 5, None, None, None, None, ctypes.byref(security))
    if status:
        raise ctypes.WinError(status)
    try:
        if not convert(security, 1, 5, ctypes.byref(result), None):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return ctypes.wstring_at(result)
        finally:
            free(result)
    finally:
        free(security)


class MachinePolicyEvidence:
    """Read the current machine policy on every check. The application has no writer."""

    def __call__(
        self, profile_id: str, scope_digest: str
    ) -> AdvisoryPolicyEvidenceV1 | None:
        import winreg

        if not re.fullmatch(r"[0-9a-f]{32}", profile_id) or not re.fullmatch(
            r"[0-9a-f]{64}", scope_digest
        ):
            return None
        name = profile_id + "-" + scope_digest
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                _MACHINE_KEY,
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            ) as key:
                if not trusted_registry_dacl(_registry_sddl(int(key))):
                    return None
                raw, kind = winreg.QueryValueEx(key, name)
            if kind != winreg.REG_SZ or len(raw) > 8192:
                return None
            return AdvisoryPolicyEvidenceV1.model_validate_json(raw)
        except (OSError, ValueError):
            return None
