"""Local single-operator SQLite review history. Brand scoping is NOT authentication."""
import json
from contextlib import contextmanager
import sqlite3
from datetime import datetime,timezone
from uuid import uuid4
from pathlib import Path


@contextmanager
def connect(path):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(path)
    con.execute('PRAGMA foreign_keys=ON')
    con.execute('CREATE TABLE IF NOT EXISTS snapshots (id TEXT PRIMARY KEY, brand_id TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL)')
    con.execute('CREATE TABLE IF NOT EXISTS decisions (id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL REFERENCES snapshots(id), brand_id TEXT NOT NULL, created_at TEXT NOT NULL, reviewer TEXT NOT NULL, decision TEXT NOT NULL, reason TEXT NOT NULL)')
    try:
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()


def save_snapshot(path,brand_id,payload):
    if payload.get('bundle',{}).get('brand',{}).get('brand_id')!=brand_id:
        raise ValueError('Snapshot brand mismatch.')
    # Serialize only known fields; never accept an API-key-bearing request object.
    permitted={k:payload[k] for k in ['bundle','reviews','coordinator'] if k in payload}
    sid=str(uuid4())
    with connect(path) as con:
        con.execute('INSERT INTO snapshots VALUES (?,?,?,?)',(sid,brand_id,datetime.now(timezone.utc).isoformat(),json.dumps(permitted)))
    return sid


def list_snapshots(path,brand_id):
    with connect(path) as con:
        return [{'id':r[0],'created_at':r[1]} for r in con.execute('SELECT id,created_at FROM snapshots WHERE brand_id=? ORDER BY created_at DESC',(brand_id,)).fetchall()]


def get_snapshot(path,brand_id,sid):
    with connect(path) as con:
        row=con.execute('SELECT payload FROM snapshots WHERE brand_id=? AND id=?',(brand_id,sid)).fetchone()
    if not row: raise ValueError('Snapshot not found for selected brand.')
    return json.loads(row[0])


def record_decision(path,brand_id,sid,reviewer,decision,reason):
    if decision not in ['needs_changes','accepted_for_pilot','rejected']:
        raise ValueError('Invalid decision.')
    if not reviewer.strip() or not reason.strip(): raise ValueError('Reviewer and reason required.')
    payload=get_snapshot(path,brand_id,sid)
    if decision=='accepted_for_pilot':
        if payload['bundle']['missing_policy_questions']:
            raise ValueError('Resolve unknown policy choices before accepting a pilot.')
        if len(payload.get('reviews',[]))!=5 or any(r['status']!='completed' or r.get('source')!='groq' for r in payload['reviews']):
            raise ValueError('All five reviews must complete before accepting a pilot.')
    with connect(path) as con:
        con.execute('INSERT INTO decisions VALUES (?,?,?,?,?,?,?)',(str(uuid4()),sid,brand_id,datetime.now(timezone.utc).isoformat(),reviewer.strip(),decision,reason.strip()))


def decisions(path,brand_id,sid):
    get_snapshot(path,brand_id,sid)
    with connect(path) as con:
        rows=con.execute('SELECT created_at,reviewer,decision,reason FROM decisions WHERE brand_id=? AND snapshot_id=? ORDER BY created_at',(brand_id,sid)).fetchall()
    return [dict(zip(['created_at','reviewer','decision','reason'],r)) for r in rows]
