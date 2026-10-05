"""Offline, bounded, resumable private-data backfill/rotation. Default is verify-only."""
import argparse
from sqlalchemy import text
from app.config import get_settings
from app.core.encryption import PREFIX, decrypt, encrypt, keyring
from app.database import engine

FIELDS = (
    ('messages', 'body'), ('mail_outbox', 'body'),
    ('consumer_subscriptions', 'provider_purchase_token'),
)


def process_private_data(connection, config, *, apply=False, rotate=False):
    keyring(config)  # Never allow a plaintext-writing backfill.
    counts = {'checked': 0, 'legacy': 0, 'changed': 0}
    for table, column in FIELDS:
        # Identifiers are constants, never user input. Keyset pages bound memory.
        last = None
        while True:
            where = f'{column} IS NOT NULL' + (' AND id > :last' if last else '')
            rows = connection.execute(text(f'SELECT id, {column} FROM {table} WHERE {where} ORDER BY id LIMIT 100'),
                                      {'last': last} if last else {}).all()
            if not rows:
                break
            for identifier, value in rows:
                counts['checked'] += 1
                legacy = not value.startswith(PREFIX)
                counts['legacy'] += int(legacy)
                clear = value if legacy else decrypt(value, f'{table}.{column}', config)
                active = value.startswith(PREFIX + config.private_data_active_key + ':')
                if apply and (legacy or (rotate and not active)):
                    connection.execute(text(f'UPDATE {table} SET {column} = :value WHERE id = :id'),
                                       {'id': identifier, 'value': encrypt(clear, f'{table}.{column}', config)})
                    counts['changed'] += 1
            last = rows[-1][0]
            if apply:
                connection.commit()
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Encrypt legacy rows; stop API/workers first')
    parser.add_argument('--rotate', action='store_true', help='Also rewrite old-key ciphertext; requires --apply')
    args = parser.parse_args()
    if args.rotate and not args.apply:
        parser.error('--rotate requires --apply')
    with engine.connect() as connection:
        result = process_private_data(connection, get_settings(), apply=args.apply, rotate=args.rotate)
    print(result)  # Counts only; never IDs, bodies, credentials or keys.
    if not args.apply and result['legacy']:
        raise SystemExit('Legacy rows remain; offline backfill is required before serving encrypted data')


if __name__ == '__main__':
    main()
