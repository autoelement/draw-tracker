import os,requests
from datetime import date,timezone,timedelta

SURL=os.environ["SUPABASE_URL"]
SKEY=os.environ["SUPABASE_KEY"]
APIKEY=os.environ["APISPORTS_KEY"]
TTOKEN=os.environ["TELEGRAM_BOT_TOKEN"]
TCHAT=os.environ["TELEGRAM_CHAT_ID"]

HEADERS={"x-apisports-key":APIKEY}
SH={"apikey":SKEY,"Authorization":f"Bearer {SKEY}","Content-Type":"application/json"}
TZ=timezone(timedelta(hours=4))
TODAY=date.today().strftime("%Y-%m-%d")
TODAY_DISPLAY=date.today().strftime("%d/%m/%Y")

print(f"Checking results: {TODAY}")

# 1. Get today's pending predictions (matches table)
r=requests.get(f"{SURL}/rest/v1/matches?date=eq.{TODAY}&outcome=eq.pending&select=*",headers=SH)
pred_matches=r.json() if isinstance(r.json(),list) else []
print(f"  Pending predictions: {len(pred_matches)}")

# 2. Get pending bets with fixture_id
r=requests.get(f"{SURL}/rest/v1/bets?status=eq.pending&fixture_id=not.is.null&select=*",headers=SH)
pending_bets=r.json() if isinstance(r.json(),list) else []
print(f"  Pending bets with fixture_id: {len(pending_bets)}")

# Collect all fixture IDs to check
fixture_ids=set()
for m in pred_matches:
    if m.get("fixture_id"): fixture_ids.add(m["fixture_id"])
for b in pending_bets:
    if b.get("fixture_id"): fixture_ids.add(b["fixture_id"])

print(f"  Total fixtures to check: {len(fixture_ids)}")

# 3. Fetch results from API-Sports
results={}
for fid in list(fixture_ids)[:30]:  # max 30 fixtures
    r=requests.get(f"https://v3.football.api-sports.io/fixtures?id={fid}",headers=HEADERS)
    data=r.json().get("response",[])
    if data:
        f=data[0]
        status=f["fixture"]["status"]["short"]
        home_goals=f["score"]["fulltime"]["home"]
        away_goals=f["score"]["fulltime"]["away"]
        if status in ["FT","AET","PEN"] and home_goals is not None and away_goals is not None:
            is_draw=(home_goals==away_goals)
            result_str=f"{home_goals}-{away_goals}"
            results[fid]={"status":status,"result":result_str,"is_draw":is_draw,"finished":True}
            print(f"  Fixture {fid}: {result_str} {'DRAW' if is_draw else 'NO DRAW'}")
        else:
            results[fid]={"status":status,"finished":False}

# 4. Update predictions (matches table)
wins=0
losses=0
for m in pred_matches:
    fid=m.get("fixture_id")
    if not fid or fid not in results: continue
    res=results[fid]
    if not res["finished"]: continue
    outcome="win" if res["is_draw"] else "loss"
    requests.patch(f"{SURL}/rest/v1/matches?id=eq.{m['id']}",headers=SH,
        json={"result":res["result"],"outcome":outcome})
    if outcome=="win": wins+=1
    else: losses+=1

# 5. Update bets (bets table)
bets_updated=0
for b in pending_bets:
    fid=b.get("fixture_id")
    if not fid or fid not in results: continue
    res=results[fid]
    if not res["finished"]: continue
    sel=b.get("selection","")
    # Determine win/loss based on selection
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
    requests.patch(f"{SURL}/rest/v1/bets?id=eq.{b['id']}",headers=SH,
        json={"status":outcome,"payout":payout,"notes":f"auto:FT:{res['result']}"})
    bets_updated+=1
    print(f"  Bet {b['id']}: {b.get('match','')} → {outcome}")

# 6. Telegram message
lines=[f"📊 Results · {TODAY_DISPLAY}\n"]
for m in pred_matches:
    fid=m.get("fixture_id")
    if fid and fid in results and results[fid]["finished"]:
        res=results[fid]
        emoji="✅" if res["is_draw"] else "❌"
        lines.append(f"{emoji} {m['home']} vs {m['away']}: {res['result']}")
    else:
        lines.append(f"⏳ {m['home']} vs {m['away']}: pending")

lines.append(f"\n🏆 {wins}/{wins+losses} predictions correct")
if bets_updated>0:
    lines.append(f"💰 {bets_updated} bets updated automatically")

text="\n".join(lines)
requests.post(f"https://api.telegram.org/bot{TTOKEN}/sendMessage",
    json={"chat_id":TCHAT,"text":text})
print(f"Done! {wins}W/{losses}L, {bets_updated} bets updated")
