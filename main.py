import os
import time
import re
import requests
from io import BytesIO
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from dotenv import load_dotenv

# Load credentials from .env
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AZURE_ENDPOINT = os.getenv("AZURE_VISION_ENDPOINT")
AZURE_KEY = os.getenv("AZURE_VISION_KEY")
API_URL = AZURE_ENDPOINT + "vision/v3.2/read/analyze"

# Keyboard for user interaction
keyboard_markup = ReplyKeyboardMarkup(
    [["Start"]],
    resize_keyboard=True
)

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to *Bariflo OCR Bot*! Tap **Start** below to begin.",
        reply_markup=keyboard_markup,
        parse_mode="Markdown"
    )

# Respond to "Start" text tap
async def handle_start_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📸 Now send any receipt image (PhonePe, GPay, Paytm, Amazon pay,  handwritten etc).\n\nI’ll extract and organize the info for you!",
        parse_mode="Markdown"
    )

# Handle image upload and OCR
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        file_bytes = await file.download_as_bytearray()
        image_stream = BytesIO(file_bytes)

        text = extract_text_from_image(image_stream)
        if not text:
            await update.message.reply_text("❌ No text found in the image.")
            return

        result = organize_text(text)
        await update.message.reply_text(result, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text("⚠️ Something went wrong.")
        print("Error:", e)

# Azure OCR logic
def extract_text_from_image(image_stream):
    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_KEY,
        'Content-Type': 'application/octet-stream'
    }

    response = requests.post(API_URL, headers=headers, data=image_stream)

    if response.status_code != 202:
        print("Azure OCR error:", response.text)
        return None

    operation_url = response.headers['Operation-Location']

    while True:
        result = requests.get(
            operation_url,
            headers={'Ocp-Apim-Subscription-Key': AZURE_KEY}
        ).json()

        if result.get("status") == "succeeded":
            break
        elif result.get("status") == "failed":
            return None
        time.sleep(1)

    lines = []
    for read_result in result['analyzeResult']['readResults']:
        for line in read_result['lines']:
            lines.append(line['text'])

    return "\n".join(lines)

# Organize extracted text
def organize_text(text):
    lines = text.splitlines()
    header = ""
    fields = {}
    extras = []

    for line in lines:
        line = line.strip()
        if ":" in line:
            k, v = line.split(":", 1)
            fields[k.strip().title()] = v.strip()
        elif re.search(r'₹\s?\d+(\.\d+)?', line):
            fields["Amount"] = line
        elif re.search(r'\d{2}[-/]\d{2}[-/]\d{4}', line):
            fields["Date"] = line
        elif re.search(r'(phonepe|paytm|gpay|upi|google pay)', line.lower()):
            fields["Vendor"] = line
        elif not header:
            header = line
        else:
            extras.append(line)

    msg = ""
    if header:
        msg += f"*🧾 {header}*\n\n"
    if fields:
        msg += "*🔑 Details:*\n"
        for k, v in fields.items():
            msg += f"• {k}: {v}\n"
    if extras:
        msg += "\n*📝 Other Info:*\n"
        for e in extras:
            msg += f"- {e}\n"

    return msg.strip()

# Run the bot
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("(?i)^start$"), handle_start_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))

    print("🤖 Bariflo OCR Bot is running...")
    app.run_polling()
