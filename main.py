import os
import time
import re
import logging
import requests
from io import BytesIO
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AZURE_ENDPOINT = os.getenv("AZURE_VISION_ENDPOINT")
AZURE_KEY = os.getenv("AZURE_VISION_KEY")
API_URL = AZURE_ENDPOINT + 'vision/v3.2/read/analyze'

# Setup logging
logging.basicConfig(level=logging.INFO)

# In-memory storage
user_images = {}
user_state = {}

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("\U0001F4F8 Send a receipt image (UPI, handwritten, printed, brochure)")

# Handle image upload
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        file_bytes = await file.download_as_bytearray()
        user_id = update.message.from_user.id
        user_images[user_id] = file_bytes
        user_state[user_id] = {"stage": "main_category"}

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("\U0001F4B8 UPI", callback_data="upi")],
            [InlineKeyboardButton("\u270D\ufe0f Handwritten Invoice", callback_data="handwritten")],
            [InlineKeyboardButton("\U0001F9FE Printed Invoice", callback_data="printed")],
            [InlineKeyboardButton("\U0001F4C4 Brochure", callback_data="brochure")]
        ])
        await update.message.reply_text("\U0001F518 Choose the receipt type:", reply_markup=keyboard)

    except Exception as e:
        logging.error(f"Image error: {e}")
        await update.message.reply_text("❌ Failed to process image.")

# OCR using Azure
def extract_text_from_image(image_stream):
    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_KEY,
        'Content-Type': 'application/octet-stream'
    }
    response = requests.post(API_URL, headers=headers, data=image_stream.getvalue())
    if response.status_code != 202:
        return None
    operation_url = response.headers['Operation-Location']
    while True:
        result = requests.get(operation_url, headers=headers).json()
        if result.get('status') == 'succeeded':
            break
        elif result.get('status') == 'failed':
            return None
        time.sleep(1)
    lines = []
    for read_result in result['analyzeResult']['readResults']:
        for line in read_result['lines']:
            lines.append(line['text'])
    return "\n".join(lines)

# Field extraction by category
def extract_limited_fields(text, category):
    lines = text.splitlines()
    fields = {
        "Amount": "",
        "Date & Time": "",
        "Transaction ID": "",
        "Person Name": "",
        "UPI ID": ""  # Only for Paytm
    }

    for line in lines:
        if not fields["Amount"] and re.search(r'₹\s?\d+[\d,.]*', line):
            fields["Amount"] = line.strip()
        elif not fields["Date & Time"] and re.search(r'\d{1,2}[:.]\d{2}.*\d{2,4}', line):
            fields["Date & Time"] = line.strip()
        elif not fields["Transaction ID"] and re.match(r'^[A-Z0-9]{12,}$', line):
            fields["Transaction ID"] = line.strip()
        elif not fields["Person Name"] and re.search(r'(To|Paid to|To:|Paid to:)', line, re.IGNORECASE):
            fields["Person Name"] = re.sub(r'(To|Paid to|To:|Paid to:)\s*', '', line, flags=re.IGNORECASE).strip()
        elif category == "Paytm" and not fields["UPI ID"] and "@" in line:
            upi_match = re.search(r"\b[\w.-]+@[\w.-]+\b", line)
            if upi_match:
                fields["UPI ID"] = upi_match.group(0).strip()

    result = f"\U0001F50D *Extracted Details for {category}:*\n"
    for key, value in fields.items():
        if category != "Paytm" and key == "UPI ID":
            continue
        result += f"• {key}: {value or 'Not Found'}\n"
    return result.strip()

# Callback handler for buttons
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if user_id not in user_images:
        await query.edit_message_text("❌ Please send a receipt image first.")
        return

    state = user_state.get(user_id, {})
    stage = state.get("stage")

    if stage == "main_category":
        if data == "upi":
            user_state[user_id]["stage"] = "upi_subtype"
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("\U0001F7E3 PhonePe", callback_data="PhonePe"),
                 InlineKeyboardButton("\U0001F537 Paytm", callback_data="Paytm"),
                 InlineKeyboardButton("\U0001F535 GooglePay", callback_data="GooglePay")]
            ])
            await query.edit_message_text("\U0001F4B3 Choose UPI type:", reply_markup=keyboard)
        else:
            user_state[user_id]["stage"] = "final"
            await process_receipt(query, user_id, category=data)

    elif stage == "upi_subtype":
        user_state[user_id]["stage"] = "final"
        await process_receipt(query, user_id, category=data)

# Final process step
async def process_receipt(query, user_id, category):
    try:
        image_stream = BytesIO(user_images.pop(user_id))
        text = extract_text_from_image(image_stream)

        if not text or len(text.strip()) < 10:
            await query.edit_message_text("\U0001F6AB *Image is unclear or unreadable.* Please upload a better receipt.", parse_mode='Markdown')
            return

        formatted = extract_limited_fields(text, category) if category in ["PhonePe", "Paytm", "GooglePay"] else f"\U0001F4C4 *Raw Text:*\n{text}"

        await query.edit_message_text(f"\u2705 *Category:* `{category}`\n\n{formatted}", parse_mode='Markdown')

    except Exception as e:
        logging.error(f"Processing error: {e}")
        await query.edit_message_text("⚠️ Failed to process receipt.")

# Entry point
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start))
    print("✅ Bot is running...")
    app.run_polling()
