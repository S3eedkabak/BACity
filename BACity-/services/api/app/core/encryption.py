"""Server-side AEAD for unindexed private text. This is NOT end-to-end encryption."""
import base64
import json
import os
import re

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

PREFIX = 'bacity:aead:v1:'


class EncryptionError(RuntimeError):
    """Safe error: never include ciphertext, keys or plaintext in diagnostics."""


def keyring(config):
    try:
        values = json.loads(config.private_data_keys)
        if not isinstance(values, dict) or not values or len(values) > 10:
            raise ValueError()
        keys = {}
        for identifier, value in values.items():
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,32}', identifier) or not isinstance(value, str):
                raise ValueError()
            key = base64.b64decode(value, validate=True)
            if len(key) != 32:
                raise ValueError()
            keys[identifier] = key
        if config.private_data_active_key not in keys:
            raise ValueError()
        return keys
    except (ValueError, TypeError, AttributeError):
        raise EncryptionError('Invalid private-data encryption configuration') from None


def encrypt(value, context, config):
    if value is None:
        return None
    if not config.private_data_keys:
        if config.environment != 'development':
            raise EncryptionError('Private-data encryption is required')
        return value
    keys = keyring(config)
    identifier = config.private_data_active_key
    header = PREFIX + identifier + ':'
    nonce = os.urandom(12)
    ciphertext = AESGCM(keys[identifier]).encrypt(nonce, value.encode('utf-8'), (header + context).encode())
    return header + base64.b64encode(nonce + ciphertext).decode('ascii')


def decrypt(value, context, config):
    if value is None:
        return None
    if not value.startswith(PREFIX):
        # Backfill legacy rows explicitly while the app is stopped; never silently
        # accept plaintext once encryption is configured, even in development.
        if not config.private_data_keys and config.environment == 'development':
            return value
        raise EncryptionError('Legacy private data requires offline encryption backfill')
    try:
        identifier, encoded = value[len(PREFIX):].split(':', 1)
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) < 28:
            raise ValueError()
        header = PREFIX + identifier + ':'
        return AESGCM(keyring(config)[identifier]).decrypt(raw[:12], raw[12:], (header + context).encode()).decode('utf-8')
    except (ValueError, KeyError, InvalidTag, UnicodeError):
        raise EncryptionError('Private-data authentication failed') from None


class EncryptedText(TypeDecorator):
    """Preserves TEXT storage/API contracts; ORM consumers receive plaintext."""
    impl = Text
    cache_ok = True

    def __init__(self, context):
        super().__init__()
        self.context = context

    def process_bind_param(self, value, dialect):
        from app.config import get_settings
        return encrypt(value, self.context, get_settings())

    def process_result_value(self, value, dialect):
        from app.config import get_settings
        return decrypt(value, self.context, get_settings())
