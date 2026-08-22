-- Own Club core schema
CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT,
  phone TEXT,
  member_no TEXT,
  name TEXT,
  position TEXT,
  is_admin INTEGER DEFAULT 0,
  is_support INTEGER DEFAULT 0,
  balance REAL DEFAULT 0,
  data TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone);
CREATE INDEX IF NOT EXISTS idx_users_member ON users(member_no);

CREATE TABLE IF NOT EXISTS withdrawals (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  amount REAL,
  fee REAL,
  status TEXT,
  data TEXT NOT NULL,
  created_at TEXT,
  updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_wd_user ON withdrawals(user_id);
CREATE INDEX IF NOT EXISTS idx_wd_status ON withdrawals(status);

CREATE TABLE IF NOT EXISTS pool_state (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  balance REAL NOT NULL DEFAULT 0,
  currency TEXT NOT NULL DEFAULT 'USD',
  seed TEXT,
  data TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pool_ledger (
  id TEXT PRIMARY KEY,
  at TEXT,
  type TEXT,
  amount REAL,
  balance_before REAL,
  balance_after REAL,
  note TEXT,
  meta TEXT,
  created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_ledger_at ON pool_ledger(at);
