import os
import requests
import schedule
import time
from datetime import datetime

# ─── إعدادات ───────────────────────────────────────────
TELEGRAM_TOKEN    = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID  = os.environ.get("TELEGRAM_CHAT_ID")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
NEWSAPI_KEY       = os.environ.get("NEWSAPI_KEY")

# ─── البرومبت الاحترافي ─────────────────────────────────
SYSTEM_PROMPT = open("system_prompt.txt", encoding="utf-8").read()

# ─── التحليل عبر OpenRouter ────────────────────────────
def analyze(user_message):
    res = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "mistralai/mistral-7b-instruct:free",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ]
        },
        timeout=60
    )
    return res.json()["choices"][0]["message"]["content"]

# ─── جلب الأخبار ────────────────────────────────────────
def get_news():
    try:
        url = (
            f"https://newsapi.org/v2/everything"
            f"?q=Federal+Reserve+OR+ECB+OR+inflation+OR+forex"
            f"&language=en&sortBy=publishedAt&pageSize=5"
            f"&apiKey={NEWSAPI_KEY}"
        )
        articles = requests.get(url, timeout=10).json().get("articles", [])
        if not articles:
            return "لا توجد أخبار حالياً."
        return "\n".join([f"{i+1}. {a['title']} — {a['source']['name']}"
                          for i, a in enumerate(articles)])
    except Exception as e:
        return f"خطأ في الأخبار: {e}"

# ─── جلب الفائدة الأمريكية ──────────────────────────────
def get_fed():
    try:
        lines = requests.get(
            "https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS",
            timeout=10
        ).text.strip().split("\n")
        last = lines[-1].split(",")
        return f"معدل الفائدة الفيدرالي: {last[1]}% ({last[0]})"
    except Exception as e:
        return f"خطأ في الفائدة: {e}"

# ─── جلب أسعار العملات ──────────────────────────────────
def get_fx():
    try:
        rates = requests.get(
            "https://open.er-api.com/v6/latest/USD", timeout=10
        ).json().get("rates", {})
        return (
            f"EUR/USD: {round(1/rates.get('EUR',1),5)}\n"
            f"GBP/USD: {round(1/rates.get('GBP',1),5)}\n"
            f"USD/JPY: {round(rates.get('JPY',0),3)}\n"
            f"USD/CAD: {round(rates.get('CAD',0),5)}\n"
            f"AUD/USD: {round(1/rates.get('AUD',1),5)}"
        )
    except Exception as e:
        return f"خطأ في العملات: {e}"

# ─── إرسال Telegram ─────────────────────────────────────
def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        for part in [message[i:i+4000] for i in range(0, len(message), 4000)]:
            requests.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": part,
                "parse_mode": "Markdown"
            }, timeout=15)
        print(f"✅ أرسل — {datetime.now().strftime('%H:%M')}")
    except Exception as e:
        print(f"❌ خطأ Telegram: {e}")

# ─── التقرير الأسبوعي ───────────────────────────────────
def weekly_analysis():
    print("🔄 التقرير الأسبوعي...")
    msg = f"""
أعد التقرير الأسبوعي الكامل.

الأخبار:
{get_news()}

الفائدة الأمريكية:
{get_fed()}

أسعار العملات:
{get_fx()}

قدم: مراجعة الأسبوع، أجندة الأسبوع القادم، السيناريوهات، التوصية.
"""
    try:
        send_telegram(f"📊 *التقرير الأسبوعي — {datetime.now().strftime('%Y/%m/%d')}*\n\n" + analyze(msg))
    except Exception as e:
        send_telegram(f"❌ خطأ: {e}")

# ─── فحص الأخبار العاجلة ────────────────────────────────
def check_news():
    print("🔍 فحص الأخبار...")
    news = get_news()
    keywords = ["rate hike","rate cut","crisis","recession","war","sanctions","collapse","surprise","shock"]
    if not any(k in news.lower() for k in keywords):
        print("لا يوجد شيء عاجل.")
        return
    print("⚡ خبر عاجل!")
    msg = f"""
خبر عاجل — حلله فوراً.

الأخبار:
{news}

العملات:
{get_fx()}

الفائدة:
{get_fed()}
"""
    try:
        send_telegram(f"⚡ *تنبيه عاجل — {datetime.now().strftime('%H:%M')}*\n\n" + analyze(msg))
    except Exception as e:
        print(f"❌ خطأ: {e}")

# ─── الجدولة ────────────────────────────────────────────
schedule.every().sunday.at("18:00").do(weekly_analysis)
schedule.every(1).hours.do(check_news)

# ─── بدء التشغيل ────────────────────────────────────────
print("🚀 النظام يعمل...")
send_telegram("✅ *نظام التحليل الأساسي يعمل*\nد. كمال منصور جاهز 🎓")

while True:
    schedule.run_pending()
    time.sleep(60)
    
