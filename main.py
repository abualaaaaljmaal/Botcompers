import os
import asyncio
import zipfile
from flask import Flask
import threading
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# --- 1. سيرفر ويب لمنع Render من إيقاف البوت ---
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is alive and running!"

def run_web():
    # Render يمرر المنفذ تلقائياً عبر متغير البيئة PORT
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# --- 2. إعدادات البوت ---
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

app = Client("compressor_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_data = {}

# --- 3. دالة الضغط ---
def compress_file(input_file, output_zip, level):
    with zipfile.ZipFile(output_zip, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=level, allowZip64=True) as zipf:
        zipf.write(input_file, arcname=os.path.basename(input_file))

# --- 4. التعامل مع الملفات ---
@app.on_message(filters.document | filters.video | filters.audio)
async def handle_incoming_file(client, message):
    msg = await message.reply_text("📥 جاري التحميل...")
    try:
        file_path = await message.download()
        file_name = os.path.basename(file_path)
        user_data[message.from_user.id] = {"path": file_path, "name": file_name}
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("مستوى 1", callback_data="level_1"), InlineKeyboardButton("مستوى 6", callback_data="level_6")],
            [InlineKeyboardButton("مستوى 9 (أقصى ضغط)", callback_data="level_9")]
        ])
        await msg.edit_text(f"✅ تم التحميل: `{file_name}`\nاختر مستوى الضغط:", reply_markup=buttons)
    except Exception as e:
        await msg.edit_text(f"❌ خطأ: {e}")

# --- 5. تنفيذ الضغط ---
@app.on_callback_query(filters.regex("^level_"))
async def process_compression(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in user_data:
        await callback_query.answer("الملف غير موجود!")
        return

    level = int(callback_query.data.split("_")[1])
    input_path = user_data[user_id]["path"]
    output_path = f"{input_path}.zip"

    await callback_query.message.edit_text(f"⚙️ جاري الضغط بمستوى {level}...")

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, compress_file, input_path, output_path, level)
        await callback_query.message.edit_text("📤 جاري الرفع...")
        
        await client.send_document(
            chat_id=callback_query.message.chat.id,
            document=output_path,
            caption=f"✅ اكتمل الضغط (مستوى {level})"
        )
    except Exception as e:
        await callback_query.message.edit_text(f"❌ فشل: {e}")
    finally:
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)
        user_data.pop(user_id, None)

# --- 6. التشغيل (إصلاح خطأ الـ Event Loop) ---
async def main():
    # تشغيل سيرفر الويب
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()
    
    # تشغيل البوت
    print("🚀 البوت يبدأ الآن...")
    await app.start()
    # الحفاظ على البوت يعمل
    from pyrogram import idle
    await idle()
    await app.stop()

if __name__ == "__main__":
    try:
        # هذه السطور تحل مشكلة "No current event loop" في Python 3.14
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
