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

def get_fixtures(d):
    r=requests.get(f"https://v3.football.api-sports.io/fixtures?date={d}&status=NS",headers=HEADERS)
    return r.json().get("response",[])

def get_odds(fid):
    r=requests.get(f"https://v3.football.api-sports.io/odds?fixture={fid}&bet=1",headers=HEADERS)
    try:
        values=r.json()["response"][0]["bookmakers"][0]["bets"][0]["values"]
        home=away=draw=0
        for v in values:
            if v["value"]=="Home": home=float(v["odd"])
            elif v["value"]=="Draw": draw=float(v["odd"])
            elif v["value"]=="Away": away=float(v["odd"])
        if home and draw and away:
            total=1/home+1/draw+1/away
            return round((1/draw)/total*100),draw
    except: pass
    return 0,0

def get_h2h(home_id,away_id):
    r=requests.get(f"https://v3.football.api-sports.io/fixtures/headtohead?h2h={home_id}-{away_id}&last=10",headers=HEADERS)
    matches=r.json().get("response",[])
    if not matches: return 0,0
    draws=sum(1 for m in matches if m["score"]["fulltime"]["home"]==m["score"]["fulltime"]["away"])
    avg_goals=sum((m["score"]["fulltime"]["home"] or 0)+(m["score"]["fulltime"]["away"] or 0) for m in matches)/len(matches)
    return round(draws/len(matches)*100),round(avg_goals,1)

def get_team_stats(team_id,league_id,season):
    r=requests.get(f"https://v3.football.api-sports.io/teams/statistics?team={team_id}&league={league_id}&season={season}",headers=HEADERS)
    try:
        s=r.json()["response"]
        total=s["fixtures"]["played"]["total"] or 1
        draws=s["fixtures"]["draws"]["total"] or 0
        goals_for=s["goals"]["for"]["average"]["total"] or "0"
        goals_against=s["goals"]["against"]["average"]["total"] or "0"
        return round(draws/total*100),float(goals_for),float(goals_against)
    except: return 0,0,0

def calc_edge(bk_pct,h2h_pct,home_dr,away_dr,avg_goals):
    low_goals=max(0,min(100,(3.0-avg_goals)*20)) if avg_goals>0 else 50
    form_avg=(home_dr+away_dr)/2
    our_pct=(h2h_pct*0.30+form_avg*0.35+low_goals*0.20+bk_pct*0.15)
    edge=our_pct-bk_pct
    return round(our_pct),round(edge,1)

all_messages=[]
total_requests=0

for day_offset in range(3):
    d=(date.today()+timedelta(days=day_offset)).strftime("%Y-%m-%d")
    display=datetime.strptime(d,"%Y-%m-%d").strftime("%d/%m/%Y")
    label=["Today","Tomorrow","Day after tomorrow"][day_offset]

    fixtures=get_fixtures(d)
    total_requests+=1
    print(f"\n{label}: {len(fixtures)} fixtures")

    # Step 1: odds filter - top candidates
    candidates=[]
    count=0
    for f in fixtures:
        if count>=20: break
        if f["league"]["country"] in AFRICA: continue
        fid=f["fixture"]["id"]
        draw_pct,draw_odd=get_odds(fid)
        total_requests+=1
        count+=1
        if draw_pct>=30 and draw_odd>=2.8:
            candidates.appen
