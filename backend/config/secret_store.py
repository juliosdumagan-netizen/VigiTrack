"""
Camera credentials. A camera URL can contain a username and password (rtsp://user:pass@host).
On Windows the full URL is encrypted with DPAPI, which only the same Windows user can decrypt.
Anywhere the URL is shown or logged, the credentials are masked.
"""
import base64
import ctypes
import ctypes.wintypes as wintypes
import re
import sys

_CREDENTIALS = re.compile(r"(://)[^/@]+@")


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def is_url(source) -> bool:
    return isinstance(source, str) and "://" in source


def redact(source):
    """Masks any credentials in a URL, for display and logs. Other values are returned unchanged."""
    if isinstance(source, str):
        return _CREDENTIALS.sub(r"\1***@", source)
    return source


def _dpapi(data: bytes, protect: bool) -> bytes:
    if sys.platform != "win32":
        raise OSError("Camera credentials can only be encrypted on Windows (DPAPI).")
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    buffer = ctypes.create_string_buffer(data, len(data))
    in_blob = _Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    out_blob = _Blob()
    call = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    if not call(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
        raise OSError(f"Windows DPAPI call failed (error {kernel32.GetLastError()}).")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def encrypt_source(source: str) -> str:
    return base64.b64encode(_dpapi(source.encode("utf-8"), protect=True)).decode("ascii")


def decrypt_source(token: str) -> str:
    return _dpapi(base64.b64decode(token), protect=False).decode("utf-8")


def stored_camera_source(settings: dict):
    """Returns the real camera source for the capture code. Decrypts a stored URL if there is one."""
    token = settings.get("camera_source_secret")
    if token:
        return decrypt_source(token)
    return settings.get("camera_source", 0)


def store_camera_source(settings: dict, source) -> None:
    """Saves a camera source. URLs are encrypted, and the settings file keeps only a masked copy."""
    if is_url(source):
        settings["camera_source_secret"] = encrypt_source(source)
        settings["camera_source"] = redact(source)
    else:
        settings.pop("camera_source_secret", None)
        settings["camera_source"] = source
