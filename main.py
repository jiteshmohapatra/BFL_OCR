# import os
# import time
# import re
# import requests
# from io import BytesIO
# from telegram import Update, ReplyKeyboardMarkup
# from telegram.ext import (
#     ApplicationBuilder,
#     CommandHandler,
#     MessageHandler,
#     ContextTypes,
#     filters
# )
# from dotenv import load_dotenv

# # Load credentials from .env
# load_dotenv()
# BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# AZURE_ENDPOINT = os.getenv("AZURE_VISION_ENDPOINT")
# AZURE_KEY = os.getenv("AZURE_VISION_KEY")
# API_URL = AZURE_ENDPOINT + "vision/v3.2/read/analyze"

# # Keyboard for user interaction
# keyboard_markup = ReplyKeyboardMarkup(
#     [["Start"]],
#     resize_keyboard=True
# )

# # /start command
# async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text(
#         "👋 Welcome to *Bariflo OCR Bot*! Tap **Start** below to begin.",
#         reply_markup=keyboard_markup,
#         parse_mode="Markdown"
#     )

# # Respond to "Start" text tap
# async def handle_start_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text(
#         "📸 Now send any receipt image (PhonePe, GPay, Paytm, Amazon pay,  handwritten etc).\n\nI’ll extract and organize the info for you!",
#         parse_mode="Markdown"
#     )

# # Handle image upload and OCR
# async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     try:
#         photo = update.message.photo[-1]
#         file = await context.bot.get_file(photo.file_id)
#         file_bytes = await file.download_as_bytearray()
#         image_stream = BytesIO(file_bytes)

#         text = extract_text_from_image(image_stream)
#         if not text:
#             await update.message.reply_text("❌ No text found in the image.")
#             return

#         result = organize_text(text)
#         await update.message.reply_text(result, parse_mode='Markdown')

#     except Exception as e:
#         await update.message.reply_text("⚠️ Something went wrong.")
#         print("Error:", e)

# # Azure OCR logic
# def extract_text_from_image(image_stream):
#     headers = {
#         'Ocp-Apim-Subscription-Key': AZURE_KEY,
#         'Content-Type': 'application/octet-stream'
#     }

#     response = requests.post(API_URL, headers=headers, data=image_stream)

#     if response.status_code != 202:
#         print("Azure OCR error:", response.text)
#         return None

#     operation_url = response.headers['Operation-Location']

#     while True:
#         result = requests.get(
#             operation_url,
#             headers={'Ocp-Apim-Subscription-Key': AZURE_KEY}
#         ).json()

#         if result.get("status") == "succeeded":
#             break
#         elif result.get("status") == "failed":
#             return None
#         time.sleep(1)

#     lines = []
#     for read_result in result['analyzeResult']['readResults']:
#         for line in read_result['lines']:
#             lines.append(line['text'])

#     return "\n".join(lines)

# # Organize extracted text
# def organize_text(text):
#     lines = text.splitlines()
#     header = ""
#     fields = {}
#     extras = []

#     for line in lines:
#         line = line.strip()
#         if ":" in line:
#             k, v = line.split(":", 1)
#             fields[k.strip().title()] = v.strip()
#         elif re.search(r'₹\s?\d+(\.\d+)?', line):
#             fields["Amount"] = line
#         elif re.search(r'\d{2}[-/]\d{2}[-/]\d{4}', line):
#             fields["Date"] = line
#         elif re.search(r'(phonepe|paytm|gpay|upi|google pay)', line.lower()):
#             fields["Vendor"] = line
#         elif not header:
#             header = line
#         else:
#             extras.append(line)

#     msg = ""
#     if header:
#         msg += f"*🧾 {header}*\n\n"
#     if fields:
#         msg += "*🔑 Details:*\n"
#         for k, v in fields.items():
#             msg += f"• {k}: {v}\n"
#     if extras:
#         msg += "\n*📝 Other Info:*\n"
#         for e in extras:
#             msg += f"- {e}\n"

#     return msg.strip()

# # Run the bot
# if __name__ == "__main__":
#     app = ApplicationBuilder().token(BOT_TOKEN).build()

#     app.add_handler(CommandHandler("start", start))
#     app.add_handler(MessageHandler(filters.TEXT & filters.Regex("(?i)^start$"), handle_start_text))
#     app.add_handler(MessageHandler(filters.PHOTO, handle_image))

#     print("🤖 Bariflo OCR Bot is running...")
#     app.run_polling()


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

# Configure logging
logging.basicConfig(level=logging.INFO)

# In-memory image storage
user_images = {}

# /start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📸 Now send any receipt image (PhonePe, GPay, Paytm, Amazon Pay, handwritten etc).\n\n"
        "I’ll extract and organize the info for you!"
    )

# Image handler
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        file_bytes = await file.download_as_bytearray()
        user_id = update.message.from_user.id
        user_images[user_id] = file_bytes

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🟣 PhonePe", callback_data="PhonePe"),
             InlineKeyboardButton("🔵 Google Pay", callback_data="GooglePay")],
            [InlineKeyboardButton("🟡 Amazon Pay", callback_data="AmazonPay"),
             InlineKeyboardButton("✍️ Handwritten", callback_data="Handwritten")],
            [InlineKeyboardButton("📦 Other", callback_data="Other")]
        ])

        await update.message.reply_text(
            "🧾 Please choose the type of receipt:",
            reply_markup=keyboard
        )

    except Exception as e:
        logging.error(f"Error handling image: {e}")
        await update.message.reply_text("⚠️ Something went wrong while processing the image.")

# Receipt type button handler
async def handle_receipt_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        receipt_type = query.data
        user_id = query.from_user.id

        if user_id not in user_images:
            await query.edit_message_text("❌ No image found. Please upload the receipt again.")
            return

        image_bytes = user_images.pop(user_id)
        image_stream = BytesIO(image_bytes)

        text = extract_text_from_image(image_stream)
        if not text:
            await query.edit_message_text("❌ No text detected in the image.")
            return

        formatted = organize_text(text, receipt_type)
        await query.edit_message_text(f"📂 You selected: *{receipt_type}*\n\n{formatted}", parse_mode='Markdown')

    except Exception as e:
        logging.error(f"Error in callback: {e}")
        await query.edit_message_text("⚠️ Failed to process the receipt type.")

# Azure OCR integration
def extract_text_from_image(image_stream):
    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_KEY,
        'Content-Type': 'application/octet-stream'
    }

    response = requests.post(API_URL, headers=headers, data=image_stream.getvalue())
    if response.status_code != 202:
        logging.error(f"Azure OCR failed: {response.text}")
        return None

    operation_url = response.headers['Operation-Location']
    while True:
        result = requests.get(operation_url, headers={'Ocp-Apim-Subscription-Key': AZURE_KEY}).json()
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

# Format extracted text
def organize_text(text, category):
    lines = text.splitlines()
    fields = {}
    header = ""
    others = []

    for line in lines:
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip().title()] = value.strip()
        elif re.search(r'₹\s?\d+(\.\d+)?', line):
            fields["Amount"] = line
        elif re.search(r'\d{2}[-/]\d{2}[-/]\d{4}', line):
            fields["Date"] = line
        elif len(line.strip()) > 3 and not header:
            header = line.strip()
        else:
            others.append(line.strip())

    result = f"🧾 *{header or 'Receipt'}*\n\n"
    result += f"🗂️ *Category:* `{category}`\n\n"

    if fields:
        result += "🔍 *Detected Fields:*\n"
        for k, v in fields.items():
            result += f"• {k}: {v}\n"
        result += "\n"

    if others:
        result += "📋 *Other Info:*\n"
        for line in others:
            result += f"- {line}\n"

    return result.strip()

# App entry point
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))
    app.add_handler(CallbackQueryHandler(handle_receipt_type))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start))  # Handles text fallback
    print("🤖 Bariflo OCR bot is running...")
    app.run_polling()
