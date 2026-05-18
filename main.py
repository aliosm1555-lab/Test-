import os
import requests
import schedule
import time
import threading
from datetime import datetime

# ─── إعدادات ───────────────────────────────────────────
TELEGRAM_TOKEN  = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GROQ_API_KEY    = os.environ.get("GROQ_API_KEY")
NEWSAPI_KEY     = os.environ.get("NEWSAPI_KEY")

# ─── البرومبت ───────────────────────────────────────────
SYSTEM_PROMPT = open("system_prompt.txt", encoding="utf-8").read()

# ─── التحليل عبر Groq ───────────────────────────────────
def analyze(user_message):
    try:
        res = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                "max_tokens": 2048,
                "temperature": 0.7
            },
            timeout=60
        )
        data = res.json()
        print("Groq response status:", res.status_code)

        if res.status_code != 200:
            return f"خطأ من Groq ({res.status_code}): {data.get('error', {}).get('message', str(data))}"

        return data["choices"][0]["message"]["content"]

    except Exception as e:
        return f"خطأ: {str(e)}"

# ─── جلب البيانات ───────────────────────────────────────
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
        return f"خطأ الأخبار: {e}"

def get_fed():
    try:
        lines = requests.get(
            "https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS",
            timeout=10
        ).text.strip().split("\n")
        last = lines[-1].split(",")
        return f"معدل الفائدة الفيدرالي: {last[1]}% ({last[0]})"
    except Exception as e:
        return f"خطأ الفائدة: {e}"

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
        return f"خطأ العملات: {e}"

# ─── إرسال Telegram ─────────────────────────────────────
def send_telegram(message, chat_id=None):
    try:
        cid = chat_id or TELEGRAM_CHAT_ID
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        for part in [message[i:i+4000] for i in range(0, len(message), 4000)]:
            requests.post(url, json={
                "chat_id": cid,
                "text": part,
                "parse_mode": "Markdown"
            }, timeout=15)
        print(f"✅ أرسل — {datetime.now().strftime('%H:%M')}")
    except Exception as e:
        print(f"❌ خطأ Telegram: {e}")

# ─── التقرير الأسبوعي ───────────────────────────────────
def weekly_analysis(chat_id=None):
    send_telegram("⏳ جاري جلب البيانات...", chat_id)
    news = get_news()
    fed  = get_fed()
    fx   = get_fx()
    send_telegram("📡 البيانات جاهزة — جاري التحليل...", chat_id)

    msg = f"""أعد تقريراً أسبوعياً احترافياً باللغة العربية.

الأخبار:
{news}

الفائدة الأمريكية:
{fed}

أسعار العملات:
{fx}

اكتب تقريراً شاملاً: مراجعة الأسبوع، أجندة الأسبوع القادم، السيناريوهات، التوصية."""

    result = analyze(msg)
    send_telegram(
        f"📊 *التقرير الأسبوعي — {datetime.now().strftime('%Y/%m/%d %H:%M')}*\n\n{result}",
        chat_id
    )

# ─── فحص الأخبار ────────────────────────────────────────
def check_news(chat_id=None, force=False):
    if force:
        send_telegram("⏳ جاري فحص الأخبار...", chat_id)
    news = get_news()
    keywords = ["rate hike","rate cut","crisis","recession","war",
                "sanctions","collapse","surprise","shock","emergency"]
    is_urgent = any(k in news.lower() for k in keywords)

    if not is_urgent and not force:
        print("لا يوجد شيء عاجل.")
        return

    msg = f"""قدم تحليلاً احترافياً باللغة العربية للأخبار التالية:

الأخبار:
{news}

العملات:
{get_fx()}

الفائدة:
{get_fed()}"""

    result = analyze(msg)
    header = "⚡ *تنبيه عاجل*\n\n" if is_urgent else f"📰 *تقرير الأخبار — {datetime.now().strftime('%H:%M')}*\n\n"
    send_telegram(header + result, chat_id)

# ─── استقبال الأوامر ────────────────────────────────────
def listen_commands():
    offset = None
    print("👂 يستمع للأوامر...")
    while True:
        try:
            updates = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
                params={"timeout": 30, "offset": offset},
                timeout=35
            ).json()

            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                msg  = update.get("message", {})
                text = msg.get("text", "").strip()
                cid  = str(msg.get("chat", {}).get("id", ""))
                print(f"📩 {text} من {cid}")

                if text in ["/تقرير", "/report"]:
                    threading.Thread(target=weekly_analysis, args=(cid,)).start()
                elif text in ["/اخبار", "/news"]:
                    threading.Thread(target=check_news, args=(cid, True)).start()
                elif text in ["/حالة", "/status"]:
                    send_telegram(
                        f"✅ *النظام يعمل*\n🕐 {datetime.now().strftime('%Y/%m/%d %H:%M')}\n"
                        f"📅 التقرير: كل أحد 6 مساءً\n⚡ فحص الأخبار: كل ساعة", cid
                    )
                elif text in ["/مساعدة", "/help"]:
                    send_telegram(
                        "📋 *الأوامر:*\n\n/تقرير — تقرير أسبوعي\n"
                        "/اخبار — تحليل الأخبار\n/حالة — حالة النظام\n"
                        "/مساعدة — هذه القائمة", cid
                    )
        except Exception as e:
            print(f"❌ خطأ استماع: {e}")
            time.sleep(5)

# ─── الجدولة ────────────────────────────────────────────
schedule.every().sunday.at("18:00").do(weekly_analysis)
schedule.every(1).hours.do(check_news)

# ─── بدء التشغيل ────────────────────────────────────────
print("🚀 النظام يعمل...")
send_telegram(
    "✅ *نظام التحليل الأساسي يعمل*\nد. كمال منصور جاهز 🎓\n\n"
    "📋 *الأوامر:*\n/تقرير\n/اخبار\n/حالة\n/مساعدة"
)
threading.Thread(target=listen_commands, daemon=True).start()

while True:
    schedule.run_pending()
    time.sleep(60)
                
