"""Snapshot and restore the study database.

``VACUUM INTO`` produces a consistent single-file copy while the app keeps
writing (WAL is on), which is what makes an unattended nightly backup safe.
Each snapshot is a complete, openable SQLite database — restoring is a file
copy, not a replay.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from open_webui.weblab.db import IS_SQLITE, WEBLAB_BACKUP_DIR, WEBLAB_DB_PATH, engine

log = logging.getLogger(__name__)

BACKUP_INTERVAL_SECONDS = int(os.getenv('WEBLAB_BACKUP_INTERVAL_SECONDS', str(24 * 60 * 60)))
BACKUP_RETENTION = int(os.getenv('WEBLAB_BACKUP_RETENTION', '30'))


def _timestamped_name(prefix: str = 'weblab') -> str:
    return f'{prefix}-{datetime.now().strftime("%Y%m%d-%H%M%S")}.db'


def create_backup(label: Optional[str] = None) -> dict:
    """Write a consistent snapshot and prune old ones.  Blocking; run in a thread."""
    if not IS_SQLITE:
        return {'ok': False, 'error': 'Automatic snapshots are only implemented for SQLite.'}

    WEBLAB_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = WEBLAB_BACKUP_DIR / _timestamped_name('weblab' if not label else f'weblab-{label}')

    connection = sqlite3.connect(str(WEBLAB_DB_PATH), timeout=30)
    try:
        # VACUUM INTO refuses to overwrite, which is what we want.
        connection.execute('VACUUM INTO ?', (str(target),))
    finally:
        connection.close()

    pruned = _prune_backups()
    return {
        'ok': True,
        'path': str(target),
        'filename': target.name,
        'size': target.stat().st_size,
        'created_at': int(time.time()),
        'pruned': pruned,
    }


def _prune_backups() -> int:
    """Keep the newest ``WEBLAB_BACKUP_RETENTION`` snapshots."""
    if BACKUP_RETENTION <= 0:
        return 0
    snapshots = sorted(
        WEBLAB_BACKUP_DIR.glob('weblab*.db'), key=lambda p: p.stat().st_mtime, reverse=True
    )
    pruned = 0
    for stale in snapshots[BACKUP_RETENTION:]:
        try:
            stale.unlink()
            pruned += 1
        except OSError:
            log.warning('Web Lab: could not prune backup %s', stale)
    return pruned


def list_backups() -> list[dict]:
    if not WEBLAB_BACKUP_DIR.exists():
        return []
    snapshots = []
    for path in sorted(WEBLAB_BACKUP_DIR.glob('weblab*.db'), key=lambda p: p.stat().st_mtime, reverse=True):
        stat = path.stat()
        snapshots.append(
            {
                'filename': path.name,
                'path': str(path),
                'size': stat.st_size,
                'created_at': int(stat.st_mtime),
            }
        )
    return snapshots


def database_info() -> dict:
    exists = WEBLAB_DB_PATH.exists() if IS_SQLITE else True
    return {
        'path': str(WEBLAB_DB_PATH),
        'exists': exists,
        'size': WEBLAB_DB_PATH.stat().st_size if exists and IS_SQLITE else None,
        'backup_dir': str(WEBLAB_BACKUP_DIR),
        'backup_count': len(list_backups()),
        'retention': BACKUP_RETENTION,
        'interval_seconds': BACKUP_INTERVAL_SECONDS,
    }


def verify_backup(filename: str) -> dict:
    """Open a snapshot read-only and confirm it is intact and has study rows."""
    path = (WEBLAB_BACKUP_DIR / filename).resolve()
    if WEBLAB_BACKUP_DIR not in path.parents or not path.exists():
        return {'ok': False, 'error': 'Unknown backup file.'}

    connection = sqlite3.connect(f'file:{path}?mode=ro', uri=True, timeout=30)
    try:
        integrity = connection.execute('PRAGMA integrity_check').fetchone()[0]
        counts = {}
        for table in (
            'weblab_case_study', 'weblab_participant', 'weblab_membership',
            'weblab_demand_window', 'weblab_usage_record', 'weblab_message_record',
            'weblab_intervention', 'weblab_postponement', 'weblab_event',
        ):
            try:
                counts[table] = connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
            except sqlite3.Error:
                counts[table] = None
        return {'ok': integrity == 'ok', 'integrity': integrity, 'counts': counts, 'filename': filename}
    finally:
        connection.close()


def restore_backup(filename: str) -> dict:
    """Replace the live study database with a snapshot.

    The database in place is itself snapshotted first, so a restore is never a
    one-way door.  The app must be restarted afterwards to drop stale handles.
    """
    path = (WEBLAB_BACKUP_DIR / filename).resolve()
    if WEBLAB_BACKUP_DIR not in path.parents or not path.exists():
        return {'ok': False, 'error': 'Unknown backup file.'}

    verification = verify_backup(filename)
    if not verification.get('ok'):
        return {'ok': False, 'error': f'Backup failed its integrity check: {verification.get("integrity")}'}

    pre_restore = None
    if WEBLAB_DB_PATH.exists():
        pre_restore = create_backup('pre-restore')

    for suffix in ('-wal', '-shm'):
        sidecar = Path(str(WEBLAB_DB_PATH) + suffix)
        if sidecar.exists():
            sidecar.unlink()

    shutil.copy2(path, WEBLAB_DB_PATH)
    return {
        'ok': True,
        'restored_from': filename,
        'pre_restore_backup': pre_restore.get('filename') if pre_restore else None,
        'note': 'Restart Open WebUI so the application reopens the restored file.',
    }


async def backup_loop() -> None:
    """Background task: snapshot on start, then on a fixed interval."""
    if not IS_SQLITE or BACKUP_INTERVAL_SECONDS <= 0:
        return
    while True:
        try:
            result = await asyncio.to_thread(create_backup)
            if result.get('ok'):
                log.info('Web Lab: study snapshot written to %s', result['path'])
        except Exception:
            log.exception('Web Lab: scheduled snapshot failed')
        await asyncio.sleep(BACKUP_INTERVAL_SECONDS)
