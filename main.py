import os
import asyncio
import zipfile
import threading
import logging
from flask import Flask
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# إعداد التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. سيرفر Flask ---
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is running on Python 3.10!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# --- 2. إعدادات البوت ---
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

# --- 3. دالة الضغط ---
def compress_file(input_file, output_zip, level):
    with zipfile.ZipFile(output_zip, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=level, allowZip64=True) as zipf:
        zipf.write(input_file, arcname=os.path.basename(input_file))

# --- 4. معالجة الرسائل ---
@app.on_message(filters.document | filters.video | filters.audio)
async def handle_incoming_file(client, message):
    msg = await message.reply_text("📥 جاري تحميل الملف...")
    file_path = await message.download()
    file_name = os.path.basename(file_path)
    user_data[message.from_user.id] = {"path": file_path, "name": file_name}
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("ضغط متوازن (6)", callback_data="level_6")],
        [InlineKeyboardButton("أقصى ضغط (9)", callback_data="level_9")]
    ])
    await msg.edit_text(f"✅ تم تحميل: {file_name}\nاختر مستوى الضغط:", reply_markup=buttons)

@app.on_callback_query(filters.regex("^level_"))
async def process_compression(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in user_data: return

    level = int(callback_query.data.split("_")[1])
    input_path = user_data[user_id]["path"]
    output_path = f"{input_path}.zip"

    await callback_query.message.edit_text(f"⚙️ جاري الضغط بمستوى {level}...")
    
    # تنفيذ الضغط
    await asyncio.get_event_loop().run_in_executor(None, compress_file, input_path, output_path, level)
    
    await callback_query.message.edit_text("📤 جاري الرفع...")
    await client.send_document(callback_query.message.chat.id, document=output_path)
    
    # تنظيف
    os.remove(input_path)
    os.remove(output_path)
    user_data.pop(user_id, None)

# --- 5. التشغيل ---
if __name__ == "__main__":
    # تشغيل الويب
    threading.Thread(target=run_web, daemon=True).start()
    
    # تشغيل البوت
    logger.info("🚀 Starting Bot...")
    app.run()
