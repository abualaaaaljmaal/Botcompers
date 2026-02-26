import os
import zipfile
import threading
from flask import Flask
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# 1. تشغيل سيرفر ويب بسيط لتجنب توقف الاستضافة
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "Bot is Alive!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# 2. إعدادات البوت (تأكد من إضافتها في Environment Variables في Render)
app = Client(
    "my_bot",
    api_id=int(os.getenv("API_ID")),
    api_hash=os.getenv("API_HASH"),
    bot_token=os.getenv("BOT_TOKEN")
)

user_files = {}

# 3. دالة ضغط الملفات
def compress_file(in_file, out_zip, level):
    with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED, compresslevel=level, allowZip64=True) as z:
        z.write(in_file, arcname=os.path.basename(in_file))

# 4. استقبال الملفات واختيار قوة الضغط
@app.on_message(filters.document | filters.video)
async def on_file(client, message):
    msg = await message.reply("📥 جاري التحميل...")
    path = await message.download()
    user_files[message.from_user.id] = path
    
    btns = InlineKeyboardMarkup([[
        InlineKeyboardButton("ضغط (6)", callback_data="c_6"),
        InlineKeyboardButton("أقصى ضغط (9)", callback_data="c_9")
    ]])
    await msg.edit("✅ تم التحميل، اختر مستوى الضغط:", reply_markup=btns)

@app.on_callback_query(filters.regex("^c_"))
async def on_compress(client, query):
    level = int(query.data.split("_")[1])
    in_path = user_files.get(query.from_user.id)
    if not in_path: return
    
    out_path = in_path + ".zip"
    await query.message.edit(f"⚙️ جاري الضغط بمستوى {level}...")
    
    import asyncio
    await asyncio.get_event_loop().run_in_executor(None, compress_file, in_path, out_path, level)
    
    await query.message.edit("📤 جاري الرفع...")
    await client.send_document(query.message.chat.id, out_path)
    
    os.remove(in_path)
    os.remove(out_path)

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    app.run()
