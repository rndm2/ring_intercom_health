"""Temporary compatibility fixes for firebase-messaging."""

from __future__ import annotations

import importlib
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

_LOGGER = logging.getLogger(__name__)

_DECRYPT_PATCH_MARKER = "__ring_intercom_health_base64url_padding__"
_HEADER_PATCH_MARKER = "__ring_intercom_health_webpush_headers__"

type DecryptRawData = Callable[
    [dict[str, dict[str, str]], str, str, bytes],
    bytes,
]


def pad_base64url(value: str) -> str:
    """Restore omitted Base64URL padding."""

    return value + "=" * (-len(value) % 4)


def webpush_header_param(header: str, name: str) -> str:
    """Select and pad a named Web Push header parameter."""

    for segment in header.split(";"):
        parameter, separator, value = segment.strip().partition("=")
        if separator and parameter == name:
            return pad_base64url(value.strip())

    bare = header.strip()
    if "=" not in bare.rstrip("="):
        return pad_base64url(bare)
    raise ValueError(f"no {name!r} parameter in Web Push header")


def apply_firebase_messaging_compatibility_patch() -> bool:
    """Patch firebase-messaging Web Push header handling and decoding.

    Return True when this call installs at least one wrapper. Markers keep
    config-entry reloads and multiple watchdog entries from wrapping methods
    repeatedly.
    """

    try:
        module = importlib.import_module("firebase_messaging.fcmpushclient")
        client_class: Any = module.FcmPushClient
    except (AttributeError, ImportError):
        _LOGGER.debug(
            "firebase-messaging internals unavailable; compatibility patch skipped"
        )
        return False

    patched = False
    original_decrypt: DecryptRawData | None = getattr(
        client_class,
        "_decrypt_raw_data",
        None,
    )
    if original_decrypt is not None and not getattr(
        original_decrypt,
        _DECRYPT_PATCH_MARKER,
        False,
    ):
        @wraps(original_decrypt)
        def decrypt_raw_data(
            credentials: dict[str, dict[str, str]],
            crypto_key: str,
            salt: str,
            raw_data: bytes,
        ) -> bytes:
            return original_decrypt(
                credentials,
                pad_base64url(crypto_key),
                pad_base64url(salt),
                raw_data,
            )

        setattr(decrypt_raw_data, _DECRYPT_PATCH_MARKER, True)
        client_class._decrypt_raw_data = staticmethod(decrypt_raw_data)
        patched = True

    original_app_data: Callable[..., str] | None = getattr(
        client_class,
        "_app_data_by_key",
        None,
    )
    if original_app_data is not None and not getattr(
        original_app_data,
        _HEADER_PATCH_MARKER,
        False,
    ):
        @wraps(original_app_data)
        def app_data_by_key(
            client: Any,
            message: Any,
            key: str,
            do_not_raise: bool = False,
        ) -> str:
            value = original_app_data(client, message, key, do_not_raise)
            if not value:
                return value
            if key == "crypto-key":
                return f"dh={webpush_header_param(value, 'dh')}"
            if key == "encryption":
                return f"salt={webpush_header_param(value, 'salt')}"
            return value

        setattr(app_data_by_key, _HEADER_PATCH_MARKER, True)
        client_class._app_data_by_key = app_data_by_key
        patched = True

    if patched:
        _LOGGER.info("Applied firebase-messaging Web Push compatibility patch")
    return patched
