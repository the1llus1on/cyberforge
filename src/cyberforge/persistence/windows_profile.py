"""Native ACL enforcement for the Windows application data profile."""

import ctypes
import re
from collections.abc import Iterator
from contextlib import contextmanager
from ctypes import wintypes
from pathlib import Path
from typing import BinaryIO

_READ_OWNER_DACL = 0x05
_SE_FILE_OBJECT = 1
_TOKEN_QUERY = 8
_TOKEN_USER = 1
_ERROR_ALREADY_EXISTS = 183
_FULL_ACCESS = 0x1F01FF
_REPARSE_POINT = 0x400
_PTR = ctypes.c_void_p
_PPTR = ctypes.POINTER(_PTR)
_DWORD = wintypes.DWORD
_PD = ctypes.POINTER(_DWORD)
_BOOL = wintypes.BOOL
_HANDLE = wintypes.HANDLE
_WSTR = wintypes.LPCWSTR


class _SecurityAttributes(ctypes.Structure):
    _fields_ = [
        ("length", _DWORD),
        ("descriptor", _PTR),
        ("inherit_handle", _BOOL),
    ]


class _RenameInfo(ctypes.Structure):
    _fields_ = [
        ("flags", _DWORD),
        ("root", _HANDLE),
        ("name_bytes", _DWORD),
        ("name", wintypes.WCHAR * 1),
    ]


def _function(library, name, result, *arguments):
    call = getattr(library, name)
    call.restype = result
    call.argtypes = arguments
    return call


class WindowsProfileSecurity:
    def __init__(self) -> None:
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.security = ctypes.WinDLL("advapi32", use_last_error=True)
        self.close = _function(self.kernel, "CloseHandle", _BOOL, _HANDLE)
        self.free = _function(self.kernel, "LocalFree", _PTR, _PTR)
        self.open_file = _function(
            self.kernel,
            "CreateFileW",
            _HANDLE,
            _WSTR,
            _DWORD,
            _DWORD,
            _PTR,
            _DWORD,
            _DWORD,
            _HANDLE,
        )
        self.sid = self._current_sid()

    def _current_sid(self) -> str:
        process = _function(self.kernel, "GetCurrentProcess", _HANDLE)()
        open_token = _function(
            self.security, "OpenProcessToken", _BOOL, _HANDLE, _DWORD, _PPTR
        )
        read_token = _function(
            self.security,
            "GetTokenInformation",
            _BOOL,
            _HANDLE,
            _DWORD,
            _PTR,
            _DWORD,
            _PD,
        )
        token = _PTR()
        if not open_token(process, _TOKEN_QUERY, ctypes.byref(token)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            length = _DWORD()
            read_token(token, _TOKEN_USER, None, 0, ctypes.byref(length))
            buffer = ctypes.create_string_buffer(length.value)
            if not read_token(token, _TOKEN_USER, buffer, length, ctypes.byref(length)):
                raise ctypes.WinError(ctypes.get_last_error())
            sid = ctypes.cast(buffer, _PPTR)[0]
            to_string = _function(
                self.security, "ConvertSidToStringSidW", _BOOL, _PTR, _PPTR
            )
            result = _PTR()
            if not to_string(sid, ctypes.byref(result)):
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                return ctypes.wstring_at(result)
            finally:
                self.free(result)
        finally:
            self.close(token)

    def create_root(self, path: Path) -> None:
        descriptor = _PTR()
        parse = _function(
            self.security,
            "ConvertStringSecurityDescriptorToSecurityDescriptorW",
            _BOOL,
            _WSTR,
            _DWORD,
            _PPTR,
            _PD,
        )
        sddl = (
            f"O:{self.sid}D:P(A;OICI;FA;;;{self.sid})(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)"
        )
        if not parse(sddl, 1, ctypes.byref(descriptor), None):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            create = _function(
                self.kernel,
                "CreateDirectoryW",
                _BOOL,
                _WSTR,
                ctypes.POINTER(_SecurityAttributes),
            )
            attrs = _SecurityAttributes(
                ctypes.sizeof(_SecurityAttributes), descriptor, False
            )
            if not create(str(path), ctypes.byref(attrs)):
                error = ctypes.get_last_error()
                if error != _ERROR_ALREADY_EXISTS:
                    raise ctypes.WinError(error)
        finally:
            self.free(descriptor)

    def _descriptor(self, path: Path) -> str:
        read = _function(
            self.security,
            "GetNamedSecurityInfoW",
            _DWORD,
            _WSTR,
            _DWORD,
            _DWORD,
            _PPTR,
            _PPTR,
            _PPTR,
            _PPTR,
            _PPTR,
        )
        convert = _function(
            self.security,
            "ConvertSecurityDescriptorToStringSecurityDescriptorW",
            _BOOL,
            _PTR,
            _DWORD,
            _DWORD,
            _PPTR,
            _PD,
        )
        security = _PTR()
        status = read(
            str(path),
            _SE_FILE_OBJECT,
            _READ_OWNER_DACL,
            None,
            None,
            None,
            None,
            ctypes.byref(security),
        )
        if status:
            raise ctypes.WinError(status)
        try:
            result = _PTR()
            if not convert(security, 1, _READ_OWNER_DACL, ctypes.byref(result), None):
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                return ctypes.wstring_at(result)
            finally:
                self.free(result)
        finally:
            self.free(security)

    def validate(self, path: Path, *, directory: bool) -> None:
        if not valid_descriptor(self._descriptor(path), self.sid, directory=directory):
            raise PermissionError("Небезпечні дозволи приватного профілю Windows.")

    @contextmanager
    def lock_for_replacement(self, path: Path) -> Iterator[BinaryIO]:
        """Allow replacement while keeping legacy SQLite readers and writers out."""
        import msvcrt

        # GENERIC_READ, FILE_SHARE_DELETE, OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT.
        handle = self.open_file(str(path), 0x80000000, 4, None, 3, 0x00200000, None)
        if handle == _PTR(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            fd = msvcrt.open_osfhandle(handle, 0)
        except OSError:
            self.close(handle)
            raise
        with open(fd, "rb") as stream:
            yield stream

    def replace(self, source: Path, target: Path) -> None:
        """Rename over the old name while holding its read-only exclusion handle."""
        rename = _function(
            self.kernel,
            "SetFileInformationByHandle",
            _BOOL,
            _HANDLE,
            _DWORD,
            _PTR,
            _DWORD,
        )
        target_bytes = str(target).encode("utf-16-le")
        size = _RenameInfo.name.offset + len(target_bytes) + 2
        buffer = ctypes.create_string_buffer(size)
        header = _RenameInfo.from_buffer(buffer)
        # FILE_RENAME_REPLACE_IF_EXISTS | FILE_RENAME_POSIX_SEMANTICS.
        header.flags = 3
        header.name_bytes = len(target_bytes)
        ctypes.memmove(
            ctypes.addressof(buffer) + _RenameInfo.name.offset,
            target_bytes,
            len(target_bytes),
        )
        # DELETE, all sharing modes, OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT.
        handle = self.open_file(str(source), 0x10000, 7, None, 3, 0x00200000, None)
        if handle == _PTR(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not rename(handle, 22, buffer, size):  # FileRenameInfoEx
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            self.close(handle)


def valid_descriptor(descriptor: str, sid: str, *, directory: bool) -> bool:
    """Check owner, effective access and inheritable directory access."""
    owner, separator, dacl = descriptor.partition("D:")
    if not separator or owner != f"O:{sid}":
        return False
    flags, _, entries = dacl.partition("(")
    if not re.fullmatch(r"(?:P|AI|AR)*", flags) or not entries:
        return False
    all_entries = "(" + entries
    entries = re.findall(r"\(([^()]*)\)", all_entries)
    if "".join(f"({entry})" for entry in entries) != all_entries:
        return False
    aliases = {"S-1-5-18": "SY", "S-1-5-32-544": "BA"}
    principals = {sid, "SY", "BA"}
    effective = set()
    inherited = set()
    for entry in entries:
        parts = entry.split(";")
        if len(parts) != 6:
            return False
        kind, ace_flags, rights, object_type, inherited_type, principal = parts
        principal = aliases.get(principal, principal)
        if (
            kind != "A"
            or principal not in principals
            or object_type
            or inherited_type
            or not re.fullmatch(r"(?:OI|CI|IO|ID|NP)*", ace_flags)
        ):
            return False
        full_access = rights == "FA" or (
            rights.startswith("0x") and int(rights, 16) == _FULL_ACCESS
        )
        if full_access and "IO" not in ace_flags:
            effective.add(principal)
        if (
            directory
            and full_access
            and all(flag in ace_flags for flag in ("OI", "CI"))
        ):
            if "NP" not in ace_flags:
                inherited.add(principal)
    return effective == principals and (not directory or inherited == principals)
