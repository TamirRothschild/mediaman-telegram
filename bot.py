import os
import subprocess
from dotenv import load_dotenv
import asyncio

from telegram.request import HTTPXRequest
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from modules.tmdb import search_media
from modules.yts import search_yts
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
TRANSMISSION_HOST = os.getenv("TRANSMISSION_HOST", "127.0.0.1:9091")
TRANSMISSION_USER = os.getenv("TRANSMISSION_USER", "tamir")
TRANSMISSION_PASS = os.getenv("TRANSMISSION_PASS", "TamRoth12")


# ---------- Admin check ----------
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ---------- Build requests keyboard ----------
def build_requests_keyboard(all_requests: dict, selected: set) -> InlineKeyboardMarkup:
    """Build inline keyboard with all requests, checkmarks for selected ones."""
    keyboard = []

    for user_id, media_list in all_requests.items():
        for m in media_list:
            key = f"{m['id']}|{m['title']}"
            icon = "✅" if key in selected else "⬜"
            label = f"{icon} {m['title']} ({m['year']})"
            keyboard.append([
                InlineKeyboardButton(label, callback_data=f"tog:{m['id']}:{m['title'][:30]}")
            ])

    keyboard.append([
        InlineKeyboardButton("⬇️ Download Selected", callback_data="dlsel:go")
    ])

    return InlineKeyboardMarkup(keyboard)


# ---------- /request ----------
async def request_media(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:
        await update.message.reply_text("Use like this:\n/request Interstellar")
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

    await update.message.reply_text(
        "Select what you meant:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ---------- /request selection callback ----------
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
        for attempt in range(3):
            try:
                await query.message.reply_photo(photo=poster, caption=text)
                break
            except Exception:
                if attempt == 2:
                    await query.message.reply_text(text)
                await asyncio.sleep(2)
    else:
        await query.message.reply_text(text)

    await query.edit_message_text(
        f"Selected: {media['title']} ({media['year']})"
    )


# ---------- /download_requests — admin multi-select ----------
async def download_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Not allowed.")
        return

    all_req = get_all_requests()

    if not all_req:
        await update.message.reply_text("No pending requests.")
        return

    # Reset selection
    context.user_data["dl_selected"] = set()
    context.user_data["dl_all_requests"] = all_req

    keyboard = build_requests_keyboard(all_req, set())

    await update.message.reply_text(
        "📋 Select requests to download:",
        reply_markup=keyboard
    )


# ---------- Toggle selection callback ----------
async def toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    # callback_data = "tog:{id}:{title}"
    parts = query.data.split(":", 2)
    media_id = parts[1]
    title = parts[2] if len(parts) > 2 else ""
    key = f"{media_id}|{title}"

    selected: set = context.user_data.get("dl_selected", set())

    if key in selected:
        selected.discard(key)
    else:
        selected.add(key)

    context.user_data["dl_selected"] = selected

    all_req = context.user_data.get("dl_all_requests", get_all_requests())
    keyboard = build_requests_keyboard(all_req, selected)

    await query.edit_message_reply_markup(reply_markup=keyboard)


# ---------- Download selected callback ----------
async def download_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    selected: set = context.user_data.get("dl_selected", set())

    if not selected:
        await query.answer("No requests selected!", show_alert=True)
        return

    await query.edit_message_text("🔍 Searching YTS for selected movies...")

    # Build list of titles to search
    titles = [key.split("|", 1)[1] for key in selected]

    # Store queue for sequential quality selection
    context.user_data["dl_queue"] = titles
    context.user_data["dl_queue_index"] = 0
    context.user_data["dl_yts_results"] = {}

    await process_next_in_queue(query.message, context)


async def process_next_in_queue(message, context: ContextTypes.DEFAULT_TYPE):
    """Search YTS for next title in queue and show quality selection."""

    queue = context.user_data.get("dl_queue", [])
    index = context.user_data.get("dl_queue_index", 0)

    if index >= len(queue):
        await message.reply_text("✅ All done! Check Transmission for downloads.")
        return

    title = queue[index]
    await message.reply_text(f"🔍 Searching YTS for: {title}")

    results = search_yts(title)

    if not results:
        await message.reply_text(f"❌ Not found on YTS: {title}\nSkipping...")
        context.user_data["dl_queue_index"] = index + 1
        await process_next_in_queue(message, context)
        return

    # Store results for this title
    context.user_data["dl_yts_results"][title] = results
    context.user_data["dl_current_title"] = title

    # Show movie selection
    keyboard = [
        [
            InlineKeyboardButton(
                f"🎬 {m['title']} ({m['year']}) ⭐{m['rating']}",
                callback_data=f"qmov:{i}"
            )
        ]
        for i, m in enumerate(results[:5])
    ]
    keyboard.append([InlineKeyboardButton("⏭ Skip this one", callback_data="qmov:skip")])

    await message.reply_text(
        f"Select the correct movie for: *{title}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ---------- Queue: movie selection callback ----------
async def queue_movie_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    data = query.data.split(":")[1]

    if data == "skip":
        context.user_data["dl_queue_index"] = context.user_data.get("dl_queue_index", 0) + 1
        await query.edit_message_text("⏭ Skipped.")
        await process_next_in_queue(query.message, context)
        return

    movie_index = int(data)
    title = context.user_data.get("dl_current_title")
    results = context.user_data["dl_yts_results"].get(title, [])
    movie = results[movie_index]

    context.user_data["dl_current_movie"] = movie

    if not movie["torrents"]:
        await query.edit_message_text(f"❌ No torrents for {movie['title']}. Skipping...")
        context.user_data["dl_queue_index"] = context.user_data.get("dl_queue_index", 0) + 1
        await process_next_in_queue(query.message, context)
        return

    keyboard = [
        [
            InlineKeyboardButton(
                f"📦 {t['quality']} — {t['size']}",
                callback_data=f"qqdl:{i}"
            )
        ]
        for i, t in enumerate(movie["torrents"])
    ]
    keyboard.append([InlineKeyboardButton("⏭ Skip this one", callback_data="qqdl:skip")])

    await query.edit_message_text(
        f"🎬 {movie['title']} ({movie['year']})\n\nSelect quality:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ---------- Queue: quality selection → Transmission ----------
async def queue_quality_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    data = query.data.split(":")[1]

    if data == "skip":
        await query.edit_message_text("⏭ Skipped.")
        context.user_data["dl_queue_index"] = context.user_data.get("dl_queue_index", 0) + 1
        await process_next_in_queue(query.message, context)
        return

    torrent_index = int(data)
    movie = context.user_data.get("dl_current_movie")
    torrent = movie["torrents"][torrent_index]

    await query.edit_message_text(
        f"⏳ Adding: {movie['title']} ({movie['year']}) — {torrent['quality']}"
    )

    try:
        result = subprocess.run(
            [
                "transmission-remote", TRANSMISSION_HOST,
                "--auth", f"{TRANSMISSION_USER}:{TRANSMISSION_PASS}",
                "--add", torrent["magnet"],
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode == 0:
            await query.message.reply_text(
                f"✅ Added!\n"
                f"🎬 {movie['title']} ({movie['year']})\n"
                f"📦 {torrent['quality']} — {torrent['size']}"
            )
        else:
            await query.message.reply_text(
                f"❌ Failed: {result.stderr or result.stdout}"
            )

    except FileNotFoundError:
        await query.message.reply_text("❌ transmission-remote not found.")
    except subprocess.TimeoutExpired:
        await query.message.reply_text("❌ Transmission timed out.")
    except Exception as e:
        await query.message.reply_text(f"❌ Error: {e}")

    # Move to next in queue
    context.user_data["dl_queue_index"] = context.user_data.get("dl_queue_index", 0) + 1
    await process_next_in_queue(query.message, context)


# ---------- /download — search YTS directly ----------
async def download_media(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Not allowed.")
        return

    if not context.args:
        await update.message.reply_text("Use like this:\n/download Interstellar")
        return

    query = " ".join(context.args)
    await update.message.reply_text(f"🔍 Searching YTS for: {query}")

    results = search_yts(query)

    if not results:
        await update.message.reply_text("No results found on YTS.")
        return

    context.user_data["yts_search"] = results

    keyboard = [
        [
            InlineKeyboardButton(
                f"🎬 {m['title']} ({m['year']}) ⭐{m['rating']}",
                callback_data=f"yts:{m['id']}"
            )
        ]
        for m in results[:8]
    ]

    await update.message.reply_text(
        "Select a movie to download:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ---------- YTS movie selection ----------
async def yts_movie_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("Not allowed.")
        return

    movie_id = int(query.data.split(":")[1])
    movie = next((m for m in context.user_data.get("yts_search", []) if m["id"] == movie_id), None)

    if not movie:
        await query.edit_message_text("Movie not found.")
        return

    if not movie["torrents"]:
        await query.edit_message_text("No torrents available.")
        return

    context.user_data["yts_selected"] = movie

    keyboard = [
        [
            InlineKeyboardButton(
                f"📦 {t['quality']} — {t['size']}",
                callback_data=f"ytsdl:{i}"
            )
        ]
        for i, t in enumerate(movie["torrents"])
    ]

    await query.edit_message_text(
        f"🎬 {movie['title']} ({movie['year']})\n\nSelect quality:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ---------- YTS quality → Transmission ----------
async def yts_quality_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("Not allowed.")
        return

    torrent_index = int(query.data.split(":")[1])
    movie = context.user_data.get("yts_selected")

    if not movie:
        await query.edit_message_text("Session expired, please search again.")
        return

    torrent = movie["torrents"][torrent_index]

    await query.edit_message_text(
        f"⏳ Adding: {movie['title']} ({movie['year']}) — {torrent['quality']}"
    )

    try:
        result = subprocess.run(
            [
                "transmission-remote", TRANSMISSION_HOST,
                "--auth", f"{TRANSMISSION_USER}:{TRANSMISSION_PASS}",
                "--add", torrent["magnet"],
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode == 0:
            await query.message.reply_text(
                f"✅ Added to Transmission!\n"
                f"🎬 {movie['title']} ({movie['year']})\n"
                f"📦 {torrent['quality']} — {torrent['size']}"
            )
        else:
            await query.message.reply_text(
                f"❌ Failed: {result.stderr or result.stdout}"
            )

    except FileNotFoundError:
        await query.message.reply_text("❌ transmission-remote not found.")
    except subprocess.TimeoutExpired:
        await query.message.reply_text("❌ Transmission timed out.")
    except Exception as e:
        await query.message.reply_text(f"❌ Error: {e}")


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

    await update.message.reply_text(
        "Select request to delete:",
        reply_markup=InlineKeyboardMarkup(keyboard)
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


# ---------- Admin: all requests ----------
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
        username = media[0].get("username") if media and "username" in media[0] else f"User {user_id}"
        text += f"{username}\n"
        for m in media:
            icon = "🎬" if m.get("type") == "movie" else "📺"
            text += f" {icon} {m['title']} ({m['year']})\n"
        text += "\n"

    await update.message.reply_text(text)


# ---------- Clear Requests ----------
async def clear_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Not allowed.")
        return

    keyboard = [
        [InlineKeyboardButton("Yes ✅", callback_data="clear:1")],
        [InlineKeyboardButton("No ❌", callback_data="clear:cancel")]
    ]
    await update.message.reply_text(
        "Are you sure you want to clear all requests?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def clear_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("Not allowed.")
        return

    data = query.data

    if data == "clear:cancel":
        await query.edit_message_text("Clearing canceled ❌")
        return

    if data == "clear:1":
        keyboard = [
            [InlineKeyboardButton("Yes, really ✅", callback_data="clear:2")],
            [InlineKeyboardButton("No ❌", callback_data="clear:cancel")]
        ]
        await query.edit_message_text(
            "Are you REALLY sure?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if data == "clear:2":
        clear_all_requests()
        await query.edit_message_text("All requests cleared ✅")
        return


# ---------- Help ----------
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
User commands

/request <name> - search movie or series
/my_requests - show your requests
/delete_request - delete a request

Admin

/all_requests - view all requests
/download_requests - select & download from requests list
/download <name> - search & download directly from YTS
/clear_requests - clear all requests
"""
    await update.message.reply_text(text)


# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "שלום! 👋\n"
        "ברוכים הבאים ל-MediaMan Bot.\n"
        "אתם יכולים לבקש סרטים או סדרות, לראות את הבקשות שלכם ולמחוק אותן.\n\n"
        "לרשימה מלאה של הפקודות הזינו /help"
    )
    await update.message.reply_text(text)


# ---------- Main ----------
def main():
    request = HTTPXRequest(
        connection_pool_size=8,
        read_timeout=30,
        write_timeout=30,
        connect_timeout=15,
        http_version="1.1",
    )
    app = ApplicationBuilder().token(TOKEN).request(request).build()

    # User commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("request", request_media))
    app.add_handler(CommandHandler("my_requests", my_requests))
    app.add_handler(CommandHandler("delete_request", delete_request))
    app.add_handler(CommandHandler("help", help_command))

    # Admin commands
    app.add_handler(CommandHandler("all_requests", all_requests))
    app.add_handler(CommandHandler("clear_requests", clear_requests))
    app.add_handler(CommandHandler("download", download_media))
    app.add_handler(CommandHandler("download_requests", download_requests))

    # Callback handlers — סדר חשוב! ספציפי לפני כללי
    app.add_handler(CallbackQueryHandler(clear_callback,         pattern="^clear:"))
    app.add_handler(CallbackQueryHandler(delete_callback,        pattern="^del:"))
    app.add_handler(CallbackQueryHandler(toggle_callback,        pattern="^tog:"))
    app.add_handler(CallbackQueryHandler(download_selected_callback, pattern="^dlsel:"))
    app.add_handler(CallbackQueryHandler(queue_movie_callback,   pattern="^qmov:"))
    app.add_handler(CallbackQueryHandler(queue_quality_callback, pattern="^qqdl:"))
    app.add_handler(CallbackQueryHandler(yts_movie_callback,     pattern="^yts:"))
    app.add_handler(CallbackQueryHandler(yts_quality_callback,   pattern="^ytsdl:"))
    app.add_handler(CallbackQueryHandler(button_callback))

    app.run_polling(timeout=30)


if __name__ == "__main__":
    main()