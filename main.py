import os
import requests
import io
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, ApplicationBuilder, ContextTypes,
    CommandHandler, CallbackQueryHandler,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN") or '8262341478:AAHi31NDnJKOrzTQaaSBGWorxVguSt8Bn0c'
ITEMS_JSON_URL = "https://ullas65.github.io/UptoOB50Data/OB50Items.json"
YOUR_USER_ID = 933925222  # Only you in private chat

items_data = []
BATCH_SIZE = 10

def load_items_data():
    global items_data
    resp = requests.get(ITEMS_JSON_URL)
    if resp.status_code == 200:
        items_data = resp.json()
    else:
        items_data = []

def is_allowed(update: Update):
    chat = update.effective_chat
    # Allow all channels
    if chat.type == "channel":
        return True
    # Allow all groups/supergroups
    if chat.type in ("group", "supergroup"):
        return True
    # Allow ONLY your private chat
    if chat.type == "private" and chat.id == YOUR_USER_ID:
        return True
    return False

def find_items(query):
    query_str = str(query).lower()
    matched = []
    for item in items_data:
        id_val = str(item.get("Id", "")) or ""
        name_val = item.get("name") or ""
        icon_val = item.get("Icon") or ""
        if (query_str in id_val.lower()) or (query_str in name_val.lower()) or (query_str in icon_val.lower()):
            matched.append(item)
    return matched

def get_image_url(item_id, mode):
    if mode == "advance":
        return f"https://rocky-astc2png.onrender.com/advance/{item_id}"
    return f"https://rocky-astc2png.onrender.com/live/{item_id}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    await update.message.reply_text(
        "Send /id followed by ID or keywords (e.g. /id 909050011 or /id Bunny) to search. You'll be asked to pick Live or Advance images."
    )

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    query_args = context.args
    if not query_args:
        await update.message.reply_text("Usage: /id <id or keywords>")
        return
    user_query = " ".join(query_args).strip()
    context.user_data['pending_query'] = user_query
    keyboard = [
        [InlineKeyboardButton("Live", callback_data="imgsrc_live"),
         InlineKeyboardButton("Advance", callback_data="imgsrc_advance")]
    ]
    await update.message.reply_text("Which image type do you want?", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "imgsrc_live":
        img_mode = "live"
    elif data == "imgsrc_advance":
        img_mode = "advance"
    else:
        await query.message.reply_text("Invalid option.")
        return
    pending_query = context.user_data.get("pending_query")
    if not pending_query:
        await query.message.reply_text("No pending search. Please use /id followed by your query.")
        return
    matched_items = find_items(pending_query)
    context.user_data["img_mode"] = img_mode  # Store for paging
    if matched_items:
        context.user_data['matched_items'] = matched_items
        context.user_data['pending_query'] = None
        await send_batch(context, query.message.chat_id, matched_items, 0, img_mode)
    else:
        if pending_query.isdigit():
            await send_unknown_id_image_only(context, query.message.chat_id, pending_query, img_mode)
        else:
            await query.message.reply_text("No items found matching your query.")
        context.user_data['pending_query'] = None

async def send_item_document_with_caption(context, chat_id, item, img_mode):
    credits = "\n— bot by @RockingGamerz65"
    caption = (
        f"Id: {item.get('Id')}\n"
        f"Name: {item.get('name') or 'N/A'}\n"
        f"Icon: {item.get('Icon') or 'N/A'}"
        f"{credits}"
    )
    image_url = get_image_url(item.get('Id'), img_mode)
    try:
        resp = requests.get(image_url)
        resp.raise_for_status()
        bio = io.BytesIO(resp.content)
        bio.name = f"{item.get('Id')}.png"
        bio.seek(0)
        await context.bot.send_document(chat_id=chat_id, document=bio, caption=caption)
    except Exception:
        await context.bot.send_message(chat_id=chat_id, text=caption)

async def send_unknown_id_image_only(context, chat_id, unknown_id, img_mode):
    credits = "\n— bot by @RockingGamerz65"
    caption = (
        f"Id: {unknown_id}\n"
        "No text info available for this ID."
        f"{credits}"
    )
    image_url = get_image_url(unknown_id, img_mode)
    try:
        resp = requests.get(image_url)
        resp.raise_for_status()
        bio = io.BytesIO(resp.content)
        bio.name = f"{unknown_id}.png"
        bio.seek(0)
        await context.bot.send_document(chat_id=chat_id, document=bio, caption=caption)
    except Exception:
        await context.bot.send_message(chat_id=chat_id, text=caption + "\nNo image preview available.")

async def send_batch(context, chat_id, items, offset, img_mode):
    for item in items[offset:offset+BATCH_SIZE]:
        await send_item_document_with_caption(context, chat_id, item, img_mode)
    next_offset = offset + BATCH_SIZE
    credits = "\n\n— bot by @RockingGamerz65"
    if next_offset < len(items):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Next 10 results", callback_data=f"next#{next_offset}")]
        ])
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Showing results {offset+1} to {next_offset} of {len(items)}",
            reply_markup=keyboard
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"End of results. Total matches: {len(items)}{credits}"
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("next#"):
        offset = int(data.split('#')[1])
        matched_items = context.user_data.get('matched_items', [])
        img_mode = context.user_data.get('img_mode', "live")
        if not matched_items:
            await query.message.reply_text("No stored results found. Please use /id to search again.")
            return
        try:
            await query.message.delete()
        except Exception:
            pass
        await send_batch(context, query.message.chat_id, matched_items, offset, img_mode)

# --- FASTAPI APP FOR VERCEL ---
from fastapi import FastAPI, Request

app = FastAPI()
telegram_app: Application = None

@app.on_event("startup")
async def on_startup():
    load_items_data()
    global telegram_app
    telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()
    telegram_app.add_handler(CommandHandler('start', start))
    telegram_app.add_handler(CommandHandler('id', id_command))
    telegram_app.add_handler(CallbackQueryHandler(handle_selection, pattern="^imgsrc_"))
    telegram_app.add_handler(CallbackQueryHandler(button_handler, pattern="^next#"))

@app.post("/")
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}
