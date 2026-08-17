-- Own Club — Share Market (iMate1)
-- PostgreSQL schema for production tracking
-- Compatible with Railway Postgres / any PostgreSQL 14+

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------------
-- Users & auth
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY DEFAULT ('u_' || substr(gen_random_uuid()::text, 1, 12)),
    name            TEXT NOT NULL,
    phone           TEXT NOT NULL,
    email           TEXT NOT NULL,
    password_hash   TEXT NOT NULL,
    id_type         TEXT DEFAULT 'National ID',
    id_num          TEXT DEFAULT '',
    invite_code     TEXT NOT NULL UNIQUE,
    used_invite     TEXT DEFAULT '',
    referred_by     TEXT REFERENCES users(id) ON DELETE SET NULL,
    balance         NUMERIC(18,2) NOT NULL DEFAULT 0,
    is_admin        BOOLEAN NOT NULL DEFAULT FALSE,
    is_support      BOOLEAN NOT NULL DEFAULT FALSE,
    is_staff        BOOLEAN NOT NULL DEFAULT FALSE,
    title           TEXT DEFAULT '',
    avatar_preset   TEXT DEFAULT '',
    avatar_url      TEXT DEFAULT '',
    junior_shareholder BOOLEAN NOT NULL DEFAULT FALSE,
    welcome_credited   BOOLEAN NOT NULL DEFAULT FALSE,
    join_bonus_locked  BOOLEAN NOT NULL DEFAULT TRUE,
    bonus_claimed      BOOLEAN NOT NULL DEFAULT FALSE,
    can_approve_deposit  BOOLEAN NOT NULL DEFAULT FALSE,
    can_approve_withdraw BOOLEAN NOT NULL DEFAULT FALSE,
    can_approve_password BOOLEAN NOT NULL DEFAULT FALSE,
    referral_earnings NUMERIC(18,2) NOT NULL DEFAULT 0,
    country_code    TEXT DEFAULT 'UG',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_lower ON users (LOWER(email));
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone_digits ON users (
    REGEXP_REPLACE(phone, '\D', '', 'g')
);
CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users (referred_by);
CREATE INDEX IF NOT EXISTS idx_users_invite_code ON users (invite_code);
CREATE INDEX IF NOT EXISTS idx_users_used_invite ON users (used_invite);

-- ---------------------------------------------------------------------------
-- Referral events (every join edge + rewards)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS referral_links (
    id              BIGSERIAL PRIMARY KEY,
    referrer_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    referred_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    invite_code     TEXT NOT NULL,
    level           INT NOT NULL DEFAULT 1 CHECK (level >= 1),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (referred_id)
);

CREATE INDEX IF NOT EXISTS idx_referral_links_referrer ON referral_links (referrer_id);

CREATE TABLE IF NOT EXISTS referral_rewards (
    id              BIGSERIAL PRIMARY KEY,
    referrer_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    referred_id     TEXT REFERENCES users(id) ON DELETE SET NULL,
    kind            TEXT NOT NULL, -- join_bonus | first_purchase | dividend
    amount          NUMERIC(18,2) NOT NULL,
    currency        TEXT NOT NULL DEFAULT 'UGX',
    meta            JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_referral_rewards_referrer ON referral_rewards (referrer_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- Deposits
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS deposits (
    id              TEXT PRIMARY KEY DEFAULT ('d_' || substr(gen_random_uuid()::text, 1, 12)),
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount          NUMERIC(18,2) NOT NULL CHECK (amount > 0),
    method          TEXT NOT NULL, -- MTN Mobile Money | Airtel Money | USDT TRC20 | ...
    network         TEXT NOT NULL DEFAULT 'mtn', -- mtn | airtel | usdt | trc20 | bep20 | erc20
    channel         TEXT DEFAULT '', -- destination number or crypto address shown
    sender          TEXT DEFAULT '',
    txid            TEXT DEFAULT '',
    reference       TEXT DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'pending', -- pending | confirmed | rejected
    verified_by     TEXT DEFAULT '', -- auto | system | user_id
    verify_note     TEXT DEFAULT '',
    auto_credited   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_deposits_user ON deposits (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_deposits_status ON deposits (status);
CREATE INDEX IF NOT EXISTS idx_deposits_txid ON deposits (txid);

-- ---------------------------------------------------------------------------
-- Withdrawals
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS withdrawals (
    id              TEXT PRIMARY KEY DEFAULT ('w_' || substr(gen_random_uuid()::text, 1, 12)),
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount          NUMERIC(18,2) NOT NULL CHECK (amount > 0),
    fee             NUMERIC(18,2) NOT NULL DEFAULT 0,
    net_amount      NUMERIC(18,2),
    method          TEXT DEFAULT '',
    destination     TEXT DEFAULT '',
    txid            TEXT DEFAULT '', -- system-generated review id
    status          TEXT NOT NULL DEFAULT 'under_review',
    -- under_review | reviewed | disbursed | rejected
    admin_note      TEXT DEFAULT '',
    status_history  JSONB DEFAULT '[]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_withdrawals_user ON withdrawals (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_withdrawals_status ON withdrawals (status);

-- ---------------------------------------------------------------------------
-- Club share purchases (machines / shares)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS share_purchases (
    id              TEXT PRIMARY KEY DEFAULT ('s_' || substr(gen_random_uuid()::text, 1, 12)),
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    club_code       TEXT NOT NULL,
    club_name       TEXT NOT NULL,
    league          TEXT DEFAULT '',
    weeks           INT NOT NULL CHECK (weeks BETWEEN 1 AND 4),
    price           NUMERIC(18,2) NOT NULL,
    locked_amount   NUMERIC(18,2) NOT NULL,
    daily_rate      NUMERIC(8,4) NOT NULL DEFAULT 0.08, -- 8% daily compound
    status          TEXT NOT NULL DEFAULT 'active', -- active | completed
    purchased_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    unlock_at       TIMESTAMPTZ NOT NULL,
    last_compound_at TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_shares_user ON share_purchases (user_id, status);
CREATE INDEX IF NOT EXISTS idx_shares_unlock ON share_purchases (status, unlock_at);

-- ---------------------------------------------------------------------------
-- Wallet ledger (full money movement)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS transactions (
    id              BIGSERIAL PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind            TEXT NOT NULL, -- deposit | withdraw | purchase | referral | welcome | compound | credit | debit
    amount          NUMERIC(18,2) NOT NULL,
    balance_after   NUMERIC(18,2),
    description     TEXT DEFAULT '',
    ref_type        TEXT DEFAULT '', -- deposits | withdrawals | share_purchases | referral_rewards
    ref_id          TEXT DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tx_user ON transactions (user_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- Company fund pool
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fund_pool (
    id              INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    balance_usd     NUMERIC(20,2) NOT NULL DEFAULT 500000000,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO fund_pool (id, balance_usd) VALUES (1, 500000000)
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS fund_pool_ledger (
    id              BIGSERIAL PRIMARY KEY,
    delta_usd       NUMERIC(20,2) NOT NULL,
    balance_after   NUMERIC(20,2) NOT NULL,
    reason          TEXT NOT NULL,
    meta            JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Payout profiles (member withdrawal destinations)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS payout_accounts (
    user_id         TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    mtn             TEXT DEFAULT '',
    airtel          TEXT DEFAULT '',
    trc20           TEXT DEFAULT '',
    withdraw_pin_hash TEXT DEFAULT '',
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Helpful views for System panel
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_referral_tree AS
SELECT
    r.referrer_id,
    ref.name AS referrer_name,
    ref.invite_code AS referrer_code,
    r.referred_id,
    u.name AS member_name,
    u.phone,
    u.email,
    u.used_invite,
    r.level,
    r.created_at AS joined_at
FROM referral_links r
JOIN users u ON u.id = r.referred_id
JOIN users ref ON ref.id = r.referrer_id;

CREATE OR REPLACE VIEW v_user_referral_stats AS
SELECT
    u.id,
    u.name,
    u.phone,
    u.email,
    u.invite_code,
    COUNT(r.referred_id) FILTER (WHERE r.level = 1) AS level1_count,
    COUNT(r.referred_id) FILTER (WHERE r.level = 2) AS level2_count,
    COUNT(r.referred_id) AS team_count,
    u.referral_earnings,
    u.created_at
FROM users u
LEFT JOIN referral_links r ON r.referrer_id = u.id
GROUP BY u.id;

-- ---------------------------------------------------------------------------
-- Trigger: when a user is created with referred_by, insert referral_links
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_on_user_referral() RETURNS TRIGGER AS $$
DECLARE
    parent_id TEXT;
    lvl INT := 1;
    cur TEXT;
BEGIN
    IF NEW.referred_by IS NULL THEN
        RETURN NEW;
    END IF;
    INSERT INTO referral_links (referrer_id, referred_id, invite_code, level)
    VALUES (NEW.referred_by, NEW.id, COALESCE(NEW.used_invite, ''), 1)
    ON CONFLICT (referred_id) DO NOTHING;

    -- build upline levels 2+
    cur := NEW.referred_by;
    lvl := 2;
    WHILE cur IS NOT NULL AND lvl <= 15 LOOP
        SELECT referred_by INTO parent_id FROM users WHERE id = cur;
        IF parent_id IS NULL THEN
            EXIT;
        END IF;
        INSERT INTO referral_links (referrer_id, referred_id, invite_code, level)
        VALUES (parent_id, NEW.id, COALESCE(NEW.used_invite, ''), lvl)
        ON CONFLICT DO NOTHING;
        -- note: UNIQUE(referred_id) only stores direct link; for multi-level
        -- use separate rows without unique on referred only — see alt below
        cur := parent_id;
        lvl := lvl + 1;
        EXIT; -- direct tree view uses recursive query; keep simple L1 edge here
    END LOOP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_user_referral ON users;
CREATE TRIGGER trg_user_referral
AFTER INSERT ON users
FOR EACH ROW EXECUTE FUNCTION fn_on_user_referral();

-- Multi-level helper (recursive)
CREATE OR REPLACE VIEW v_team_downline AS
WITH RECURSIVE tree AS (
    SELECT id AS root_id, id AS member_id, 0 AS level
    FROM users
    UNION ALL
    SELECT t.root_id, u.id, t.level + 1
    FROM tree t
    JOIN users u ON u.referred_by = t.member_id
    WHERE t.level < 15
)
SELECT root_id, member_id, level
FROM tree
WHERE level > 0;
