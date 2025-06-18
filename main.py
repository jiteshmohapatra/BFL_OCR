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

# Load env variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AZURE_ENDPOINT = os.getenv("AZURE_VISION_ENDPOINT")
AZURE_KEY = os.getenv("AZURE_VISION_KEY")
API_URL = AZURE_ENDPOINT + 'vision/v3.2/read/analyze'

# Logging
logging.basicConfig(level=logging.INFO)

# Image storage
user_images = {}

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hello! Send me any receipt image (PhonePe, GPay, Paytm, etc). I’ll extract and format the details for you."
    )

# Handle receipt image
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
            [InlineKeyboardButton("🔷 Paytm", callback_data="Paytm"),
             InlineKeyboardButton("📦 Other", callback_data="Other")]
        ])

        await update.message.reply_text(
            "🧾 Please choose the type of receipt:",
            reply_markup=keyboard
        )

    except Exception as e:
        logging.error(f"Image Upload Error: {e}")
        await update.message.reply_text("⚠️ Error processing image. Please try again.")

# Azure OCR
def extract_text_from_image(image_stream):
    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_KEY,
        'Content-Type': 'application/octet-stream'
    }
    response = requests.post(API_URL, headers=headers, data=image_stream.getvalue())
    if response.status_code != 202:
        logging.error(f"Azure error: {response.text}")
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

# Format text
def organize_text(text, category):
    lines = text.splitlines()
    if not lines or all(len(l.strip()) < 3 for l in lines):
        return None  # poor image quality

    fields = {}
    others = []
    result = ""

    if category == "PhonePe":
        header = "PhonePe Receipt Summary"
        for line in lines:
            if "₹" in line:
                fields["Amount"] = line.strip()
            elif "Transaction ID" in line:
                fields["Transaction ID"] = line.split(":")[-1].strip()
            elif "UTR" in line:
                fields["UTR"] = line.split(":")[-1].strip()
            elif re.match(r"(?i)^message[:\- ]", line.strip()):
                fields["Message"] = line.split(":", 1)[-1].strip()
            elif "Debited" in line:
                fields["Debited From"] = line.replace("Debited from", "").strip()
            elif re.search(r"\d{2}:\d{2}.*\d{2,4}", line):
                fields["Date & Time"] = line.strip()
            else:
                others.append(line.strip())

    elif category == "Paytm":
        header = "Paytm Receipt Summary"
        amount = date_time = transaction_id = upi_ref = to_account = upi_id = ""
        for line in lines:
            if "₹" in line:
                amount = line.strip()
            elif re.search(r"\d{2}[:]\d{2}.*\d{2,4}", line):
                date_time = line.strip()
            elif re.match(r"^[A-Z0-9]{16,}$", line.strip()):
                transaction_id = line.strip()
            elif "Ref No" in line or "UPI Ref" in line:
                upi_ref = line.split(":")[-1].strip()
            elif "To:" in line:
                to_account = line.replace("To:", "").strip()
            elif "@" in line:
                upi_id = line.strip()
            else:
                others.append(line.strip())
        fields = {
            "Amount Paid": amount,
            "To Account": to_account,
            "UPI ID": upi_id,
            "Transaction ID": transaction_id,
            "UPI Ref No": upi_ref,
            "Date & Time": date_time
        }

    else:
        header = f"{category} Receipt Summary"
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                fields[key.strip().title()] = value.strip()
            elif re.search(r'₹\s?\d+(\.\d+)?', line):
                fields["Amount"] = line.strip()
            elif re.search(r'\d{2}[-/]\d{2}[-/]\d{4}', line):
                fields["Date"] = line.strip()
            else:
                others.append(line.strip())

    result += f"🧾 *{header}*\n\n"
    result += f"🗂️ *Category:* `{category}`\n\n"
    if fields:
        result += "🔍 *Extracted Details:*\n"
        for k, v in fields.items():
            if v:
                result += f"• {k}: {v}\n"
    if others:
        result += "\n📋 *Other Info:*\n"
        for line in others:
            if len(line.strip()) > 2:
                result += f"- {line}\n"

    return result.strip()

# Receipt type handler
async def handle_receipt_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        receipt_type = query.data
        user_id = query.from_user.id

        if user_id not in user_images:
            await query.edit_message_text("❌ No image found. Please send again.")
            return

        image_bytes = user_images.pop(user_id)
        image_stream = BytesIO(image_bytes)
        text = extract_text_from_image(image_stream)

        if not text:
            await query.edit_message_text(
                "❗ *Unable to read the text clearly from the image.*\n"
                "📸 Please send a properly captured, clear image of the receipt for best results.",
                parse_mode='Markdown'
            )
            return

        formatted = organize_text(text, receipt_type)
        if not formatted:
            await query.edit_message_text(
                "⚠️ *The image seems blurry or unclear.*\n"
                "📷 Kindly upload a clear, readable image of the receipt to extract details.",
                parse_mode='Markdown'
            )
            return

        await query.edit_message_text(f"{formatted}", parse_mode='Markdown')

    except Exception as e:
        logging.error(f"ReceiptType Error: {e}")
        await query.edit_message_text("❌ Error occurred. Please retry.")

# Main
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))
    app.add_handler(CallbackQueryHandler(handle_receipt_type))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start))  # fallback
    print("✅ Telegram OCR bot is live...")
    app.run_polling()
