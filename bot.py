import os
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from modules.tmdb import search_media
from modules.storage import (
    add_request,
    get_all_requests,
    clear_all_requests,
    get_user_requests,
    delete_user_request,
)

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]


# ---------- Admin check ----------
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ---------- /request ----------
async def request_media(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:
        await update.message.reply_text(
            "Use like this:\n/request Interstellar"
        )
        return

    query = " ".join(context.args)

    results = search_media(query)

    if not results:
        await update.message.reply_text("No results found.")
        return

    context.user_data["last_search"] = results

    keyboard = [
        [
            InlineKeyboardButton(
                f"{'🎬' if m['type']=='movie' else '📺'} {m['title']} ({m['year']})",
                callback_data=str(m["id"])
            )
        ]
        for m in results[:8]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Select what you meant:",
        reply_markup=reply_markup
    )


# ---------- Selection ----------
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    media_id = query.data

    media = None

    for m in context.user_data.get("last_search", []):
        if str(m["id"]) == media_id:
            media = m
            break

    if not media:
        await query.edit_message_text("Item not found.")
        return

    add_request(
        query.from_user.id,
        {
            "id": media["id"],
            "title": media["title"],
            "year": media["year"],
            "type": media["type"],
        },
    )

    poster = None
    if media.get("poster_path"):
        poster = f"https://image.tmdb.org/t/p/w500{media['poster_path']}"

    icon = "🎬" if media["type"] == "movie" else "📺"

    text = f"{icon} Request saved:\n{media['title']} ({media['year']})"

    if poster:
        await query.message.reply_photo(
            photo=poster,
            caption=text
        )
    else:
        await query.message.reply_text(text)

    await query.edit_message_text(
        f"Selected: {media['title']} ({media['year']})"
    )


# ---------- My requests ----------
async def my_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    media = get_user_requests(user_id)

    if not media:
        await update.message.reply_text("You have no requests.")
        return

    text = "Your requests:\n\n"

    for m in media:

        icon = "🎬" if m.get("type") == "movie" else "📺"

        text += f"{icon} {m['title']} ({m['year']})\n"

    await update.message.reply_text(text)


# ---------- Delete request ----------
async def delete_request(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    media = get_user_requests(user_id)

    if not media:
        await update.message.reply_text("You have no requests.")
        return

    keyboard = [
        [
            InlineKeyboardButton(
                f"{m['title']} ({m['year']})",
                callback_data=f"del:{m['id']}"
            )
        ]
        for m in media
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Select request to delete:",
        reply_markup=reply_markup
    )


async def delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    media_id = query.data.split(":")[1]

    success = delete_user_request(query.from_user.id, media_id)

    if success:
        await query.edit_message_text("Request deleted.")
    else:
        await query.edit_message_text("Could not delete request.")


# ---------- Admin ----------
async def all_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Not allowed.")
        return

    data = get_all_requests()

    if not data:
        await update.message.reply_text("No requests.")
        return

    text = ""

    for user_id, media in data.items():

        text += f"User {user_id}\n"

        for m in media:

            icon = "🎬" if m.get("type") == "movie" else "📺"

            text += f" {icon} {m['title']} ({m['year']})\n"

        text += "\n"

    await update.message.reply_text(text)


async def clear_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Not allowed.")
        return

    clear_all_requests()

    await update.message.reply_text("All requests cleared.")


# ---------- Help ----------
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = """
User commands

/request <name> - search movie or series
/my_requests - show your requests
/delete_request - delete request

Admin

/all_requests
/clear_requests
"""

    await update.message.reply_text(text)


# ---------- Main ----------
def main():

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("request", request_media))
    app.add_handler(CommandHandler("my_requests", my_requests))
    app.add_handler(CommandHandler("delete_request", delete_request))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(CommandHandler("all_requests", all_requests))
    app.add_handler(CommandHandler("clear_requests", clear_requests))

    app.add_handler(CallbackQueryHandler(delete_callback, pattern="^del:"))
    app.add_handler(CallbackQueryHandler(button_callback))

    app.run_polling()


if __name__ == "__main__":
    main()