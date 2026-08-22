-- Staff flags + transaction log table (history is also inside users.data)
CREATE TABLE IF NOT EXISTS transactions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  at TEXT,
  type TEXT,
  amount REAL,
  note TEXT,
  data TEXT,
  created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_tx_user ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_tx_at ON transactions(at);
