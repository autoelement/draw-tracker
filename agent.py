import os,json,requests,re
from datetime import date

AKEY=os.environ["ANTHROPIC_API_KEY"]
SURL=os.environ["SUPABASE_URL"]
SKEY=os.environ["SUPABASE_KEY"]
TTOKEN=os.environ["TELEGRAM_BOT_TOKEN"]
TCHAT=os.environ["TELEGRAM_CHAT_ID"]
TODAY=date.today().strftime("%Y-%m-%d")
TODAYD=date.today().strftime("%d/%m/%Y")

r=requests.post("https://api.anthropic.com/v1/messages",headers={"x-api-key":AKEY,"anthropic-version":"2023-06-01","content-type":"application/json"},json={"model":"claude-sonnet-4-6","max_tokens":1000,"tools":[{"type":"web_search_20250305","name":"web_search"}],"messages":[{"role":"user","content":f"დღეს არის {TODAYD}. მოძებნე ინტერნეტში დღევანდელი ფეხბურთის მატჩები სადაც ფრის ალბათობა ყველაზე მაღალია. გამოიყენე Forebet.com. დააბრუნე Top-5 მატჩი მხოლოდ JSON ფორმატში: {{\"matches\":[{{\"home\":\"გუნდი1\",\"away\":\"გუნდი2\",\"league\":\"ლიგა\",\"draw_pct\":35,\"pred_score\":\"1-1\",\"kickoff\":\"21:00\"}}]}}"}]})
print(r.status_code)
data=r.json()
print(data)
text=""
for block in data.get("content",[]):
    if block.get("type")=="text":
        text=block["text"]
        break
print("პასუხი:",text[:300])
m=re.search(r'\{.*\}',text,re.DOTALL)
if m:
    text=m.group()
matches=json.loads(text)["matches"]
print(f"{len(matches)} მატჩი")

h={"apikey":SKEY,"Authorization":f"Bearer {SKEY}","Content-Type":"application/json"}
rows=[{"date":TODAY,"home":m["home"],"away":m["away"],"league":m.get("league",""),"draw_pct":m.get("draw_pct",0),"pred_score":m.get("pred_score",""),"kickoff":m.get("kickoff",""),"outcome":"pending"} for m in matches]
requests.post(f"{SURL}/rest/v1/matches",headers=h,json=rows)

lines=[f"⚽ Draw Tracker · {TODAYD}\n"]
for i,m in enumerate(matches,1):
    lines.append(f"{i}. {m['home']} vs {m['away']} | X:{m['draw_pct']}% | {m['pred_score']} | {m['kickoff']} | {m.get('league','')}")
lines.append("\nანგარიში ღამით განახლდება 🔄")
requests.post(f"https://api.telegram.org/bot{TTOKEN}/sendMessage",json={"chat_id":TCHAT,"text":"\n".join(lines)})
print("დასრულდა!")
