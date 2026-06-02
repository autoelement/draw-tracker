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


def get_todays_matches():
    """დღევანდელი pending მატჩები Supabase-იდან"""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/matches?date=eq.{TODAY}&outcome=eq.pending&select=*",
        headers=headers
    )
    return resp.json()


def check_results(matches):
    """Gemini-ს გამოყენებით შედეგების მოძებნა"""
    if not matches:
        return []

    model = genai.GenerativeModel(
    model_name="gemini-2.0-flash"
    )

    match_list = "\n".join([
        f"- {m['home']} vs {m['away']} ({m['league']})"
        for m in matches
    ])

    prompt = f"""
დღეს არის {TODAY_DISPLAY}.

შეამოწმე ამ მატჩების საბოლოო შედეგები:
{match_list}

დააბრუნე JSON:
{{
  "results": [
    {{
      "home": "სახლის გუნდი",
      "away": "სტუმარი გუნდი",
      "result": "1-1",
      "outcome": "win"
    }}
  ]
}}

outcome = "win" თუ ფრი დასრულდა, "loss" თუ არა, "pending" თუ ჯერ არ დასრულებულა.
მხოლოდ JSON, სხვა ტექსტი არ დაამატო.
"""

    response = model.generate_content(prompt)
    text = response.text.strip()

    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    data = json.loads(text)
    return data["results"]


def update_supabase(match_id, result, outcome):
    """შედეგი Supabase-ში განახლება"""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/matches?id=eq.{match_id}",
        headers=headers,
        json={"result": result, "outcome": outcome}
    )
    return resp.status_code in [200, 204]


def send_results_telegram(matches, results):
    """შედეგების შეტყობინება Telegram-ში"""
    results_map = {
        f"{r['home']}|{r['away']}": r
        for r in results
    }

    wins = 0
    lines = [f"📊 *შედეგები · {TODAY_DISPLAY}*\n"]

    for m in matches:
        key = f"{m['home']}|{m['away']}"
        r = results_map.get(key, {})
        outcome = r.get("outcome", "pending")
        result = r.get("result", "?")

        if outcome == "win":
            emoji = "✅"
            wins += 1
        elif outcome == "loss":
            emoji = "❌"
        else:
            emoji = "⏳"

        home = m['home'].replace('.', '\\.').replace('-', '\\-').replace('(', '\\(').replace(')', '\\)')
        away = m['away'].replace('.', '\\.').replace('-', '\\-').replace('(', '\\(').replace(')', '\\)')

        lines.append(f"{emoji} {home} vs {away}: *{result}*")

    total = len(matches)
    lines.append(f"\n🏆 *{wins}/{total}* მოგება დღეს")

    text = "\n".join(lines)
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "MarkdownV2"
    })
    print(f"Telegram: {resp.status_code}")


def main():
    print(f"🔍 შედეგების შემოწმება: {TODAY}")
    matches = get_todays_matches()

    if not matches:
        print("მატჩები ვერ მოიძებნა")
        return

    print(f"✅ {len(matches)} მატჩი შესამოწმებელი")
    results = check_results(matches)

    results_map = {
        f"{r['home']}|{r['away']}": r
        for r in results
    }

    for m in matches:
        key = f"{m['home']}|{m['away']}"
        r = results_map.get(key, {})
        if r.get("outcome") != "pending":
            update_supabase(m["id"], r.get("result", ""), r.get("outcome", "pending"))

    send_results_telegram(matches, results)
    print("🎉 დასრულდა!")


if __name__ == "__main__":
    main()
