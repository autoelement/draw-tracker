import os
import json
import requests
from datetime import date

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

TODAY = date.today().strftime("%Y-%m-%d")
TODAY_DISPLAY = date.today().strftime("%d/%m/%Y")

def find_top_draws():
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"""დღეს არის {TODAY_DISPLAY}. იპოვე დღევანდელი ფეხბურთის Top-5 მატჩი სადაც ფრის ალბათობა ყველაზე მაღალია. გამოიყენე Forebet და სხვა საიტები. დააბრუნე მხოლოდ JSON:
{{"matches":[{{"home":"გუნდი1","away":"გუნდი2","league":"ლიგა","draw_pct":35,"pred_score":"1-1","kickoff":"21:00"}}]}}
მხოლოდ JSON, სხვა ტექსტი არ დაამატო."""
    resp = requests.post(url, json={"contents":[{"parts":[{"text":prompt}]}]})
    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    return json.loads(text)["matches"]

def save_to_supabase(matches):
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
    rows = [{"date": TODAY, "home": m["home"], "away": m["away"], "league": m.get("league",""), "draw_pct": m.get("draw_pct",0), "pred_score": m.get("pred_score",""), "kickoff": m.get("kickoff",""), "outcome": "pending"} for m in matches]
    requests.post(f"{SUPABASE_URL}/rest/v1/matches", headers=headers, json=rows)

def send_telegram(matches):
    lines = [f"⚽ Draw Tracker · {TODAY_DISPLAY}\n"]
    for i, m in enumerate(matches, 1):
        lines.append(f"{i}. {m['home']} vs {m['away']}\n   X: {m['draw_pct']}% | {m['pred_score']} | {m['kickoff']}\n   {m.get('league','')}\n")
    lines.append("\nანგარიში ღამით განახლდება 🔄")
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT_ID, "text": "\n".join(lines)})

def main():
    print(f"მოძებნა იწყება: {TODAY}")
    matches = find_top_draws()
    print(f"{len(matches)} მატჩი ნაპოვნია")
    save_to_supabase(matches)
    send_telegram(matches)
    print("დასრულდა!")

if __name__ == "__main__":
    main()
