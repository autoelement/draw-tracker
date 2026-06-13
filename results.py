import os,requests
from datetime import date,timezone,timedelta

SURL=os.environ["SUPABASE_URL"]
SKEY=os.environ["SUPABASE_KEY"]
FOOTYSTATS_KEY=os.environ["FOOTYSTATS_KEY"]

SH={"apikey":SKEY,"Authorization":f"Bearer {SKEY}","Content-Type":"application/json"}
TODAY=date.today().strftime("%Y-%m-%d")

print(f"Checking results: {TODAY}")

# 1. Get pending predictions
r=requests.get(f"{SURL}/rest/v1/matches?date=eq.{TODAY}&outcome=eq.pending&select=*",headers=SH)
pred_matches=r.json() if isinstance(r.json(),list) else []
print(f"  Pending predictions: {len(pred_matches)}")

# 2. Get pending bets with fixture_id
r=requests.get(f"{SURL}/rest/v1/bets?status=eq.pending&fixture_id=not.is.null&select=*",headers=SH)
pending_bets=r.json() if isinstance(r.json(),list) else []
print(f"  Pending bets with fixture_id: {len(pending_bets)}")

# Collect fixture IDs
fixture_ids=set()
for m in pred_matches:
    if m.get("fixture_id"): fixture_ids.add(m["fixture_id"])
for b in pending_bets:
    if b.get("fixture_id"): fixture_ids.add(b["fixture_id"])

print(f"  Total fixtures to check: {len(fixture_ids)}")

# 3. Fetch results from FootyStats
results={}
for fid in list(fixture_ids)[:30]:
    r=requests.get(f"https://api.football-data-api.com/match?key={FOOTYSTATS_KEY}&match_id={fid}")
    data=r.json()
    if data.get("success") and data.get("data"):
        m=data["data"]
        status=m.get("status","")
        home_goals=m.get("homeGoalCount")
        away_goals=m.get("awayGoalCount")
        if status=="complete" and home_goals is not None and away_goals is not None:
            is_draw=(home_goals==away_goals)
            result_str=f"{home_goals}-{away_goals}"
            results[fid]={"status":status,"result":result_str,"is_draw":is_draw,"finished":True}
            print(f"  Fixture {fid}: {result_str} {'DRAW' if is_draw else 'NO DRAW'}")
        else:
            results[fid]={"status":status,"finished":False}

# 4. Update predictions
for m in pred_matches:
    fid=m.get("fixture_id")
    if not fid or fid not in results: continue
    res=results[fid]
    if not res["finished"]: continue
    outcome="win" if res["is_draw"] else "loss"
    requests.patch(f"{SURL}/rest/v1/matches?id=eq.{m['id']}",headers=SH,
        json={"result":res["result"],"outcome":outcome})

# 5. Update bets
for b in pending_bets:
    fid=b.get("fixture_id")
    if not fid or fid not in results: continue
    res=results[fid]
    if not res["finished"]: continue
    sel=b.get("selection","")
    if "Draw" in sel or "(X)" in sel:
        won=res["is_draw"]
    elif "Home" in sel or "(1)" in sel:
        parts=res["result"].split("-")
        won=int(parts[0])>int(parts[1]) if len(parts)==2 else False
    elif "Away" in sel or "(2)" in sel:
        parts=res["result"].split("-")
        won=int(parts[1])>int(parts[0]) if len(parts)==2 else False
    else:
        won=res["is_draw"]
    outcome="win" if won else "loss"
    payout=round(b["amount"]*b["odds"],2) if won and b.get("odds") and b.get("amount") else 0
    already=b.get("balance_applied")
    requests.patch(f"{SURL}/rest/v1/bets?id=eq.{b['id']}",headers=SH,
        json={"status":outcome,"payout":payout,"notes":f"auto:FT:{res['result']}","balance_applied":True})
    bk=b.get("bookmaker")
    amt=b.get("amount") or 0
    if not already and bk and bk!="Stake":
        eff=(payout-amt) if won else (-amt)
        if eff:
            bal=requests.get(f"{SURL}/rest/v1/balances?bookmaker=eq.{bk}&select=balance",headers=SH).json()
            if bal:
                nb=(bal[0].get("balance") or 0)+eff
                requests.patch(f"{SURL}/rest/v1/balances?bookmaker=eq.{bk}",headers=SH,json={"balance":nb})
    print(f"  Bet {b['id']}: {b.get('match','')} → {outcome}")
