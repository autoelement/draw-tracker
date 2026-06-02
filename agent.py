import os,json,requests,re
from datetime import date,datetime,timezone,timedelta

AKEY=os.environ["ANTHROPIC_API_KEY"]
SURL=os.environ["SUPABASE_URL"]
SKEY=os.environ["SUPABASE_KEY"]
TTOKEN=os.environ["TELEGRAM_BOT_TOKEN"]
TCHAT=os.environ["TELEGRAM_CHAT_ID"]
APIKEY=os.environ["APISPORTS_KEY"]
TODAY=date.today().strftime("%Y-%m-%d")
TODAYD=date.today().strftime("%d/%m/%Y")
TZ=timezone(timedelta(hours=4))
HEADERS={"x-apisports-key":APIKEY}

AFRICA={"Morocco","Algeria","Tunisia","Egypt","Nigeria","Ghana","Senegal","Cameroon","Ivory Coast","South Africa","Ethiopia","Kenya","Tanzania","Uganda","Rwanda","Mali","Burkina Faso","Niger","Chad","Sudan","Libya","Mauritania","Guinea","Sierra Leone","Liberia","Togo","Benin","Gambia","Guinea-Bissau","Equatorial Guinea","Gabon","Congo","DR Congo","Angola","Zambia","Zimbabwe","Mozambique","Madagascar","Malawi","Botswana","Namibia","Lesotho","Swaziland","Comoros","Cape Verde","Djibouti","Somalia","Eritrea","Burundi","Central African Republic","South Sudan"}

def get_fixtures():
    r=requests.get(f"https://v3.football.api-sports.io/fixtures?date={TODAY}&status=NS",headers=HEADERS)
    fixtures=r.json().get("response",[])
    print(f"Total fixtures today: {len(fixtures)}")
    return fixtures

def get_odds(fixture_id):
    r=requests.get(f"https://v3.football.api-sports.io/odds?fixture={fixture_id}&bet=1",headers=HEADERS)
    try:
        values=r.json()["response"][0]["bookmakers"][0]["bets"][0]["values"]
        home=away=draw=0
        for v in values:
            if v["value"]=="Home": home=float(v["odd"])
            elif v["value"]=="Draw": draw=float(v["odd"])
            elif v["value"]=="Away": away=float(v["odd"])
        if home and draw and away:
            total=1/home+1/draw+1/away
            draw_pct=round((1/draw)/total*100)
            return draw_pct,draw
    except:
        pass
    return 0,0

fixtures=get_fixtures()
candidates=[]
count=0

for f in fixtures:
    if count>=50: break
    country=f["league"]["country"]
    if country in AFRICA:
        continue
    fid=f["fixture"]["id"]
    home=f["teams"]["home"]["name"]
    away=f["teams"]["away"]["name"]
    league=f["league"]["name"]
    try:
        dt=datetime.fromisoformat(f["fixture"]["date"].replace("Z","+00:00"))
        kickoff=dt.astimezone(TZ).strftime("%H:%M")
    except:
        kickoff=f["fixture"]["date"][11:16]
    draw_pct,draw_odd=get_odds(fid)
    count+=1
    print(f"{home} vs {away} ({country}): X={draw_pct}% odd={draw_odd}")
    if draw_pct>=35 and draw_odd>=3.0:
        candidates.append({"fixture_id":fid,"home":home,"away":away,"league":league,"country":country,"kickoff":kickoff,"draw_pct":draw_pct,"draw_odd":round(draw_odd,2)})

candidates.sort(key=lambda x:x["draw_pct"],reverse=True)
top5=candidates[:5]

if not top5:
    requests.post(f"https://api.telegram.org/bot{TTOKEN}/sendMessage",json={"chat_id":TCHAT,"text":f"⚽ Draw Tracker · {TODAYD}\n\n❌ No matches found with X≥35% and odds≥3.0 today."})
    exit()

prompt=f"Today is {TODAYD}. Analyze these football matches filtered by draw probability ≥35% and draw odds ≥3.0, excluding African leagues:\n\n"
for i,m in enumerate(top5,1):
    prompt+=f"{i}. {m['home']} vs {m['away']} ({m['league']}, {m['country']}) - Kickoff: {m['kickoff']} Tbilisi time - Draw: {m['draw_pct']}% - Odds: {m['draw_odd']}\n"
prompt+="""
For each match analyze briefly:
- Recent form of both teams (last 5 matches)
- Head to head history
- Why a draw is likely
- Predicted score

Return ONLY this JSON, no other text:
{"matches":[{"home":"team1","away":"team2","league":"league","country":"country","draw_pct":35,"draw_odd":3.2,"pred_score":"1-1","kickoff":"21:00","analysis":"brief analysis in English"}]}"""

r=requests.post("https://api.anthropic.com/v1/messages",headers={"x-api-key":AKEY,"anthropic-version":"2023-06-01","content-type":"application/json"},json={"model":"claude-haiku-4-5-20251001","max_tokens":2000,"messages":[{"role":"user","content":prompt}]})
text=r.json()["content"][0]["text"].strip()
print("Claude response:",text[:300])
m=re.search(r'\{[\s\S]*"matches"[\s\S]*\}',text)
if m: text=m.group()
matches=json.loads(text)["matches"]

h={"apikey":SKEY,"Authorization":f"Bearer {SKEY}","Content-Type":"application/json"}
rows=[{"date":TODAY,"home":x["home"],"away":x["away"],"league":x.get("league",""),"draw_pct":x.get("draw_pct",0),"pred_score":x.get("pred_score",""),"kickoff":x.get("kickoff",""),"outcome":"pending"} for x in matches]
requests.post(f"{SURL}/rest/v1/matches",headers=h,json=rows)

lines=[f"⚽ Draw Tracker · {TODAYD}\n📊 X≥35% | Odds≥3.0 | Tbilisi Time\n"]
for i,x in enumerate(matches,1):
    lines.append(f"{i}. {x['home']} vs {x['away']}\n   X: {x['draw_pct']}% | Odds: {x.get('draw_odd','?')} | {x['pred_score']} | ⏰ {x['kickoff']}\n   📝 {x.get('analysis','')}\n")
lines.append("Results update tonight 🔄")
requests.post(f"https://api.telegram.org/bot{TTOKEN}/sendMessage",json={"chat_id":TCHAT,"text":"\n".join(lines)})
print("Done!")
