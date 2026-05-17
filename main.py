import os
import requests
import schedule
import time
import threading
from datetime import datetime

# ─── إعدادات ───────────────────────────────────────────
TELEGRAM_TOKEN     = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
NEWSAPI_KEY        = os.environ.get("NEWSAPI_KEY")

# ─── البرومبت ───────────────────────────────────────────
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
        return f"خطأ: {e}"

def get_fed():
    try:
        lines = requests.get(
            "https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS",
            timeout=10
        ).text.strip().split("\n")
        last = lines[-1].split(",")
        return f"معدل الفائدة الفيدرالي: {last[1]}% ({last[0]})"
    except Exception as e:
        return f"خطأ: {e}"

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
        return f"خطأ: {e}"

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
    send_telegram("⏳ جاري إعداد التقرير، انتظر لحظة...", chat_id)
    msg = f"""
أعد التقرير الأسبوعي الكامل الآن.

الأخبار:
{get_news()}

الفائدة الأمريكية:
{get_fed()}

أسعار العملات:
{get_fx()}

قدم: مراجعة الأسبوع، أجندة الأسبوع القادم، السيناريوهات، التوصية.
"""
    try:
        result = analyze(msg)
        send_telegram(
            f"📊 *التقرير الأسبوعي — {datetime.now().strftime('%Y/%m/%d %H:%M')}*\n\n" + result,
            chat_id
        )
    except Exception as e:
        send_telegram(f"❌ خطأ في التحليل: {e}", chat_id)

# ─── فحص الأخبار العاجلة ────────────────────────────────
def check_news(chat_id=None, force=False):
    send_telegram("⏳ جاري فحص الأخبار...", chat_id) if force else None
    news = get_news()
    keywords = ["rate hike","rate cut","crisis","recession","war",
                "sanctions","collapse","surprise","shock","emergency"]
    is_urgent = any(k in news.lower() for k in keywords)

    if not is_urgent and not force:
        print("لا يوجد شيء عاجل.")
        return

    msg = f"""
{"خبر عاجل — حلله فوراً." if is_urgent else "تقرير الأخبار الاقتصادية الحالية."}

الأخبار:
{news}

العملات:
{get_fx()}

الفائدة:
{get_fed()}

قدم تحليلاً كاملاً للوضع الحالي.
"""
    try:
        result = analyze(msg)
        header = f"⚡ *تنبيه عاجل*\n\n" if is_urgent else f"📰 *تقرير الأخبار — {datetime.now().strftime('%H:%M')}*\n\n"
        send_telegram(header + result, chat_id)
    except Exception as e:
        send_telegram(f"❌ خطأ: {e}", chat_id)

# ─── استقبال الأوامر من Telegram ────────────────────────
def listen_commands():
    offset = None
    print("👂 يستمع للأوامر...")
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            params = {"timeout": 30, "offset": offset}
            updates = requests.get(url, params=params, timeout=35).json()

            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                text = msg.get("text", "").strip()
                chat_id = str(msg.get("chat", {}).get("id", ""))

                print(f"📩 أمر: {text} من {chat_id}")

                if text == "/تقرير" or text == "/report":
                    threading.Thread(
                        target=weekly_analysis, args=(chat_id,)
                    ).start()

                elif text == "/اخبار" or text == "/news":
                    threading.Thread(
                        target=check_news, args=(chat_id, True)
                    ).start()

                elif text == "/حالة" or text == "/status":
                    send_telegram(
                        f"✅ *النظام يعمل بشكل طبيعي*\n"
                        f"🕐 الوقت: {datetime.now().strftime('%Y/%m/%d %H:%M')}\n"
                        f"📅 التقرير الأسبوعي: كل أحد 6 مساءً\n"
                        f"⚡ فحص الأخبار: كل ساعة",
                        chat_id
                    )

                elif text == "/مساعدة" or text == "/help":
                    send_telegram(
                        "📋 *الأوامر المتاحة:*\n\n"
                        "/تقرير — تقرير أسبوعي كامل الآن\n"
                        "/اخبار — تحليل الأخبار الحالية\n"
                        "/حالة  — التحقق من حالة النظام\n"
                        "/مساعدة — عرض هذه القائمة",
                        chat_id
                    )

        except Exception as e:
            print(f"❌ خطأ في الاستماع: {e}")
            time.sleep(5)

# ─── الجدولة ────────────────────────────────────────────
schedule.every().sunday.at("18:00").do(weekly_analysis)
schedule.every(1).hours.do(check_news)

# ─── بدء التشغيل ────────────────────────────────────────
print("🚀 النظام يعمل...")
send_telegram(
    "✅ *نظام التحليل الأساسي يعمل*\n"
    "د. كمال منصور جاهز 🎓\n\n"
    "📋 *الأوامر المتاحة:*\n"
    "/تقرير — تقرير أسبوعي كامل\n"
    "/اخبار — تحليل الأخبار الحالية\n"
    "/حالة  — حالة النظام\n"
    "/مساعدة — قائمة الأوامر"
)

# ─── تشغيل الاستماع في thread منفصل ────────────────────
threading.Thread(target=listen_commands, daemon=True).start()

# ─── الحلقة الرئيسية ────────────────────────────────────
while True:
    schedule.run_pending()
    time.sleep(60)
