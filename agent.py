import os,json,requests,re
from datetime import date

AKEY=os.environ["ANTHROPIC_API_KEY"]
SURL=os.environ["SUPABASE_URL"]
SKEY=os.environ["SUPABASE_KEY"]
TTOKEN=os.environ["TELEGRAM_BOT_TOKEN"]
TCHAT=os.environ["TELEGRAM_CHAT_ID"]
APIKEY=os.environ["APISPORTS_KEY"]
TODAY=date.today().strftime("%Y-%m-%d")
TODAYD=date.today().strftime("%d/%m/%Y")

HEADERS={"x-apisports-key":APIKEY}

def get_fixtures():
    r=requests.get(f"https://v3.football.api-sports.io/fixtures?date={TODAY}&status=NS",headers=HEADERS)
    data=r.json()
    fixtures=data.get("response",[])
    print(f"სულ {len(fixtures)} მატჩი დღეს")
    return fixtures

def get_odds(fixture_id):
    r=requests.get(f"https://v3.football.api-sports.io/odds?fixture={fixture_id}&bet=1",headers=HEADERS)
    data=r.json()
    try:
        values=data["response"][0]["bookmakers"][0]["bets"][0]["values"]
        home=away=draw=0
        for v in values:
            if v["value"]=="Home": home=float(v["odd"])
            elif v["value"]=="Draw": draw=float(v["odd"])
            elif v["value"]=="Away": away=float(v["odd"])
        if home and draw and away:
            total=1/home+1/draw+1/away
            draw_pct=round((1/draw)/total*100)
            return draw_pct
    except:
        pass
    return 0

fixtures=get_fixtures()

candidates=[]
count=0
for f in fixtures:
    if count>=30: break
    fid=f["fixture"]["id"]
    home=f["teams"]["home"]["name"]
    away=f["teams"]["away"]["name"]
    league=f["league"]["name"]
    country=f["league"]["country"]
    kickoff=f["fixture"]["date"][11:16]
    draw_pct=get_odds(fid)
    count+=1
    if draw_pct>=25:
        candidates.append({"fixture_id":fid,"home":home,"away":away,"league":league,"country":country,"kickoff":kickoff,"draw_pct":draw_pct})
    print(f"{home} vs {away}: X={draw_pct}%")

candidates.sort(key=lambda x:x["draw_pct"],reverse=True)
top5=candidates[:5]

if not top5:
    print("მატჩები ვერ მოიძებნა")
    exit()

prompt=f"დღეს არის {TODAYD}. გქონდეს ეს 5 ფეხბურთის მატჩი:\n\n"
for i,m in enumerate(top5,1):
    prompt+=f"{i}. {m['home']} vs {m['away']} ({m['league']}, {m['country']}) - {m['kickoff']} - ფრის ალბათობა odds-ით: {m['draw_pct']}%\n"
prompt+="\nგააანალიზე თითოეული მატჩი მოკლედ (ფორმა, H2H, ლიგის სპეციფიკა) და დააბრუნე მხოლოდ JSON:\n"
prompt+="{\"matches\":[{\"home\":\"გუნდი1\",\"away\":\"გუნდი2\",\"league\":\"ლიგა\",\"draw_pct\":35,\"pred_score\":\"1-1\",\"kickoff\":\"21:00\",\"analysis\":\"მოკლე ანალიზი\"}]}"

r=requests.post("https://api.anthropic.com/v1/messages",headers={"x-api-key":AKEY,"anthropic-version":"2023-06-01","content-type":"application/json"},json={"model":"claude-haiku-4-5-20251001","max_tokens":1500,"messages":[{"role":"user","content":prompt}]})
text=r.json()["content"][0]["text"].strip()
print("Claude პასუხი:",text[:300])
m=re.search(r'\{[\s\S]*"matches"[\s\S]*\}',text)
if m: text=m.group()
matches=json.loads(text)["matches"]

h={"apikey":SKEY,"Authorization":f"Bearer {SKEY}","Content-Type":"application/json"}
rows=[{"date":TODAY,"home":x["home"],"away":x["away"],"league":x.get("league",""),"draw_pct":x.get("draw_pct",0),"pred_score":x.get("pred_score",""),"kickoff":x.get("kickoff",""),"outcome":"pending"} for x in matches]
requests.post(f"{SURL}/rest/v1/matches",headers=h,json=rows)

lines=[f"⚽ Draw Tracker · {TODAYD}\n"]
for i,x in enumerate(matches,1):
    lines.append(f"{i}. {x['home']} vs {x['away']}\n   X: {x['draw_pct']}% | {x['pred_score']} | {x['kickoff']}\n   📊 {x.get('analysis','')}\n")
lines.append("ანგარიში ღამით განახლდება 🔄")
requests.post(f"https://api.telegram.org/bot{TTOKEN}/sendMessage",json={"chat_id":TCHAT,"text":"\n".join(lines)})
print("დასრულდა!")
