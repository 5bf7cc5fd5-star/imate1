# iMate1 Go-Live Checklist

## Already working
- [x] Hosted on Railway
- [x] Domain imate1.com (if DNS active)
- [x] Volume `/app/data` for persistence
- [x] Register / login
- [x] Machines A1–A10
- [x] Deposit TxID → pending
- [x] Admin approve deposit → wallet credit
- [x] Buy machine, 5-day lock, withdrawals need admin
- [x] Referrals

## Required for production ops
1. Railway Variables:
   - ADMIN_PASSWORD=(strong password)
   - IMATE1_SECRET=(long random string)
   - ADMIN_ONLY_DEPOSIT_CREDIT=1
2. Change default admin password after first login
3. Only approve deposits after you see real MoMo/USDT
4. Only approve withdrawals after you send money

## Optional MoMo API (later)
- MOMO_PROVIDER=mtn
- MTN_MOMO_SUBSCRIPTION_KEY=
- MTN_MOMO_API_USER=
- MTN_MOMO_API_KEY=
- MTN_MOMO_TARGET_ENVIRONMENT=sandbox then production

## Legal
High daily-return products may be regulated. Get local legal advice before public marketing.
