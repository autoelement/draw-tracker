import os,json,requests,re
from datetime import date,datetime,timezone,timedelta

AKEY=os.environ["ANTHROPIC_API_KEY"]
SURL=os.environ["SUPABASE_URL"]
SKEY=os.environ["SUPABASE_KEY"]
TTOKEN=os.environ["TELEGRAM_BOT_TOKEN"]
TCHAT=os.environ["TELEGRAM_CHAT_ID"]
APIKEY=os.environ["APISPORTS_KEY"]
TZ=timezone(timedelta(hours=4))
HEADERS={"x-apisports-key":APIKEY}

AFRICA={"Morocco","Algeria","Tunisia","Egypt","Nigeria","Ghana","Senegal","Cameroon","Ivory Coast","South Africa","Ethiopia","Kenya","Tanzania","Uganda","Rwanda","Mali","Burkina Faso","Niger","Chad","Sudan","Libya","Mauritania","Guinea","Sierra Leone","Liberia","Togo","Benin","Gambia","Guinea-Bissau","Equatorial Guinea","Gabon","Congo","DR Congo","Angola","Zambia","Zimbabwe","Mozambique","Madagascar","Malawi","Botswana","Namibia","Lesotho","Swaziland","Comoros","Cape Verde","Djibouti","Somalia","Eritrea","Burundi","Central African Republic","South Sudan"}

def get_fixtures(day_offset):
    d=(date.today()+timedelta(days=day_offset)).strftime("%Y-%m-%d")
    r=requests.get(f"https://v3.football.api-sports.io/fixtures?date={d}&status=NS",headers=HEADERS)
    return r.json().get("response",[]),d

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

all_messages=[]

for day_offset in range(3):
    fixtures,datestr=get_fixtures(day_offset)
    display_date=datetime.strptime(datestr,"%Y-%m-%d").strftime("%d/%m/%Y")
    label=["Today","Tomorrow","Day after tomorrow"][day_offset]
    print(f"\n{label} ({display_date}): {len(fixtures)} fixtures")

    candidates=[]
    count=0
    for f in fixtures:
        if count>=30: break
        country=f["league"]["country"]
        if country in AFRICA: continue
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
        print(f"  {home} vs {away}: X={draw_pct}% odd={draw_odd}")
        if draw_pct>=35 and draw_odd>=3.0:
            candidates.append({"home":home,"away":away,"league":league,"country":country,"kickoff":kickoff,"draw_pct":draw_pct,"draw_odd":round(draw_odd,2),"date":display_date,"label":label})

    candidates.sort(key=lambda x:x["draw_pct"],reverse=True)
    top=candidates[:5]

    if top:
        section=f"📅 {label} · {display_date}\n"
        for i,x in enumerate(top,1):
            section+=f"{i}. {x['home']} vs {x['away']}\n   X: {x['draw_pct']}% | Odds: {x['draw_odd']} | ⏰ {x['kickoff']} | {x['league']}\n"
        all_messages.append(section)

        rows=[{"date":datestr,"home":x["home"],"away":x["away"],"league":x.get("league",""),"draw_pct":x.get("draw_pct",0),"pred_score":"","kickoff":x.get("kickoff",""),"outcome":"pending"} for x in top]
        h={"apikey":SKEY,"Authorization":f"Bearer {SKEY}","Content-Type":"application/json"}
        requests.post(f"{SURL}/rest/v1/matches",headers=h,json=rows)
    else:
        all_messages.append(f"📅 {label} · {display_date}\n❌ No matches with X≥35% and odds≥3.0\n")

final="⚽ Draw Tracker · 3 Days\n📊 X≥35% | Odds≥3.0 | Tbilisi Time\n\n"
final+="\n".join(all_messages)
final+="Results update tonight 🔄"
requests.post(f"https://api.telegram.org/bot{TTOKEN}/sendMessage",json={"chat_id":TCHAT,"text":final})
print("Done!")
