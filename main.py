import os
import asyncio
import zipfile
from flask import Flask
import threading
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# --- 1. سيرفر ويب وهمي لمنع Render من إيقاف البوت ---
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    # Render يستخدم المنفذ 8080 غالباً
    web_app.run(host="0.0.0.0", port=8080)

# --- 2. إعدادات البوت ---
API_ID = "YOUR_API_ID" 
API_HASH = "YOUR_API_HASH"
BOT_TOKEN = "YOUR_BOT_TOKEN"

app = Client("compressor_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# مخزن مؤقت لمسارات الملفات (بناءً على ID المستخدم)
user_data = {}

# --- 3. دالة الضغط (خارج مسار Async لضمان السرعة) ---
def compress_file(input_file, output_zip, level):
    """
    تستخدم write لتقليل استهلاك الرام (Streaming).
    تستخدم allowZip64 للملفات التي تتخطى 2GB.
    """
    with zipfile.ZipFile(output_zip, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=level, allowZip64=True) as zipf:
        zipf.write(input_file, arcname=os.path.basename(input_file))

# --- 4. معالجة الرسائل واستلام الملفات ---
@app.on_message(filters.document | filters.video | filters.audio)
async def handle_incoming_file(client, message):
    msg = await message.reply_text("📥 جاري تحميل الملف إلى السيرفر... (يرجى الانتظار)")
    
    try:
        # تحميل الملف
        file_path = await message.download()
        file_name = os.path.basename(file_path)
        
        user_data[message.from_user.id] = {"path": file_path, "name": file_name}
        
        # أزرار مستويات الضغط
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("ضغط سريع (مستوى 1)", callback_data="level_1")],
            [InlineKeyboardButton("ضغط متوازن (مستوى 6)", callback_data="level_6")],
            [InlineKeyboardButton("أقصى ضغط (مستوى 9)", callback_data="level_9")]
        ])
        
        await msg.edit_text(f"✅ تم تحميل: `{file_name}`\n\nاختر قوة الضغط (كلما زاد المستوى زاد الوقت المستغرق):", reply_markup=buttons)
        
    except Exception as e:
        await msg.edit_text(f"❌ حدث خطأ أثناء التحميل: {e}")

# --- 5. معالجة اختيار مستوى الضغط وبدء العملية ---
@app.on_callback_query(filters.regex("^level_"))
async def process_compression(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    if user_id not in user_data:
        await callback_query.answer("⚠️ الملف غير موجود، أرسله مرة أخرى.", show_alert=True)
        return

    level = int(callback_query.data.split("_")[1])
    input_path = user_data[user_id]["path"]
    output_path = f"{input_path}.zip"

    await callback_query.message.edit_text(f"⚙️ جاري الضغط بمستوى {level}...\nستصلك رسالة عند الانتهاء.")

    try:
        # تنفيذ الضغط في Thread منفصل لعدم تجميد البوت
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, compress_file, input_path, output_path, level)

        await callback_query.message.edit_text("📤 اكتمل الضغط! جاري رفع الملف إلى تيليجرام...")

        # إرسال الملف الناتج
        original_size = os.path.getsize(input_path) // (1024 * 1024)
        new_size = os.path.getsize(output_path) // (1024 * 1024)

        await client.send_document(
            chat_id=callback_query.message.chat.id,
            document=output_path,
            caption=(
                f"✅ **تمت العملية بنجاح**\n\n"
                f"🔹 الحجم الأصلي: {original_size} MB\n"
                f"🔸 الحجم بعد الضغط: {new_size} MB\n"
                f"📊 مستوى الضغط: {level}"
            )
        )
    except Exception as e:
        await callback_query.message.edit_text(f"❌ فشلت العملية: {e}")
    finally:
        # تنظيف الملفات فوراً لتوفير مساحة القرص على Render
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)
        if user_id in user_data: del user_data[user_id]

# --- 6. تشغيل البوت والسيرفر ---
if __name__ == "__main__":
    # تشغيل سيرفر Flask في الخلفية
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()
    
    print("🚀 البوت يعمل الآن...")
    app.run()
