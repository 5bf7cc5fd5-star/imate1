# MTN MoMo Collection — connect to iMate1

## 1. Portal
1. Go to https://momodeveloper.mtn.com
2. Subscribe to **Collection**
3. (Sandbox) use **Sandbox User Provisioning** to create:
   - API User (UUID)
   - API Key

## 2. Products / APIs you need
- CreateAccessToken
- RequesttoPay
- RequesttoPayTransactionStatus

## 3. Railway Variables
In your service → Variables, add:

| Name | Value |
|------|--------|
| `MOMO_PROVIDER` | `mtn` |
| `MTN_MOMO_SUBSCRIPTION_KEY` | Primary key from portal |
| `MTN_MOMO_API_USER` | API User UUID |
| `MTN_MOMO_API_KEY` | API Key |
| `MTN_MOMO_TARGET_ENVIRONMENT` | `sandbox` (later production code e.g. `mtnuganda`) |
| `MTN_MOMO_CURRENCY` | `UGX` |
| `MTN_MOMO_CALLBACK_URL` | `https://imate1.com/api/momo/webhook` |
| `MOMO_COLLECTION_NUMBER` | your merchant number (optional display) |

Never commit keys to GitHub.

## 4. App flow
1. Member opens Deposit, enters amount + MoMo phone
2. Backend: CreateAccessToken → RequesttoPay
3. Member approves on phone
4. Backend polls RequesttoPayTransactionStatus OR webhook hits `/api/momo/webhook`
5. Status SUCCESSFUL → wallet auto-credited

## 5. Test (sandbox)
1. Deploy with `MTN_MOMO_TARGET_ENVIRONMENT=sandbox`
2. Use sandbox test numbers from MTN docs
3. Call deposit from the app
4. Check Railway logs for RequesttoPay response

## 6. Production
1. Get production subscription + API user from MTN
2. Set target environment to MTN Uganda production value
3. Set callback to https://imate1.com/api/momo/webhook
4. Redeploy
