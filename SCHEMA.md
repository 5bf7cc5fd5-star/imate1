# Own Club database schema

File: `schema.sql` (PostgreSQL)

## Core tables

| Table | Purpose |
|-------|---------|
| `users` | Accounts, invite codes, balances, roles |
| `referral_links` | Who invited whom (level 1 edge) |
| `referral_rewards` | Money paid for referrals |
| `deposits` | MoMo / USDT top-ups + TxID + status |
| `withdrawals` | Withdraw requests + status pipeline |
| `share_purchases` | Club share locks + compound schedule |
| `transactions` | Full wallet ledger |
| `fund_pool` + `fund_pool_ledger` | Company USD pool |
| `payout_accounts` | Member MTN / Airtel / TRC20 |

## Referral tracking

- On signup: `users.referred_by`, `users.used_invite`, unique `users.invite_code`
- Trigger writes `referral_links`
- View `v_user_referral_stats` → L1 / L2 / team counts
- View `v_team_downline` → recursive team tree
- Rewards logged in `referral_rewards` + `users.referral_earnings`

## Uniqueness

- Email unique (case-insensitive)
- Phone unique on digits only
- One invite code per user
- One direct referrer per member

## Current runtime

App still uses JSON files on Railway (`data/users.json`).  
Migrate to Postgres by loading this schema, then pointing the API at `DATABASE_URL`.

```bash
psql $DATABASE_URL -f schema.sql
```
