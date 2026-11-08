"""Consistent SQLite backup. Run inside the worker's Docker filesystem."""
import argparse
import json
import os
import sqlite3
from pathlib import Path
from uuid import uuid4
from contextlib import closing


def backup(source, output):
    source=Path(source).resolve()
    output=Path(output).resolve()
    if source==output or output.exists():
        raise ValueError('Backup output must be a new file distinct from the source')
    temporary=output.with_name(output.name+'.partial-'+uuid4().hex)
    try:
        # Read-only URI prevents accidentally creating an empty source database.
        with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as incoming:
            with closing(sqlite3.connect(temporary)) as outgoing:
                incoming.backup(outgoing)
                if outgoing.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                    raise ValueError('Backup failed SQLite integrity check')
        # Exclusive atomic publication; never overwrite another backup.
        os.chmod(temporary,0o600)
        os.link(temporary,output)
        return {'path':str(output),'integrity':'ok','bytes':output.stat().st_size}
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',default=os.getenv('CRAWLER_STATE_PATH','crawler-state/state.db'))
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    print(json.dumps(backup(args.source,args.output)))


if __name__=='__main__':
    main()
