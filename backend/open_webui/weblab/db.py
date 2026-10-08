"""Isolated database for the Web Lab study.

The study keeps its own SQLite file, completely separate from ``webui.db``.
Everything the study needs to be reconstructed later — participants, group
history, demand windows, token usage, interventions and postponements —
lives in this one file, so it survives an Open WebUI upgrade, a reset of the
main database, or a move to another host.  Copy the file, and you have the
study.

Override the location with ``WEBLAB_DATABASE_URL`` (any SQLAlchemy async URL)
or ``WEBLAB_DB_PATH``.  Default: ``$DATA_DIR/weblab.db``.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from open_webui.env import DATA_DIR
from sqlalchemy import MetaData, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

WEBLAB_DB_PATH = Path(os.getenv('WEBLAB_DB_PATH', str(DATA_DIR / 'weblab.db'))).resolve()
WEBLAB_BACKUP_DIR = Path(os.getenv('WEBLAB_BACKUP_DIR', str(WEBLAB_DB_PATH.parent / 'weblab-backups'))).resolve()

_default_url = f'sqlite+aiosqlite:///{WEBLAB_DB_PATH}'
WEBLAB_DATABASE_URL = os.getenv('WEBLAB_DATABASE_URL', _default_url)
if WEBLAB_DATABASE_URL.startswith('sqlite://'):
    WEBLAB_DATABASE_URL = WEBLAB_DATABASE_URL.replace('sqlite://', 'sqlite+aiosqlite://', 1)

IS_SQLITE = WEBLAB_DATABASE_URL.startswith('sqlite')

# Naming convention keeps constraint names stable so the schema can be diffed
# and migrated by hand years from now.
metadata_obj = MetaData(
    naming_convention={
        'ix': 'ix_%(column_0_label)s',
        'uq': 'uq_%(table_name)s_%(column_0_name)s',
        'ck': 'ck_%(table_name)s_%(constraint_name)s',
        'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
        'pk': 'pk_%(table_name)s',
    }
)
WeblabBase = declarative_base(metadata=metadata_obj)

engine = create_async_engine(
    WEBLAB_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args={'timeout': 30} if IS_SQLITE else {},
)

if IS_SQLITE:

    @event.listens_for(engine.sync_engine, 'connect')
    def _set_sqlite_pragmas(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        try:
            # WAL keeps the study readable (and backup-able) while the app writes.
            cursor.execute('PRAGMA journal_mode=WAL')
            cursor.execute('PRAGMA synchronous=NORMAL')
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.execute('PRAGMA busy_timeout=30000')
        finally:
            cursor.close()


WeblabSession = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def get_weblab_db(db: AsyncSession | None = None):
    """Yield a study-database session, reusing *db* when one is passed in."""
    if db is not None:
        yield db
        return
    async with WeblabSession() as session:
        yield session


async def init_weblab_db() -> None:
    """Create the study schema if it does not exist and stamp its version."""
    from open_webui.weblab import models  # noqa: F401  (registers the tables)

    if IS_SQLITE:
        WEBLAB_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        WEBLAB_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(WeblabBase.metadata.create_all)
        await conn.execute(
            text('CREATE TABLE IF NOT EXISTS weblab_schema_version (version INTEGER PRIMARY KEY, applied_at INTEGER NOT NULL)')
            if IS_SQLITE
            else text('CREATE TABLE IF NOT EXISTS weblab_schema_version (version INTEGER PRIMARY KEY, applied_at BIGINT NOT NULL)')
        )
        current = (await conn.execute(text('SELECT MAX(version) FROM weblab_schema_version'))).scalar()
        if current is None or current < SCHEMA_VERSION:
            import time

            await conn.execute(
                text('INSERT INTO weblab_schema_version (version, applied_at) VALUES (:v, :t)'),
                {'v': SCHEMA_VERSION, 't': int(time.time())},
            )
    log.info('Web Lab study database ready at %s (schema v%s)', WEBLAB_DATABASE_URL, SCHEMA_VERSION)
