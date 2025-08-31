import requests
from bs4 import BeautifulSoup
import pandas as pd
import telebot
import time
import os

# إعدادات التليجرام
BOT_TOKEN = "توكن_البوت_بتاعك"
CHANNEL_USERNAME = "@storage_data_me"

bot = telebot.TeleBot(BOT_TOKEN)

# المجالات الافتراضية
categories = {
    "مطاعم": "مطاعم في مصر رقم تليفون",
    "عيادات": "عيادات في مصر رقم تليفون",
    "صالات": "كوافير في مصر رقم تليفون",
    "جيمات": "جيم في مصر رقم تليفون",
    "مراكز تعليم": "مراكز تدريب في مصر رقم تليفون"
}

# دالة بحث في DuckDuckGo
def ddg_search(query, max_results=15):
    url = "https://duckduckgo.com/html/"
    params = {"q": query}
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.post(url, data=params, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")

    results = []
    for link in soup.find_all("a", class_="result__a", limit=max_results):
        text = link.get_text()
        if any(c.isdigit() for c in text):
            results.append(text)
    return results

# القائمة النهائية
all_data = []

# حلقة على كل مجال
for cat_name, search_q in categories.items():
    print(f"[+] جاري البحث عن: {cat_name} ...")
    data = ddg_search(search_q, max_results=20)

    cat_data = []
    for d in data:
        if any(c.isdigit() for c in d):
            cat_data.append({"المجال": cat_name, "المعلومة": d, "المصدر": "DuckDuckGo"})
            all_data.append({"المجال": cat_name, "المعلومة": d, "المصدر": "DuckDuckGo"})

    if cat_data:
        message = f"📌 نتائج {cat_name}:\n"
        for item in cat_data:
            message += f"- {item['المعلومة']}\n"
        bot.send_message(CHANNEL_USERNAME, message)
        time.sleep(2)

# حفظ في CSV
df = pd.DataFrame(all_data)
csv_file = "unified_data.csv"
df.to_csv(csv_file, index=False, encoding="utf-8-sig")

# إرسال الملف على التليجرام
if os.path.exists(csv_file):
    bot.send_document(CHANNEL_USERNAME, open(csv_file, "rb"))
    print(f"[✔] تم حفظ وإرسال الملف: {csv_file}")
else:
    print("[!] لم يتم إنشاء الملف.")
