import os

# Ensure tests run without external Postgres.
os.environ.setdefault('DATABASE_URL', 'sqlite+pysqlite:///./test_trade_recon.db')
os.environ.setdefault('ENVIRONMENT', 'test')
