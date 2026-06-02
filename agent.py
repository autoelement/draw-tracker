import os,json,requests
from datetime import date

KEY=os.environ["GEMINI_API_KEY"]
SURL=os.environ["SUPABASE_URL"]
SKEY=os.environ["SUPABASE_KEY"]
TTOKEN=os.environ["TELEGRAM_BOT_TOKEN"]
TCHAT=os.environ["TELEGRAM_CHAT_ID"]
TODAY=date.today().strftime("%Y-%m-%d")
TODAYD=date.today().strftime("%d/%m/%Y")

url=f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={KEY}"
prompt=f"დღეს არის {TODAYD}. იპოვე დღევანდელი ფეხბურთის Top-5 მატჩი სადაც ფრის ალბათობა ყველაზე მაღალია Forebet-ზე. დააბრუნე მხოლოდ JSON ფორმატში: {{\"matches\":[{{\"home\":\"გუნდი1\",\"away\":\"გუნდი2\",\"league\":\"ლიგა\",\"draw_pct\":35,\"pred_score\":\"1-1\",\"kickoff\":\"21:00\"}}]}}"
r=requests.post(url,json={"contents":[{"parts":[{"text":prompt}]}]})
print(r.json())
data=r.json()
if "candidates" not in data:
    raise Exception(str(data))
text=data["candidates"][0]["content"]["parts"][0]["text"].strip()
if "```json" in text:
    text=text.split("```json")[1].split("```")[0].strip()
elif "```" in text:
    text=text.split("```")[1].split("```")[0].strip()
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
