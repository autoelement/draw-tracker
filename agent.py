import os
import json
import requests
from datetime import date
import google.generativeai as genai

# --- კონფიგურაცია ---
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

genai.configure(api_key=GEMINI_API_KEY)

TODAY = date.today().strftime("%Y-%m-%d")
TODAY_DISPLAY = date.today().strftime("%d/%m/%Y")


def find_top_draws():
    """Gemini-ს გამოყენებით მოძებნის დღევანდელ Top-5 ფრს"""
    model = genai.GenerativeModel(
    model_name="gemini-1.5-flash"
    )

    prompt = f"""
დღეს არის {TODAY_DISPLAY}.

შეძებე ინტერნეტში დღევანდელი ფეხბურთის მატჩები სადაც ფრის (X) ალბათობა ყველაზე მაღალია.
გამოიყენე Forebet, Sofascore, Betexplorer ან სხვა პროგნოზის საიტები.

დააბრუნე მხოლოდ JSON ფორმატში Top-5 მატჩი ფრის ალბათობის მიხედვით (მაღლიდან დაბლა):

{{
  "matches": [
    {{
      "home": "სახლის გუნდი",
      "away": "სტუმარი გუნდი", 
      "league": "ლიგის სახელი",
      "draw_pct": 38,
      "pred_score": "1-1",
      "kickoff": "21:00"
    }}
  ]
}}

მხოლოდ JSON, სხვა ტექსტი არ დაამატო.
"""

    response = model.generate_content(prompt)
    text = response.text.strip()

    # JSON გამოყოფა
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    data = json.loads(text)
    return data["matches"]


def save_to_supabase(matches):
    """მატჩები Supabase-ში ჩაწერა"""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    rows = []
    for m in matches:
        rows.append({
            "date": TODAY,
            "home": m["home"],
            "away": m["away"],
            "league": m.get("league", ""),
            "draw_pct": m.get("draw_pct", 0),
            "pred_score": m.get("pred_score", ""),
            "kickoff": m.get("kickoff", ""),
            "outcome": "pending"
        })

    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/matches",
        headers=headers,
        json=rows
    )
    print(f"Supabase: {resp.status_code}")
    return resp.status_code in [200, 201]


def send_telegram(matches):
    """Telegram-ში შეტყობინების გაგზავნა"""
    lines = [f"⚽ *Draw Tracker · {TODAY_DISPLAY}*\n"]

    for i, m in enumerate(matches, 1):
        lines.append(
            f"{i}\\. {m['home']} vs {m['away']}\n"
            f"   🟡 X: *{m['draw_pct']}%* | {m['pred_score']} | {m['kickoff']}\n"
            f"   _{m.get('league', '')}_\n"
        )

    lines.append("\n_ანგარიში ღამით განახლდება_ 🔄")
    text = "\n".join(lines)

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "MarkdownV2"
    })
    print(f"Telegram: {resp.status_code}")


def main():
    print(f"🔍 მოძებნა იწყება: {TODAY}")
    matches = find_top_draws()
    print(f"✅ {len(matches)} მატჩი ნაპოვნია")

    save_to_supabase(matches)
    send_telegram(matches)
    print("🎉 დასრულდა!")


if __name__ == "__main__":
    main()
