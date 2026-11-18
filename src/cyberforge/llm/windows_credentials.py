"""Win32 generic credentials scoped to a release channel and data profile."""

import ctypes
import re
from ctypes import wintypes

from pydantic import SecretStr

from cyberforge.llm.secret_store import CloudProvider, SecretStoreError

_GENERIC = 1
_LOCAL_MACHINE = 2
_NOT_FOUND = 1168


class _Credential(ctypes.Structure):
    _fields_ = [
        ("flags", wintypes.DWORD),
        ("kind", wintypes.DWORD),
        ("target", wintypes.LPWSTR),
        ("comment", wintypes.LPWSTR),
        ("written", wintypes.FILETIME),
        ("size", wintypes.DWORD),
        ("blob", ctypes.c_void_p),
        ("persist", wintypes.DWORD),
        ("attribute_count", wintypes.DWORD),
        ("attributes", ctypes.c_void_p),
        ("alias", wintypes.LPWSTR),
        ("username", wintypes.LPWSTR),
    ]


class WindowsCredentialStore:
    def __init__(self, channel: str, profile_id: str) -> None:
        if not re.fullmatch(r"[a-z0-9-]{1,24}", channel) or not re.fullmatch(
            r"[0-9a-f]{32}", profile_id
        ):
            raise ValueError("invalid_credential_namespace")
        self.prefix = f"CyberForge/{channel}/{profile_id}/"
        api = ctypes.WinDLL("advapi32", use_last_error=True)
        pointer = ctypes.POINTER(_Credential)
        self._read = api.CredReadW
        self._read.argtypes = (
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(pointer),
        )
        self._read.restype = wintypes.BOOL
        self._write = api.CredWriteW
        self._write.argtypes = (pointer, wintypes.DWORD)
        self._write.restype = wintypes.BOOL
        self._delete = api.CredDeleteW
        self._delete.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD)
        self._delete.restype = wintypes.BOOL
        self._free = api.CredFree
        self._free.argtypes = (ctypes.c_void_p,)
        self._free.restype = None

    def _target(self, provider: CloudProvider) -> str:
        if provider not in ("groq", "gemini"):
            raise SecretStoreError("vault_provider")
        return self.prefix + provider

    def read(self, provider: CloudProvider) -> SecretStr | None:
        result = ctypes.POINTER(_Credential)()
        if not self._read(self._target(provider), _GENERIC, 0, ctypes.byref(result)):
            if ctypes.get_last_error() == _NOT_FOUND:
                return None
            raise SecretStoreError("vault_read")
        try:
            credential = result.contents
            if not credential.blob or not 0 < credential.size <= 2560:
                raise SecretStoreError("vault_format")
            return SecretStr(
                ctypes.string_at(credential.blob, credential.size).decode("utf-8")
            )
        except UnicodeError:
            raise SecretStoreError("vault_format") from None
        finally:
            self._free(result)

    def write(self, provider: CloudProvider, secret: SecretStr) -> None:
        data = secret.get_secret_value().encode("utf-8")
        if not 0 < len(data) <= 2560:
            raise SecretStoreError("vault_format")
        buffer = ctypes.create_string_buffer(data, len(data))
        credential = _Credential(
            kind=_GENERIC,
            target=self._target(provider),
            size=len(data),
            blob=ctypes.addressof(buffer),
            persist=_LOCAL_MACHINE,
        )
        try:
            if not self._write(ctypes.byref(credential), 0):
                raise SecretStoreError("vault_write")
        finally:
            ctypes.memset(buffer, 0, len(data))

    def delete(self, provider: CloudProvider) -> None:
        if not self._delete(self._target(provider), _GENERIC, 0):
            if ctypes.get_last_error() != _NOT_FOUND:
                raise SecretStoreError("vault_delete")
