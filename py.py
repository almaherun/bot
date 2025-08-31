import pandas as pd
import telebot
import time
import os
from googlesearch import search  # لازم تعمل: pip install googlesearch-python

# --- إعداد البوت ---
BOT_TOKEN = "ضع_توكن_البوت_هنا"
CHANNEL_USERNAME = "@storage_data_me"
bot = telebot.TeleBot(BOT_TOKEN)

# --- المجالات ---
categories = {
    "مطاعم": "restaurants in Egypt",
    "عيادات": "clinics in Egypt",
    "صالات": "beauty salons in Egypt",
    "جيمات": "gyms in Egypt",
    "مراكز تعليم": "training centers in Egypt"
}

# --- القائمة النهائية ---
all_data = []

# --- البحث عن البيانات ---
def get_results(query, limit=10):
    results = []
    for url in search(query + " phone number", num_results=limit, lang="en"):
        results.append(url)
    return results

# --- تشغيل ---
for cat_name, search_q in categories.items():
    print(f"[+] جاري البحث عن: {cat_name} ...")
    data = get_results(search_q, limit=10)

    cat_data = []
    for d in data:
        cat_data.append({
            "المجال": cat_name,
            "المعلومة": d,
            "المصدر": "Google Search"
        })
        all_data.append({
            "المجال": cat_name,
            "المعلومة": d,
            "المصدر": "Google Search"
        })

    # --- إرسال رسالة فورية ---
    if cat_data:
        message = f"📌 نتائج {cat_name}:\n"
        for item in cat_data:
            message += f"- {item['المعلومة']}\n"
        bot.send_message(CHANNEL_USERNAME, message)
        time.sleep(2)

# --- حفظ الملف ---
df = pd.DataFrame(all_data)
csv_file = "unified_data.csv"
df.to_csv(csv_file, index=False, encoding="utf-8-sig")

# --- إرسال الملف في الآخر ---
if os.path.exists(csv_file):
    bot.send_document(CHANNEL_USERNAME, open(csv_file, "rb"))
    print(f"[✔] تم حفظ وإرسال الملف: {csv_file}")
else:
    print("[!] لم يتم إنشاء الملف.")
