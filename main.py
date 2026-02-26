import os
import sys

# خدعة تقنية: منع Pyrogram من محاولة إنشاء Loop تلقائياً عند الاستدعاء
os.environ["PYROGRAM_COMPAT"] = "1" 

import asyncio
import zipfile
import threading
import logging
from flask import Flask

# استدعاء المكونات بعناية
try:
    from pyrogram import Client, filters, idle
    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
except RuntimeError:
    # إذا فشل الاستدعاء العادي، نستخدم الاستدعاء اليدوي للمكونات
    import pyrogram
    Client = pyrogram.Client
    filters = pyrogram.filters
    idle = pyrogram.idle

# إعداد التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. سيرفر Flask ---
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Server is Up!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# --- 2. إعدادات البوت ---
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# إنشاء الكائن بدون تشغيل أي شيء في الخلفية
app = Client(
    "compressor_bot",
    api_id=int(API_ID) if API_ID else 0,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

user_data = {}

# --- 3. دالة الضغط ---
def compress_file(input_file, output_zip, level):
    with zipfile.ZipFile(output_zip, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=level, allowZip64=True) as zipf:
        zipf.write(input_file, arcname=os.path.basename(input_file))

# --- 4. معالجة الرسائل (Async) ---
@app.on_message(filters.document | filters.video | filters.audio)
async def handle_incoming_file(client, message):
    msg = await message.reply_text("📥 جاري تحميل الملف...")
    file_path = await message.download()
    file_name = os.path.basename(file_path)
    user_data[message.from_user.id] = {"path": file_path, "name": file_name}
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("مستوى 6", callback_data="level_6"), InlineKeyboardButton("مستوى 9", callback_data="level_9")]
    ])
    await msg.edit_text(f"✅ تم تحميل: {file_name}\nاختر الضغط:", reply_markup=buttons)

@app.on_callback_query(filters.regex("^level_"))
async def process_compression(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    level = int(callback_query.data.split("_")[1])
    input_path = user_data[user_id]["path"]
    output_path = f"{input_path}.zip"

    await callback_query.message.edit_text(f"⚙️ جاري الضغط...")
    await asyncio.to_thread(compress_file, input_path, output_path, level)
    
    await client.send_document(callback_query.message.chat.id, document=output_path)
    
    if os.path.exists(input_path): os.remove(input_path)
    if os.path.exists(output_path): os.remove(output_path)

# --- 5. التشغيل المتوافق مع Python 3.14 ---
async def start_all():
    # تشغيل الويب
    threading.Thread(target=run_web, daemon=True).start()
    
    # تشغيل البوت يدوياً داخل الـ Loop
    await app.start()
    logger.info("🚀 Bot is running...")
    await idle()
    await app.stop()

if __name__ == "__main__":
    # إنشاء الـ Loop يدوياً وهو الحل الجذري
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(start_all())
    except KeyboardInterrupt:
        pass
