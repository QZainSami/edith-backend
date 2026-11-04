"""Small transactional store: SQLite locally, pooled PostgreSQL when hosted."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3


class StorageUnavailable(RuntimeError):
    pass


class PostgresSession:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, params=()):
        # All statements here are application-owned; values always remain bound parameters.
        if sql.startswith('INSERT OR IGNORE INTO '):
            sql = sql.replace('INSERT OR IGNORE INTO ', 'INSERT INTO ', 1) + ' ON CONFLICT DO NOTHING'
        return self.connection.execute(sql.replace('?', '%s'), params)


class Database:
    def __init__(self, target):
        self.target = str(target)
        self.postgres = self.target.startswith(('postgres://', 'postgresql://'))
        self.pool = None
        if self.postgres:
            from psycopg_pool import ConnectionPool
            self.pool = ConnectionPool(self.target, min_size=0, max_size=2, timeout=8,
                max_idle=60, kwargs={'connect_timeout':5, 'prepare_threshold':None}, open=True)
        else:
            Path(self.target).parent.mkdir(parents=True, exist_ok=True)

    @property
    def lock_suffix(self):
        return ' FOR UPDATE' if self.postgres else ''

    @contextmanager
    def connect(self, write=False):
        if self.postgres:
            import psycopg
            from psycopg_pool import PoolTimeout
            try:
                with self.pool.connection() as connection:
                    connection.execute('SET LOCAL statement_timeout = 5000')
                    yield PostgresSession(connection)
            except (psycopg.Error, PoolTimeout):
                raise StorageUnavailable('Persistent database unavailable. Check its connection and usage limits.') from None
        else:
            db = sqlite3.connect(self.target, timeout=5)
            try:
                with db:
                    if write: db.execute('BEGIN IMMEDIATE')
                    yield db
            except sqlite3.Error:
                raise StorageUnavailable('Local database unavailable. Check its writable path.') from None
            finally:
                db.close()

    def columns(self, db, table):
        if table not in ('state', 'companion'):
            raise ValueError('Unknown application table')
        if self.postgres:
            return {row[0] for row in db.execute('SELECT column_name FROM information_schema.columns '
                'WHERE table_schema=current_schema() AND table_name=?', (table,))}
        return {row[1] for row in db.execute('PRAGMA table_info(' + table + ')')}

    def close(self):
        if self.pool is not None: self.pool.close()


def database(value):
    return value if isinstance(value, Database) else Database(value)
