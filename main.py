import os
import asyncio
import zipfile
import threading
import logging
from flask import Flask
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# إعداد تسجيل الأخطاء لرؤيتها في Render Logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. سيرفر Flask (لإبقاء الخدمة تعمل) ---
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is running perfectly!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting Web Server on port {port}")
    web_app.run(host="0.0.0.0", port=port)

# --- 2. إعدادات البوت من متغيرات البيئة ---
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# التأكد من وجود المتغيرات
if not all([API_ID, API_HASH, BOT_TOKEN]):
    logger.error("Missing Environment Variables! Check API_ID, API_HASH, and BOT_TOKEN.")

app = Client(
    "compressor_bot",
    api_id=int(API_ID) if API_ID else 0,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True # لتوفير مساحة القرص
)

user_data = {}

# --- 3. دالة الضغط ---
def compress_file(input_file, output_zip, level):
    try:
        with zipfile.ZipFile(output_zip, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=level, allowZip64=True) as zipf:
            zipf.write(input_file, arcname=os.path.basename(input_file))
    except Exception as e:
        logger.error(f"Compression Error: {e}")
        raise e

# --- 4. معالجة الرسائل ---
@app.on_message(filters.document | filters.video | filters.audio)
async def handle_incoming_file(client, message):
    msg = await message.reply_text("📥 جاري تحميل الملف...")
    try:
        file_path = await message.download()
        file_name = os.path.basename(file_path)
        user_data[message.from_user.id] = {"path": file_path, "name": file_name}
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("مستوى 1", callback_data="level_1"), 
             InlineKeyboardButton("مستوى 6 (ينصح به)", callback_data="level_6")],
            [InlineKeyboardButton("مستوى 9 (أقصى ضغط)", callback_data="level_9")]
        ])
        await msg.edit_text(f"✅ تم التحميل: `{file_name}`\nاختر مستوى الضغط:", reply_markup=buttons)
    except Exception as e:
        await msg.edit_text(f"❌ فشل التحميل: {e}")

@app.on_callback_query(filters.regex("^level_"))
async def process_compression(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in user_data:
        await callback_query.answer("⚠️ انتهت الجلسة، أعد إرسال الملف.")
        return

    level = int(callback_query.data.split("_")[1])
    input_path = user_data[user_id]["path"]
    output_path = f"{input_path}.zip"

    await callback_query.message.edit_text(f"⚙️ جاري الضغط بمستوى {level}... قد يستغرق وقتاً.")

    try:
        # تنفيذ الضغط في خيط منفصل
        await asyncio.to_thread(compress_file, input_path, output_path, level)
        await callback_query.message.edit_text("📤 جاري الرفع...")
        
        await client.send_document(
            chat_id=callback_query.message.chat.id,
            document=output_path,
            caption=f"✅ اكتمل الضغط (مستوى {level})"
        )
    except Exception as e:
        await callback_query.message.edit_text(f"❌ فشل الضغط: {e}")
    finally:
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)
        user_data.pop(user_id, None)

# --- 5. التشغيل النهائي ---
async def start_services():
    # تشغيل سيرفر الويب في خيط منفصل
    threading.Thread(target=run_web, daemon=True).start()
    
    # تشغيل البوت
    logger.info("🚀 Starting Telegram Bot...")
    await app.start()
    await idle()
    await app.stop()

if __name__ == "__main__":
    try:
        asyncio.run(start_services())
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as e:
        logger.critical(f"Fatal Error: {e}")
