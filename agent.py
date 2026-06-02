import os,json,requests,re
from datetime import date

AKEY=os.environ["ANTHROPIC_API_KEY"]
SURL=os.environ["SUPABASE_URL"]
SKEY=os.environ["SUPABASE_KEY"]
TTOKEN=os.environ["TELEGRAM_BOT_TOKEN"]
TCHAT=os.environ["TELEGRAM_CHAT_ID"]
TODAY=date.today().strftime("%Y-%m-%d")
TODAYD=date.today().strftime("%d/%m/%Y")

payload={"model":"claude-sonnet-4-6","max_tokens":2000,"tools":[{"type":"web_search_20250305","name":"web_search"}],"messages":[{"role":"user","content":f"Search the web for football matches on {TODAYD} with highest draw probability. Search forebet.com and sofascore.com. Find top 5 matches where draw probability is highest. After searching, return ONLY a JSON object like this, no other text: {{\"matches\":[{{\"home\":\"Arsenal\",\"away\":\"Chelsea\",\"league\":\"EPL\",\"draw_pct\":38,\"pred_score\":\"1-1\",\"kickoff\":\"21:00\"}}]}}"}]}

r=requests.post("https://api.anthropic.com/v1/messages",headers={"x-api-key":AKEY,"anthropic-version":"2023-06-01","content-type":"application/json"},json=payload)
data=r.json()
print("status:",r.status_code)

text=""
for block in data.get("content",[]):
    if block.get("type")=="text":
        text+=block["text"]

print("response:",text[:500])

m=re.search(r'\{[\s\S]*"matches"[\s\S]*\}',text)
if not m:
    raise Exception("JSON ვერ მოიძებნა პასუხში: "+text[:300])

matches=json.loads(m.group())["matches"]
print(f"{len(matches)} match found")

h={"apikey":SKEY,"Authorization":f"Bearer {SKEY}","Content-Type":"application/json"}
rows=[{"date":TODAY,"home":x["home"],"away":x["away"],"league":x.get("league",""),"draw_pct":x.get("draw_pct",0),"pred_score":x.get("pred_score",""),"kickoff":x.get("kickoff",""),"outcome":"pending"} for x in matches]
resp=requests.post(f"{SURL}/rest/v1/matches",headers=h,json=rows)
print("supabase:",resp.status_code)

lines=[f"⚽ Draw Tracker · {TODAYD}\n"]
for i,x in enumerate(matches,1):
    lines.append(f"{i}. {x['home']} vs {x['away']} | X:{x['draw_pct']}% | {x['pred_score']} | {x['kickoff']} | {x.get('league','')}")
lines.append("\nანგარიში ღამით განახლდება 🔄")
resp2=requests.post(f"https://api.telegram.org/bot{TTOKEN}/sendMessage",json={"chat_id":TCHAT,"text":"\n".join(lines)})
print("telegram:",resp2.status_code)
print("დასრულდა!")
