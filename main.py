import os
import zipfile
import threading
import logging
from flask import Flask
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# إعداد التسجيل لرؤية ما يحدث داخل ريندر
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. سيرفر Flask (لإبقاء الخدمة تعمل وبدون مشاكل Port)
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "Bot is Running on Python 3.10!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# 2. إعدادات البوت من Environment Variables
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

app = Client(
    "compressor_bot",
    api_id=int(API_ID) if API_ID else 0,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

user_data = {}

# 3. دالة الضغط قطعة قطعة لتوفير الرام (500MB)
def compress_file(input_file, output_zip, level):
    with zipfile.ZipFile(output_zip, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=level, allowZip64=True) as zipf:
        zipf.write(input_file, arcname=os.path.basename(input_file))

# 4. استقبال الملفات
@app.on_message(filters.document | filters.video | filters.audio)
async def handle_file(client, message):
    msg = await message.reply_text("📥 جاري التحميل للسيرفر...")
    path = await message.download()
    user_data[message.from_user.id] = {"path": path, "name": os.path.basename(path)}
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("ضغط متوازن (6)", callback_data="lv_6")],
        [InlineKeyboardButton("أقصى ضغط (9)", callback_data="lv_9")]
    ])
    await msg.edit_text("✅ تم التحميل. اختر مستوى الضغط:", reply_markup=buttons)

# 5. معالجة الضغط والإرسال
@app.on_callback_query(filters.regex("^lv_"))
async def start_comp(client, callback):
    user_id = callback.from_user.id
    if user_id not in user_data: return
    
    level = int(callback.data.split("_")[1])
    in_p = user_data[user_id]["path"]
    out_p = f"{in_p}.zip"
    
    await callback.message.edit_text("⚙️ جاري الضغط... (قد يستغرق دقائق)")
    
    # تشغيل الضغط بدون تجميد البوت
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, compress_file, in_p, out_p, level)
    
    await callback.message.edit_text("📤 جاري الرفع لتيليجرام...")
    await client.send_document(callback.message.chat.id, document=out_p)
    
    # تنظيف المساحة فوراً
    if os.path.exists(in_p): os.remove(in_p)
    if os.path.exists(out_p): os.remove(out_p)
    user_data.pop(user_id, None)

if __name__ == "__main__":
    # تشغيل الويب في الخلفية
    threading.Thread(target=run_web, daemon=True).start()
    # تشغيل البوت
    logger.info("🚀 Starting Bot...")
    app.run()
