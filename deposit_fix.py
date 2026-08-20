def normalize_deposit_items(get_users):
    items = []
    for x in get_users():
        for d in x.get("deposits") or []:
            ref = (d.get("txid") or d.get("txId") or d.get("reference") or d.get("transaction_id") or "")
            items.append({
                **d,
                "user_id": x.get("id"),
                "user_name": x.get("name"),
                "user_phone": x.get("phone"),
                "txid": ref,
                "reference": ref,
                "txId": ref,
            })
    def _k(z):
        st = str(z.get("status") or "").lower()
        return (0 if st in ("pending", "under_review") else 1, z.get("created_at") or "")
    items.sort(key=_k)
    return items
