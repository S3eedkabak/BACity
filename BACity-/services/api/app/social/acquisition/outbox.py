"""Collector-owned, fsync-backed journal. No PostgreSQL or provider credentials.

One collector owns a volume. Undelivered work is never TTL-deleted or evicted.
"""
import argparse
import fcntl
import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import time
import uuid
from pathlib import Path

MAX_WORK_BYTES=12*1024*1024
MAX_MESSAGES=128
MIN_FREE_BYTES=32*1024*1024

class OutboxUnavailable(RuntimeError):pass


def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)

class Outbox:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.lock=os.open(str(self.path)+'.lock',os.O_CREAT|os.O_RDWR,0o600)
        try:fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            os.close(self.lock);raise OutboxUnavailable('Another collector owns the outbox') from None
        try:
            self.db=sqlite3.connect(self.path,timeout=5)
            os.chmod(self.path,0o600)
            self.db.executescript('''PRAGMA journal_mode=DELETE; PRAGMA synchronous=FULL;
                PRAGMA fullfsync=ON; PRAGMA secure_delete=ON; PRAGMA max_page_count=16384;
                CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS work(id TEXT PRIMARY KEY,data TEXT NOT NULL,created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,action TEXT NOT NULL,payload TEXT NOT NULL,
                    response TEXT,created REAL NOT NULL);''')
            if self.db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise OutboxUnavailable('Outbox integrity check failed')
            with self.db:self.db.execute('INSERT OR IGNORE INTO metadata VALUES(?,?)',('owner',secrets.token_urlsafe(32)))
            self.owner=self.db.execute('SELECT value FROM metadata WHERE key=?',('owner',)).fetchone()[0]
            directory=os.open(self.path.parent,os.O_RDONLY)
            try:os.fsync(directory)
            finally:os.close(directory)
        except Exception:
            os.close(self.lock);raise

    def close(self):self.db.close();os.close(self.lock)
    def load(self):
        row=self.db.execute('SELECT id,data FROM work LIMIT 1').fetchone()
        return (row[0],json.loads(row[1])) if row else (None,None)
    def capacity(self):
        if shutil.disk_usage(self.path.parent).free<MIN_FREE_BYTES:raise OutboxUnavailable('Outbox disk capacity low; acquisition paused')
    def save(self,data,identity=None):
        raw=encoded(data)
        if len(raw.encode())>MAX_WORK_BYTES:raise OutboxUnavailable('Outbox work limit reached; acquisition paused')
        self.capacity();current,_=self.load();identity=identity or current or str(uuid.uuid4())
        if current and current!=identity:raise OutboxUnavailable('Pending work must be delivered first')
        with self.db:self.db.execute('INSERT INTO work VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data',(identity,raw,time.time()))
        return identity
    def message(self,action,identity,owner,payload,*,stable=None,data_after=None):
        work_id,_=self.load()
        if not work_id:raise OutboxUnavailable('No authorized work journal')
        message_id=str(uuid.uuid5(uuid.UUID(work_id),stable)) if stable else str(uuid.uuid4())
        envelope={'id':message_id,'action':action,'identity':identity,'owner':owner,'payload':payload or {}}
        raw=encoded(envelope)
        if len(raw.encode())>65536:raise OutboxUnavailable('Delivery message exceeds gateway limit')
        old=self.db.execute('SELECT payload FROM messages WHERE id=?',(message_id,)).fetchone()
        if old:
            if old[0]!=raw:raise OutboxUnavailable('Journal message identity changed')
            return message_id
        if self.db.execute('SELECT count(*) FROM messages').fetchone()[0]>=MAX_MESSAGES:raise OutboxUnavailable('Outbox message capacity reached')
        self.capacity()
        with self.db:
            self.db.execute('INSERT INTO messages VALUES(?,?,?,?,?)',(message_id,action,raw,None,time.time()))
            if data_after is not None:
                updated=encoded(data_after)
                if len(updated.encode())>MAX_WORK_BYTES:raise OutboxUnavailable('Outbox work capacity reached')
                self.db.execute('UPDATE work SET data=? WHERE id=?',(updated,work_id))
        return message_id
    def response(self,identity):
        row=self.db.execute('SELECT response FROM messages WHERE id=?',(identity,)).fetchone()
        return json.loads(row[0]) if row and row[0] is not None else None
    def flush(self,send):
        for identity,raw in self.db.execute('SELECT id,payload FROM messages WHERE response IS NULL ORDER BY rowid').fetchall():
            response=send('/outbox/deliver',payload=json.loads(raw))
            # A response exists only after PostgreSQL commits receipt + staging.
            with self.db:self.db.execute('UPDATE messages SET response=? WHERE id=?',(encoded(response),identity))
    def online(self,send,action,identity,owner,payload,stable):
        message=self.message(action,identity,owner,payload,stable=stable)
        self.flush(send);response=self.response(message)
        if response is None:raise OutboxUnavailable('Delivery acknowledgement missing')
        return response
    def clear(self):
        if self.db.execute('SELECT 1 FROM messages WHERE response IS NULL LIMIT 1').fetchone():raise OutboxUnavailable('Undelivered data cannot be removed')
        with self.db:self.db.execute('DELETE FROM messages');self.db.execute('DELETE FROM work')
    def status(self):
        identity,data=self.load();row=self.db.execute('SELECT min(created),count(*) FROM messages WHERE response IS NULL').fetchone()
        return {'work_pending':bool(identity),'kind':data.get('kind') if data else None,'messages_pending':row[1],
            'oldest_pending_seconds':max(0,int(time.time()-row[0])) if row[0] else 0}


def main():
    parser=argparse.ArgumentParser(description='Read collector queue metadata; never prints captions or credentials')
    parser.add_argument('command',choices=['status']);parser.add_argument('--path',default=os.environ.get('SOCIAL_OUTBOX_PATH','/var/lib/bacity-outbox/outbox.sqlite3'))
    args=parser.parse_args();p=Path(args.path)
    db=sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True,timeout=5)
    assert db.execute('PRAGMA quick_check').fetchone()[0]=='ok'
    row=db.execute('SELECT min(created),count(*) FROM messages WHERE response IS NULL').fetchone()
    print(encoded({'work_pending':bool(db.execute('SELECT 1 FROM work').fetchone()),'messages_pending':row[1],
        'oldest_pending_seconds':max(0,int(time.time()-row[0])) if row[0] else 0,'integrity':'ok'}));db.close()

if __name__=='__main__':main()
