import os
import requests
import schedule
import time
from datetime import datetime
import google.generativeai as genai

# ─── إعدادات ───────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ.get("8905450316:AAHJFhI9BuZXhT_-uBS4Do2UTwnnZDsLy8g")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_API_KEY   = os.environ.get("AIzaSyDVqczwdGH3L69PMnfytEtqnAnD_tmw2IM")
NEWSAPI_KEY      = os.environ.get("97ce1c9acdca450d99981bba0ef96d17")

# ─── إعداد Gemini ───────────────────────────────────────
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# ─── البرومبت الاحترافي الكامل ─────────────────────────
SYSTEM_PROMPT = open("system_prompt.txt", encoding="utf-8").read()

# ─── جلب الأخبار الاقتصادية ────────────────────────────
def get_breaking_news():
    try:
        url = (
            f"https://newsapi.org/v2/everything"
            f"?q=Federal+Reserve+OR+ECB+OR+inflation+OR+interest+rate+OR+forex"
            f"&language=en"
            f"&sortBy=publishedAt"
            f"&pageSize=5"
            f"&apiKey={NEWSAPI_KEY}"
        )
        res = requests.get(url, timeout=10).json()
        articles = res.get("articles", [])
        if not articles:
            return "لا توجد أخبار جديدة حالياً."
        news_text = ""
        for i, a in enumerate(articles, 1):
            news_text += f"{i}. {a['title']}\n   المصدر: {a['source']['name']}\n\n"
        return news_text
    except Exception as e:
        return f"تعذر جلب الأخبار: {e}"

# ─── جلب بيانات الفائدة الأمريكية ─────────────────────
def get_fedwatch():
    try:
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS"
        res = requests.get(url, timeout=10)
        lines = res.text.strip().split("\n")
        last = lines[-1].split(",")
        return f"آخر قراءة لمعدل الفائدة الفيدرالي: {last[1]}% (تاريخ: {last[0]})"
    except Exception as e:
        return f"تعذر جلب بيانات الفائدة: {e}"

# ─── جلب أسعار العملات ─────────────────────────────────
def get_fx_rates():
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        res = requests.get(url, timeout=10).json()
        rates = res.get("rates", {})
        pairs = {
            "EUR/USD": round(1 / rates.get("EUR", 1), 5),
            "GBP/USD": round(1 / rates.get("GBP", 1), 5),
            "USD/JPY": round(rates.get("JPY", 0), 3),
            "USD/CAD": round(rates.get("CAD", 0), 5),
            "AUD/USD": round(1 / rates.get("AUD", 1), 5),
        }
        text = ""
        for pair, rate in pairs.items():
            text += f"• {pair}: {rate}\n"
        return text
    except Exception as e:
        return f"تعذر جلب أسعار العملات: {e}"

# ─── التحليل عبر Gemini ─────────────────────────────────
def analyze_with_gemini(user_message):
    full_prompt = SYSTEM_PROMPT + "\n\n" + user_message
    response = model.generate_content(full_prompt)
    return response.text

# ─── إرسال رسالة على Telegram ──────────────────────────
def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        max_len = 4000
        parts = [message[i:i+max_len] for i in range(0, len(message), max_len)]
        for part in parts:
            requests.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": part,
                "parse_mode": "Markdown"
            }, timeout=15)
        print(f"✅ تم الإرسال — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    except Exception as e:
        print(f"❌ خطأ في الإرسال: {e}")

# ─── التقرير الأسبوعي (كل أحد 6 مساءً) ───────────────
def weekly_analysis():
    print("🔄 جاري إعداد التقرير الأسبوعي...")
    news = get_breaking_news()
    fed  = get_fedwatch()
    fx   = get_fx_rates()

    user_message = f"""
أعد التقرير الأسبوعي الكامل الآن.

البيانات الحالية:

📰 آخر الأخبار الاقتصادية:
{news}

🏦 بيانات الفائدة الأمريكية:
{fed}

💱 أسعار العملات الحالية:
{fx}

بناءً على هذه البيانات، قدم:
1. مراجعة الأسبوع المنتهي
2. أجندة الأسبوع القادم
3. خارطة السيناريوهات
4. توصية الأسبوع
"""
    try:
        analysis = analyze_with_gemini(user_message)
        header = f"📊 *التقرير الأسبوعي — {datetime.now().strftime('%Y/%m/%d')}*\n\n"
        send_telegram(header + analysis)
    except Exception as e:
        send_telegram(f"❌ خطأ في التحليل الأسبوعي: {e}")

# ─── مراقبة الأخبار العاجلة (كل ساعة) ────────────────
def check_breaking_news():
    print("🔍 فحص الأخبار العاجلة...")
    news = get_breaking_news()

    keywords = [
        "emergency", "rate hike", "rate cut", "crisis",
        "recession", "war", "sanctions", "collapse",
        "surprise", "unexpected", "shock"
    ]

    is_urgent = any(kw in news.lower() for kw in keywords)

    if not is_urgent:
        print("لا توجد أخبار عاجلة.")
        return

    print("⚡ خبر عاجل — جاري التحليل...")
    fed = get_fedwatch()
    fx  = get_fx_rates()

    user_message = f"""
خبر عاجل يستدعي تحليلاً فورياً.

📰 الأخبار:
{news}

💱 أسعار العملات الحالية:
{fx}

🏦 الفائدة الأمريكية:
{fed}

قدم تحليل الأخبار العاجلة كاملاً وفق القسم 8 من إطار عملك.
"""
    try:
        analysis = analyze_with_gemini(user_message)
        header = f"⚡ *تنبيه عاجل — {datetime.now().strftime('%Y/%m/%d %H:%M')}*\n\n"
        send_telegram(header + analysis)
    except Exception as e:
        print(f"❌ خطأ في تحليل الأخبار العاجلة: {e}")

# ─── الجدولة ────────────────────────────────────────────
schedule.every().sunday.at("18:00").do(weekly_analysis)
schedule.every(1).hours.do(check_breaking_news)

# ─── تشغيل أولي ────────────────────────────────────────
print("🚀 النظام يعمل...")
send_telegram("✅ *نظام التحليل الأساسي بدأ العمل*\nد. كمال منصور جاهز للتحليل 🎓")

# ─── الحلقة الرئيسية ────────────────────────────────────
while True:
    schedule.run_pending()
    time.sleep(60)
