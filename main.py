import os
import lzma
import threading
import logging
import time
from flask import Flask
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# إعداد التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

web_app = Flask(__name__)
@web_app.route('/')
def home(): return "Progress Bot is Active!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# إعدادات البوت
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

app = Client("progress_bot", api_id=int(API_ID) if API_ID else 0, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_data = {}

# --- دالة تحديث شريط التقدم في تيليجرام ---
async def progress_bar(current, total, message, text):
    try:
        percent = current * 100 / total
        # إنشاء شكل الشريط [██░░]
        completed = int(percent / 10)
        bar = "█" * completed + "░" * (10 - completed)
        
        # التحديث فقط كل 10% أو عند الانتهاء لتجنب حظر تيليجرام (Flood)
        if int(percent) % 10 == 0 or current == total:
            await message.edit_text(f"{text}\n\n📊 النسبة: {percent:.1f}%\n[{bar}]")
    except Exception:
        pass

# --- دالة الضغط الفائق مع مراقبة التقدم ---
def super_compress_with_progress(input_file, output_file, preset, user_id, client, message):
    total_size = os.path.getsize(input_file)
    current_size = 0
    last_update_time = 0
    
    with lzma.open(output_file, "wb", preset=preset) as f_out:
        with open(input_file, "rb") as f_in:
            while True:
                chunk = f_in.read(1024 * 1024) # 1MB
                if not chunk: break
                f_out.write(chunk)
                current_size += len(chunk)
                
                # تحديث العداد كل ثانيتين لتجنب تجميد العملية
                if time.time() - last_update_time > 2:
                    percent = (current_size / total_size) * 100
                    bar = "█" * int(percent / 10) + "░" * (10 - int(percent / 10))
                    try:
                        client.loop.create_task(message.edit_text(
                            f"⚙️ جاري الضغط الفائق...\n\n📊 التقدم: {percent:.1f}%\n[{bar}]"
                        ))
                    except: pass
                    last_update_time = time.time()

@app.on_message(filters.document | filters.video)
async def handle_file(client, message):
    file = message.document or message.video
    MAX_SIZE = 500 * 1024 * 1024
    
    if file.file_size > MAX_SIZE:
        await message.reply_text("❌ الملف كبير جداً! الحد الأقصى 500 ميجابايت.")
        return

    msg = await message.reply_text("📥 جاري التحميل...")
    # عداد التحميل المدمج في Pyrogram
    path = await message.download(progress=progress_bar, progress_args=(msg, "📥 جاري تحميل الملف من تيليجرام..."))
    
    user_data[message.from_user.id] = {"path": path, "name": os.path.basename(path)}
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("ضغط 30%", callback_data="p_1"), InlineKeyboardButton("ضغط 50%", callback_data="p_5")],
        [InlineKeyboardButton("ضغط فائق 80%", callback_data="p_9")]
    ])
    await msg.edit_text(f"✅ تم التحميل: {os.path.basename(path)}\nاختر القوة:", reply_markup=buttons)

@app.on_callback_query(filters.regex("^p_"))
async def start_compression(client, callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in user_data: return
    
    preset = int(callback.data.split("_")[1])
    in_p = user_data[user_id]["path"]
    out_p = f"{in_p}.xz"
    
    msg = callback.message
    await msg.edit_text("⚙️ جاري بدء عملية الضغط الفائق...")

    try:
        # تشغيل الضغط في Thread مع العداد
        await asyncio.to_thread(super_compress_with_progress, in_p, out_p, preset, user_id, client, msg)
        
        await msg.edit_text("📤 جاري الرفع الآن...")
        await client.send_document(
            chat_id=callback.message.chat.id, 
            document=out_p,
            progress=progress_bar,
            progress_args=(msg, "📤 جاري رفع الملف المضغوط...")
        )
    except Exception as e:
        await msg.edit_text(f"❌ خطأ: {e}")
    finally:
        if os.path.exists(in_p): os.remove(in_p)
        if os.path.exists(out_p): os.remove(out_p)
        user_data.pop(user_id, None)

if __name__ == "__main__":
    import asyncio
    threading.Thread(target=run_web, daemon=True).start()
    app.run()
