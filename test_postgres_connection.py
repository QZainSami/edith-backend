"""Opt-in read-only driver/connectivity check; no tables or data are changed."""
import os
import pytest
from storage import Database

@pytest.mark.skipif(not os.getenv('EDITH_TEST_DATABASE_URL'), reason='No PostgreSQL connectivity test URL provided')
def test_postgres_connection_read_only():
    db=Database(os.environ['EDITH_TEST_DATABASE_URL'])
    try:
        assert db.postgres
        with db.connect() as connection:
            connection.execute('SET TRANSACTION READ ONLY')
            assert connection.execute('SELECT 1').fetchone()[0]==1
    finally:
        db.close()
