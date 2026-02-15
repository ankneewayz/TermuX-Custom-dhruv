import os
import re
import asyncio
import requests
from flask import Flask, request
from Crypto.Cipher import AES
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# --- Configuration ---
TOKEN = '8183534977:AAGYLeHEUExoQTY3YNJ9yRp-NuVCSDOgXug'
VIDEO_FILE_ID = "BAACAgUAAxkBAAICYWmSDu9PxdumNL2jt_HuEbhU9ej8AAJUIAACnY2RVB4XvSbfaDVBOgQ"

app = Flask(__name__)

# Initialize PTB Application
ptb_instance = Application.builder().token(TOKEN).build()

MODELS = [
    "DeepSeek-V1", "DeepSeek-V2", "DeepSeek-V2.5", "DeepSeek-V3", "DeepSeek-V3-0324",
    "DeepSeek-V3.1", "DeepSeek-V3.2", "DeepSeek-R1", "DeepSeek-R1-0528", "DeepSeek-R1-Distill",
    "DeepSeek-Prover-V1", "DeepSeek-Prover-V1.5", "DeepSeek-Prover-V2", "DeepSeek-VL",
    "DeepSeek-Coder", "DeepSeek-Coder-V2", "DeepSeek-Coder-6.7B-base", "DeepSeek-Coder-6.7B-instruct"
]

class DeepSeekSession:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})
        self.model = "DeepSeek-R1"
        self.ready = False
        self.history = []

    def bypass_challenge(self):
        try:
            r = self.session.get('https://asmodeus.free.nf/', timeout=10)
            nums = re.findall(r'toNumbers\("([a-f0-9]+)"\)', r.text)
            if len(nums) >= 3:
                key, iv, data = [bytes.fromhex(n) for n in nums[:3]]
                test_cookie = AES.new(key, AES.MODE_CBC, iv).decrypt(data).hex()
                self.session.cookies.set('__test', test_cookie, domain='asmodeus.free.nf')
                self.session.get('https://asmodeus.free.nf/index.php?i=1')
                self.ready = True
                return True
        except: return False

    def ask_ai(self, question):
        if not self.ready: self.bypass_challenge()
        prompt = "".join([f"U: {h['user']}\nA: {h['bot']}\n" for h in self.history[-3:]]) + f"U: {question}\nA: "
        try:
            r = self.session.post('https://asmodeus.free.nf/deepseek.php', params={'i': '1'}, data={'model': self.model, 'question': prompt}, timeout=25)
            reply = re.search(r'class="response-content">(.*?)</div>', r.text, re.DOTALL)
            if reply:
                text = re.sub(r'<[^>]*>', '', reply.group(1).replace('<br>', '\n')).strip()
                self.history.append({"user": question, "bot": text})
                return text
            return "⚠️ Server Busy."
        except: return "❌ Timeout."

user_sessions = {}

# --- Bot Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_sessions[uid] = DeepSeekSession()
    kb = [[InlineKeyboardButton(MODELS[j], callback_data=f"set_{MODELS[j]}") for j in range(i, min(i+2, len(MODELS)))] for i in range(0, len(MODELS), 2)]
    await update.message.reply_video(video=VIDEO_FILE_ID, caption="🤖 **DeepSeek Bot OWNER:@ankneewayz**\nSelect model:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    model = query.data.replace("set_", "")
    if uid not in user_sessions: user_sessions[uid] = DeepSeekSession()
    user_sessions[uid].model = model
    user_sessions[uid].bypass_challenge()
    await query.edit_message_caption(caption=f"✅ Model: **{model}**\nSend a message!", parse_mode='Markdown')

async def msg_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in user_sessions: user_sessions[uid] = DeepSeekSession()
    
    wait = await update.message.reply_text("⏳ Thinking...")
    # Use to_thread to prevent blocking the async loop
    ans = await asyncio.to_thread(user_sessions[uid].ask_ai, update.message.text)
    
    await context.bot.edit_message_text(chat_id=uid, message_id=wait.message_id, text=ans)

ptb_instance.add_handler(CommandHandler("start", start))
ptb_instance.add_handler(CallbackQueryHandler(cb_handler))
ptb_instance.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_handler))

# --- Flask Routes ---
@app.route('/', methods=['POST', 'GET'])
async def webhook_handler():
    if request.method == "POST":
        try:
            update = Update.de_json(request.get_json(force=True), ptb_instance.bot)
            async with ptb_instance: # This ensures the bot is started and stopped correctly
                await ptb_instance.process_update(update)
            return "OK", 200
        except Exception as e:
            print(f"Error: {e}")
            return "Error", 500
    return "DeepSeek Bot is Active!", 200

