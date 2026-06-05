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
SH={"apikey":SKEY,"Authorization":f"Bearer {SKEY}","Content-Type":"application/json"}

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
        goals_for=float(s["goals"]["for"]["average"]["total"] or 0)
        goals_against=float(s["goals"]["against"]["average"]["total"] or 0)
        return round(draws/total*100),goals_for,goals_against
    except: return 0,0,0

def calc_edge(bk_pct,h2h_pct,home_dr,away_dr,avg_goals):
    h2h=h2h_pct if h2h_pct>0 else bk_pct
    form_avg=(home_dr+away_dr)/2 if (home_dr+away_dr)>0 else bk_pct
    low_goals=max(0,min(100,(3.0-avg_goals)*20)) if avg_goals>0 else bk_pct
    our_pct=(h2h*0.25+form_avg*0.30+low_goals*0.15+bk_pct*0.30)
    edge=our_pct-bk_pct
    return round(our_pct),round(edge,1)

# ---- SAVE UPCOMING MATCHES TO SUPABASE ----
def save_upcoming_matches():
    print("\nSaving upcoming matches to Supabase...")
    # Delete old upcoming matches (older than today)
    today=date.today().strftime("%Y-%m-%d")
    requests.delete(f"{SURL}/rest/v1/upcoming_matches?kickoff=lt.{today}",headers=SH)
    
    all_fixtures=[]
    for day_offset in range(7):
        d=(date.today()+timedelta(days=day_offset)).strftime("%Y-%m-%d")
        fixtures=get_fixtures(d)
        for f in fixtures:
            if f["league"]["country"] in AFRICA: continue
            try:
                dt=datetime.fromisoformat(f["fixture"]["date"].replace("Z","+00:00"))
                kickoff=dt.isoformat()
            except:
                kickoff=f["fixture"]["date"]
            all_fixtures.append({
                "fixture_id":f["fixture"]["id"],
                "home":f["teams"]["home"]["name"],
                "away":f["teams"]["away"]["name"],
                "league":f["league"]["name"],
                "country":f["league"]["country"],
                "kickoff":kickoff,
                "season":f["league"]["season"]
            })
    
    if all_fixtures:
        # Insert in batches of 100
        for i in range(0,len(all_fixtures),100):
            batch=all_fixtures[i:i+100]
            requests.post(f"{SURL}/rest/v1/upcoming_matches",headers=SH,json=batch)
        print(f"  Saved {len(all_fixtures)} upcoming matches")
    return len(all_fixtures)

# Save upcoming matches first
saved=save_upcoming_matches()
total_requests=3  # fixtures for 7 days

all_messages=[]

for day_offset in range(3):
    d=(date.today()+timedelta(days=day_offset)).strftime("%Y-%m-%d")
    display=datetime.strptime(d,"%Y-%m-%d").strftime("%d/%m/%Y")
    label=["Today","Tomorrow","Day after tomorrow"][day_offset]

    fixtures=get_fixtures(d)
    total_requests+=1
    print(f"\n{label}: {len(fixtures)} fixtures")

    candidates=[]
    count=0
    for f in fixtures:
        if count>=25: break
        if f["league"]["country"] in AFRICA: continue
        fid=f["fixture"]["id"]
        draw_pct,draw_odd=get_odds(fid)
        total_requests+=1
        count+=1
        if draw_pct>=25:
            candidates.append({
                "fid":fid,
                "home":f["teams"]["home"]["name"],
                "away":f["teams"]["away"]["name"],
                "home_id":f["teams"]["home"]["id"],
                "away_id":f["teams"]["away"]["id"],
                "league":f["league"]["name"],
                "league_id":f["league"]["id"],
                "season":f["league"]["season"],
                "country":f["league"]["country"],
                "date":f["fixture"]["date"],
                "draw_pct":draw_pct,
                "draw_odd":round(draw_odd,2)
            })

    candidates.sort(key=lambda x:x["draw_pct"],reverse=True)
    top10=candidates[:10]
    print(f"  Candidates: {len(top10)}")

    scored=[]
    for m in top10:
        if total_requests>=88: break
        h2h_pct,avg_goals=get_h2h(m["home_id"],m["away_id"])
        total_requests+=1
        home_dr,hgf,hga=get_team_stats(m["home_id"],m["league_id"],m["season"])
        total_requests+=1
        away_dr,agf,aga=get_team_stats(m["away_id"],m["league_id"],m["season"])
        total_requests+=1
        combined_avg=(hgf+agf)/2
        our_pct,edge=calc_edge(m["draw_pct"],h2h_pct,home_dr,away_dr,combined_avg)
        try:
            dt=datetime.fromisoformat(m["date"].replace("Z","+00:00"))
            kickoff=dt.astimezone(TZ).strftime("%H:%M")
        except:
            kickoff=m["date"][11:16]
        scored.append({**m,"h2h_pct":h2h_pct,"avg_goals":avg_goals,"home_dr":home_dr,"away_dr":away_dr,"our_pct":our_pct,"edge":edge,"kickoff":kickoff})
        print(f"  {m['home']} vs {m['away']}: bk={m['draw_pct']}% our={our_pct}% edge={edge}%")

    top5=sorted([x for x in scored if x["edge"]>=3],key=lambda x:x["edge"],reverse=True)[:5]

    if top5:
        # Claude analysis
        prompt="You are an expert football betting analyst specializing in draw predictions.\n\n"
        prompt+="Analyze these matches and provide a brief insight for each:\n\n"
        for i,x in enumerate(top5,1):
            prompt+=f"{i}. {x['home']} vs {x['away']} ({x['league']}, {x['country']})\n"
            prompt+=f"   Kickoff: {x['kickoff']} Tbilisi | Bk draw: {x['draw_pct']}% | Our model: {x['our_pct']}% | Edge: +{x['edge']}%\n"
            prompt+=f"   Draw odds: {x['draw_odd']} | H2H draw rate: {x['h2h_pct']}% | Avg goals H2H: {x['avg_goals']}\n"
            prompt+=f"   Home draw rate: {x['home_dr']}% | Away draw rate: {x['away_dr']}%\n\n"
        prompt+="For each match write ONE concise sentence: key reason + action (Bet/Skip/Watch).\n"
        prompt+='Return ONLY JSON: {"matches":[{"home":"t1","away":"t2","analysis":"one sentence","action":"Bet","pred_score":"1-1"}]}'

        try:
            r=requests.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key":AKEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
                json={"model":"claude-haiku-4-5-20251001","max_tokens":1000,"messages":[{"role":"user","content":prompt}]})
            txt=r.json()["content"][0]["text"].strip()
            m=re.search(r'\{[\s\S]*"matches"[\s\S]*\}',txt)
            if m: txt=m.group()
            analyses={a["home"]+a["away"]:a for a in json.loads(txt)["matches"]}
        except:
            analyses={}

        section=f"📅 {label} · {display}\n"
        for i,x in enumerate(top5,1):
            key=x["home"]+x["away"]
            ana=analyses.get(key,{})
            action=ana.get("action","")
            action_emoji={"Bet":"✅","Skip":"❌","Watch":"👀"}.get(action,"")
            pred=ana.get("pred_score","")
            analysis=ana.get("analysis","")
            section+=f"{i}. {x['home']} vs {x['away']}\n"
            section+=f"   📊 Bk: {x['draw_pct']}% → Our: {x['our_pct']}% | Edge: +{x['edge']}%\n"
            section+=f"   🔢 Odds: {x['draw_odd']} | H2H: {x['h2h_pct']}% | Goals: {x['avg_goals']}\n"
            section+=f"   ⏰ {x['kickoff']} | {x['league']}\n"
            if analysis: section+=f"   {action_emoji} {analysis}\n"
            if pred: section+=f"   🎯 {pred}\n"
            section+="\n"
        all_messages.append(section)

        rows=[{"date":d,"home":x["home"],"away":x["away"],"league":x["league"],"draw_pct":x["our_pct"],"pred_score":"","kickoff":x["kickoff"],"outcome":"pending","fixture_id":x["fid"]} for x in top5]
        requests.post(f"{SURL}/rest/v1/matches",headers=SH,json=rows)
    else:
        all_messages.append(f"📅 {label} · {display}\n❌ No edge found (edge<3%)\n")

print(f"\nTotal API requests: {total_requests}/100")
final=f"⚽ Draw Tracker · 3 Days\n📊 Edge Model | Tbilisi Time\n📋 Saved {saved} upcoming matches\n\n"
final+="\n".join(all_messages)
final+=f"\n🔢 API calls: {total_requests}/100"
requests.post(f"https://api.telegram.org/bot{TTOKEN}/sendMessage",json={"chat_id":TCHAT,"text":final})
print("Done!")
