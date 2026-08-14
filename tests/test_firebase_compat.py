"""Tests for firebase-messaging compatibility helpers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest import TestCase
from unittest.mock import patch

MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "ring_intercom_health"
    / "firebase_compat.py"
)
SPEC = importlib.util.spec_from_file_location(
    "ring_intercom_health_firebase_compat",
    MODULE_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None
firebase_compat = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(firebase_compat)


class FirebaseCompatTest(TestCase):
    """Test firebase-messaging compatibility helpers."""

    def test_pad_base64url(self) -> None:
        """Padding is added only when necessary."""

        self.assertEqual(firebase_compat.pad_base64url("YWJjZA"), "YWJjZA==")
        self.assertEqual(firebase_compat.pad_base64url("YWJjZA="), "YWJjZA==")
        self.assertEqual(firebase_compat.pad_base64url("YWJjZA=="), "YWJjZA==")

    def test_webpush_header_param(self) -> None:
        """Named, reordered, bare, and unpadded values are normalized."""

        self.assertEqual(
            firebase_compat.webpush_header_param(
                "p256ecdsa=CCCC; dh=AAA",
                "dh",
            ),
            "AAA=",
        )
        self.assertEqual(firebase_compat.webpush_header_param("BB", "salt"), "BB==")
        with self.assertRaisesRegex(ValueError, "no 'dh' parameter"):
            firebase_compat.webpush_header_param("p256ecdsa=CCCC", "dh")

    def test_apply_firebase_messaging_patch_is_idempotent(self) -> None:
        """Wrappers normalize headers and decoding inputs only once."""

        calls: list[tuple[object, str, str, bytes]] = []

        class FakeFcmPushClient:
            @staticmethod
            def _decrypt_raw_data(
                credentials: object,
                crypto_key: str,
                salt: str,
                raw_data: bytes,
            ) -> bytes:
                calls.append((credentials, crypto_key, salt, raw_data))
                return raw_data

            def _app_data_by_key(
                self,
                message: dict[str, str],
                key: str,
                do_not_raise: bool = False,
            ) -> str:
                if do_not_raise:
                    return message.get(key, "")
                return message[key]

        package = ModuleType("firebase_messaging")
        module = ModuleType("firebase_messaging.fcmpushclient")
        module.FcmPushClient = FakeFcmPushClient

        with patch.dict(
            sys.modules,
            {
                "firebase_messaging": package,
                "firebase_messaging.fcmpushclient": module,
            },
        ):
            self.assertTrue(
                firebase_compat.apply_firebase_messaging_compatibility_patch()
            )
            self.assertFalse(
                firebase_compat.apply_firebase_messaging_compatibility_patch()
            )

            client = FakeFcmPushClient()
            crypto_header = client._app_data_by_key(
                {"crypto-key": "p256ecdsa=VkFQSUQ; dh=Y3J5cHRvLWtleQ"},
                "crypto-key",
            )
            salt_header = client._app_data_by_key(
                {"encryption": "salt=c2FsdA"},
                "encryption",
            )

            self.assertEqual(crypto_header, "dh=Y3J5cHRvLWtleQ==")
            self.assertEqual(salt_header, "salt=c2FsdA==")

            credentials = {"keys": {"private": "key", "secret": "secret"}}
            result = FakeFcmPushClient._decrypt_raw_data(
                credentials,
                "Y3J5cHRvLWtleQ",
                "c2FsdA",
                b"ciphertext",
            )

        self.assertEqual(result, b"ciphertext")
        self.assertEqual(
            calls,
            [(credentials, "Y3J5cHRvLWtleQ==", "c2FsdA==", b"ciphertext")],
        )
