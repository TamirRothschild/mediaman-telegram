import os
import subprocess
import logging
import asyncio
from dotenv import load_dotenv

from telegram.request import HTTPXRequest
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

from modules.tmdb import search_media, get_movie_details, get_trending
from modules.plex import search_plex, get_stream_url, get_episode_stream, get_show_seasons, get_season_episodes, get_movie_plex
from modules.yts import search_yts
from modules.storage import add_request, get_all_requests, clear_all_requests, get_user_requests, delete_user_request, delete_requests_by_title, get_requesters_by_title, log_download, get_stats, get_activity, log

load_dotenv()

TOKEN             = os.getenv("TELEGRAM_TOKEN")
ADMIN_IDS         = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]
TRANSMISSION_HOST = os.getenv("TRANSMISSION_HOST", "127.0.0.1:9091")
TRANSMISSION_USER = os.getenv("TRANSMISSION_USER", "tamir")
TRANSMISSION_PASS = os.getenv("TRANSMISSION_PASS", "TamRoth12")

logging.basicConfig(level=logging.WARNING)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def is_admin(user_id): return user_id in ADMIN_IDS

def get_username(user):
    return f"@{user.username}" if user.username else (user.full_name or str(user.id))

def build_requests_keyboard(all_req, selected):
    keyboard = []
    for uid, media_list in all_req.items():
        for m in media_list:
            key  = f"{m['id']}|{m['title']}"
            icon = "✅" if key in selected else "⬜"
            who  = m.get("username") or f"User {uid}"
            keyboard.append([InlineKeyboardButton(f"{icon} {m['title']} ({m['year']}) — {who}", callback_data=f"tog:{m['id']}:{m['title'][:30]}")])
    keyboard.append([InlineKeyboardButton("⬇️ Download Selected", callback_data="dlsel:go")])
    return InlineKeyboardMarkup(keyboard)

async def send_to_transmission(magnet):
    try:
        r = subprocess.run(["transmission-remote", TRANSMISSION_HOST, "--auth", f"{TRANSMISSION_USER}:{TRANSMISSION_PASS}", "--add", magnet], capture_output=True, text=True, timeout=15)
        return (True, "") if r.returncode == 0 else (False, r.stderr or r.stdout)
    except FileNotFoundError: return False, "transmission-remote not found."
    except subprocess.TimeoutExpired: return False, "Transmission timed out."
    except Exception as e: return False, str(e)

# ─── /start ───────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("שלום! 👋\nברוכים הבאים ל-MediaMan Bot.\nאתם יכולים לבקש סרטים או סדרות, לראות את הבקשות שלכם ולמחוק אותן.\n\nלרשימה מלאה של הפקודות הזינו /help")

# ─── /request ─────────────────────────────────────────────────────────────────

async def request_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use like this:\n/request Interstellar")
        return
    results = search_media(" ".join(context.args))
    if not results:
        await update.message.reply_text("No results found.")
        return
    context.user_data["last_search"] = results
    keyboard = [[InlineKeyboardButton(
        f"{'🎬' if m['type']=='movie' else '📺'} {m['title']} ({m['year']}) ⭐{m['rating']}",
        callback_data=str(m["id"])
    )] for m in results[:8]]
    await update.message.reply_text("Select what you meant:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    media = next((m for m in context.user_data.get("last_search", []) if str(m["id"]) == query.data), None)
    if not media:
        await query.edit_message_text("Item not found.")
        return
    username = get_username(query.from_user)
    # Check Plex first
    plex = search_plex(media["title"], media["type"], year=media.get("year"), imdb_id=media.get("imdb_id"))

    details = get_movie_details(media["id"], media["type"])
    icon    = "🎬" if media["type"] == "movie" else "📺"
    poster  = f"https://image.tmdb.org/t/p/w500{media['poster_path']}" if media.get("poster_path") else None

    if plex:
        # Already on Plex — show poster + notify, delete any existing request
        plex_title = plex.get("title") or media["title"]
        text = (
            f"🎉 Good news!\n"
            f"{icon} *{plex_title}* ({plex.get('year') or media['year']}) "
            f"is already available on Plex!\n\n"
            f"⭐ {details['rating']} | ⏱ {details['runtime']}\n"
            f"▶️ Open Plex and enjoy!"
        )
        # Always use TMDb poster for better quality
        thumb = poster
        # Build stream button
        stream_url = get_stream_url(media["title"], media["type"])
        keyboard = None
        if stream_url:
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("▶️ Watch on Plex", url=stream_url)
            ]])

        sent = False
        if thumb:
            try:
                await query.message.reply_photo(
                    photo=thumb,
                    caption=text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
                sent = True
            except Exception:
                pass
        if not sent:
            await query.message.reply_text(
                text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        # Delete any existing request for this title
        delete_requests_by_title(media["title"])
        log(f"PLEX HIT | user={username} | {plex_title} ({plex.get('year') or media['year']})")
        await query.edit_message_text(f"✅ Available on Plex: {plex_title}")
        return

    # Not on Plex — save request normally
    add_request(query.from_user.id, {"id": media["id"], "title": media["title"], "year": media["year"], "type": media["type"]}, username=username)

    text = (
        f"{icon} *{media['title']}* ({media['year']})\n"
        f"⭐ {details['rating']} | ⏱ {details['runtime']}\n\n"
        f"✅ Request saved!"
    )

    if poster:
        for attempt in range(3):
            try:
                await query.message.reply_photo(photo=poster, caption=text, parse_mode="Markdown")
                break
            except Exception:
                if attempt == 2:
                    await query.message.reply_text(text, parse_mode="Markdown")
                await asyncio.sleep(2)
    else:
        await query.message.reply_text(text, parse_mode="Markdown")

    await query.edit_message_text(f"Selected: {media['title']} ({media['year']})")

# ─── /trending ────────────────────────────────────────────────────────────────

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 Fetching trending movies...")
    movies = get_trending()
    if not movies:
        await update.message.reply_text("Could not fetch trending movies.")
        return
    context.user_data["last_search"] = movies
    keyboard = [[InlineKeyboardButton(f"🎬 {m['title']} ({m['year']}) ⭐{m['rating']}", callback_data=str(m["id"]))] for m in movies]
    await update.message.reply_text("🔥 Trending this week — tap to request:", reply_markup=InlineKeyboardMarkup(keyboard))

# ─── /my_requests ─────────────────────────────────────────────────────────────

async def my_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    media = get_user_requests(update.effective_user.id)
    if not media:
        await update.message.reply_text("You have no requests.")
        return
    text = "Your requests:\n\n"
    for m in media:
        icon  = "🎬" if m.get("media_type") == "movie" else "📺"
        text += f"{icon} {m['title']} ({m['year']})\n"
    await update.message.reply_text(text)

# ─── /delete_request ──────────────────────────────────────────────────────────

async def delete_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    media = get_user_requests(update.effective_user.id)
    if not media:
        await update.message.reply_text("You have no requests.")
        return
    keyboard = [[InlineKeyboardButton(f"{m['title']} ({m['year']})", callback_data=f"del:{m['media_id']}")] for m in media]
    await update.message.reply_text("Select request to delete:", reply_markup=InlineKeyboardMarkup(keyboard))

async def delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    success = delete_user_request(query.from_user.id, query.data.split(":")[1])
    await query.edit_message_text("Request deleted." if success else "Could not delete request.")

# ─── /download — direct YTS search ───────────────────────────────────────────

async def download_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Not allowed.")
        return
    if not context.args:
        await update.message.reply_text("Use like this:\n/download Interstellar")
        return
    query   = " ".join(context.args)
    await update.message.reply_text(f"🔍 Searching YTS for: {query}")
    results = search_yts(query)
    if not results:
        await update.message.reply_text("No results found on YTS.")
        return
    context.user_data["yts_search"] = results
    keyboard = [[InlineKeyboardButton(f"🎬 {m['title']} ({m['year']}) ⭐{m['rating']}", callback_data=f"yts:{m['id']}")] for m in results[:8]]
    await update.message.reply_text("Select a movie to download:", reply_markup=InlineKeyboardMarkup(keyboard))

async def yts_movie_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    movie = next((m for m in context.user_data.get("yts_search", []) if m["id"] == int(query.data.split(":")[1])), None)
    if not movie or not movie["torrents"]:
        await query.edit_message_text("No torrents available.")
        return
    context.user_data["yts_selected"] = movie
    runtime_str = f" | ⏱ {movie['runtime']}min" if movie.get("runtime") else ""
    caption     = f"🎬 *{movie['title']}* ({movie['year']})\n⭐ {movie['rating']}{runtime_str}\n\nSelect quality:"
    keyboard    = [[InlineKeyboardButton(f"📦 {t['quality']} — {t['size']}", callback_data=f"ytsdl:{i}")] for i, t in enumerate(movie["torrents"])]
    if movie.get("poster"):
        await query.message.reply_photo(photo=movie["poster"], caption=caption, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        await query.edit_message_text(f"Selected: {movie['title']}")
    else:
        await query.edit_message_text(caption, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def yts_quality_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    movie   = context.user_data.get("yts_selected")
    if not movie:
        await query.edit_message_text("Session expired.")
        return
    torrent    = movie["torrents"][int(query.data.split(":")[1])]
    ok, errmsg = await send_to_transmission(torrent["magnet"])
    if ok:
        log(f"DOWNLOAD | {movie['title']} ({movie['year']}) | {torrent['quality']}")
        await query.message.reply_text(f"✅ Added to Transmission!\n🎬 {movie['title']} ({movie['year']})\n📦 {torrent['quality']} — {torrent['size']}")
    else:
        await query.message.reply_text(f"❌ Failed: {errmsg}")
    try: await query.edit_message_reply_markup(reply_markup=None)
    except Exception: pass

# ─── /download_requests ───────────────────────────────────────────────────────

async def download_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Not allowed.")
        return
    all_req = get_all_requests()
    if not all_req:
        await update.message.reply_text("No pending requests.")
        return
    context.user_data["dl_selected"]     = set()
    context.user_data["dl_all_requests"] = all_req
    await update.message.reply_text("📋 Select requests to download:", reply_markup=build_requests_keyboard(all_req, set()))

async def toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    parts    = query.data.split(":", 2)
    key      = f"{parts[1]}|{parts[2] if len(parts)>2 else ''}"
    selected = context.user_data.get("dl_selected", set())
    selected.discard(key) if key in selected else selected.add(key)
    context.user_data["dl_selected"] = selected
    all_req  = context.user_data.get("dl_all_requests", get_all_requests())
    await query.edit_message_reply_markup(reply_markup=build_requests_keyboard(all_req, selected))

async def download_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    selected = context.user_data.get("dl_selected", set())
    if not selected:
        await query.answer("No requests selected!", show_alert=True)
        return
    await query.edit_message_text("🔍 Searching YTS for selected movies...")
    context.user_data["dl_queue"]       = [key.split("|", 1)[1] for key in selected]
    context.user_data["dl_queue_index"] = 0
    context.user_data["dl_yts_results"] = {}
    await process_next_in_queue(query.message, context)

async def process_next_in_queue(message, context):
    queue = context.user_data.get("dl_queue", [])
    index = context.user_data.get("dl_queue_index", 0)
    if index >= len(queue):
        await message.reply_text("✅ All done! Check Transmission for downloads.")
        return
    title   = queue[index]
    results = search_yts(title)
    if not results:
        await message.reply_text(f"❌ Not found on YTS: *{title}* — skipping.", parse_mode="Markdown")
        context.user_data["dl_queue_index"] = index + 1
        await process_next_in_queue(message, context)
        return
    context.user_data["dl_yts_results"][title] = results
    context.user_data["dl_current_title"]       = title
    keyboard = [[InlineKeyboardButton(f"🎬 {m['title']} ({m['year']}) ⭐{m['rating']}", callback_data=f"qmov:{i}")] for i, m in enumerate(results[:5])]
    keyboard.append([InlineKeyboardButton("⏭ Skip", callback_data="qmov:skip")])
    await message.reply_text(f"🔍 Results for: *{title}*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def queue_movie_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    data = query.data.split(":")[1]
    if data == "skip":
        context.user_data["dl_queue_index"] = context.user_data.get("dl_queue_index", 0) + 1
        await query.edit_message_text("⏭ Skipped.")
        await process_next_in_queue(query.message, context)
        return
    title   = context.user_data.get("dl_current_title")
    movie   = context.user_data["dl_yts_results"].get(title, [])[int(data)]
    if not movie["torrents"]:
        context.user_data["dl_queue_index"] = context.user_data.get("dl_queue_index", 0) + 1
        await query.edit_message_text("❌ No torrents. Skipping...")
        await process_next_in_queue(query.message, context)
        return
    context.user_data["dl_current_movie"] = movie
    runtime_str = f" | ⏱ {movie['runtime']}min" if movie.get("runtime") else ""
    caption     = f"🎬 *{movie['title']}* ({movie['year']})\n⭐ {movie['rating']}{runtime_str}\n\nSelect quality:"
    keyboard    = [[InlineKeyboardButton(f"📦 {t['quality']} — {t['size']}", callback_data=f"qqdl:{i}")] for i, t in enumerate(movie["torrents"])]
    keyboard.append([InlineKeyboardButton("⏭ Skip", callback_data="qqdl:skip")])
    if movie.get("poster"):
        await query.message.reply_photo(photo=movie["poster"], caption=caption, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        await query.edit_message_text(f"Selected: {movie['title']}")
    else:
        await query.edit_message_text(caption, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def queue_quality_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    data = query.data.split(":")[1]
    if data == "skip":
        await query.edit_message_text("⏭ Skipped.")
        context.user_data["dl_queue_index"] = context.user_data.get("dl_queue_index", 0) + 1
        await process_next_in_queue(query.message, context)
        return
    movie      = context.user_data.get("dl_current_movie")
    torrent    = movie["torrents"][int(data)]
    ok, errmsg = await send_to_transmission(torrent["magnet"])
    if ok:
        log_download(movie["title"], movie["year"], torrent["quality"])
        await query.message.reply_text(
            f"✅ Added!\n🎬 {movie['title']} ({movie['year']})\n📦 {torrent['quality']} — {torrent['size']}"
        )
        # Notify all users who requested this movie
        requesters = get_requesters_by_title(movie["title"])
        for requester in requesters:
            try:
                await context.bot.send_message(
                    chat_id=int(requester["user_id"]),
                    text=(
                        f"🎬 Good news! *{movie['title']}* ({movie['year']}) "
                        f"has been added for download!\n📦 Quality: {torrent['quality']}"
                    ),
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        # Auto-delete requests for this title
        delete_requests_by_title(movie["title"])
    else:
        await query.message.reply_text(f"❌ Failed: {errmsg}")
    try: await query.edit_message_reply_markup(reply_markup=None)
    except Exception: pass
    context.user_data["dl_queue_index"] = context.user_data.get("dl_queue_index", 0) + 1
    await process_next_in_queue(query.message, context)

# ─── Admin ────────────────────────────────────────────────────────────────────

async def all_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Not allowed.")
        return
    data = get_all_requests()
    if not data:
        await update.message.reply_text("No requests.")
        return
    text = ""
    for uid, media_list in data.items():
        who   = media_list[0].get("username") or f"User {uid}"
        text += f"{who}\n"
        for m in media_list:
            text += f"  {'🎬' if m.get('type')=='movie' else '📺'} {m['title']} ({m['year']})\n"
        text += "\n"
    await update.message.reply_text(text)

async def clear_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Not allowed.")
        return
    keyboard = [[InlineKeyboardButton("Yes ✅", callback_data="clear:1")], [InlineKeyboardButton("No ❌", callback_data="clear:cancel")]]
    await update.message.reply_text("Are you sure you want to clear all requests?", reply_markup=InlineKeyboardMarkup(keyboard))

async def clear_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("Not allowed.")
        return
    if query.data == "clear:cancel":
        await query.edit_message_text("Clearing canceled ❌")
        return
    if query.data == "clear:1":
        keyboard = [[InlineKeyboardButton("Yes, really ✅", callback_data="clear:2")], [InlineKeyboardButton("No ❌", callback_data="clear:cancel")]]
        await query.edit_message_text("Are you REALLY sure?", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    if query.data == "clear:2":
        clear_all_requests()
        await query.edit_message_text("All requests cleared ✅")



async def activity_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Not allowed.")
        return
    logs = get_activity(limit=30)
    if not logs:
        await update.message.reply_text("No activity yet.")
        return
    text = "📋 *Recent Activity:*\n\n"
    for entry in logs:
        ts    = entry["timestamp"][:16]
        text += f"`{ts}` {entry['message']}\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def requests_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Not allowed.")
        return
    stats = get_stats()
    text = "📊 *Stats*\n\n"
    text += f"📋 Total open requests: *{stats['total_requests']}*\n"
    text += f"⬇️ Total downloads: *{stats['total_downloads']}*\n\n"
    if stats["top_users"]:
        text += "👤 *Top requesters:*\n"
        for i, u in enumerate(stats["top_users"], 1):
            name = u.get("username") or f"User {u['user_id']}"
            text += f"  {i}. {name} — {u['count']} requests\n"
    if stats["recent_downloads"]:
        text += "\n🎬 *Recent downloads:*\n"
        for d in stats["recent_downloads"]:
            text += f"  • {d['title']} ({d['year']}) {d['quality']}\n"
    await update.message.reply_text(text, parse_mode="Markdown")

# ─── /help ────────────────────────────────────────────────────────────────────

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""User commands

/request <n>      - search & request movie or series
/my_requests      - show your requests
/delete_request   - delete a request
/trending         - show trending movies this week
/stream <show>    - browse & watch show episodes from Plex

Admin

/all_requests          - view all requests
/download_requests     - select & download from requests list
/download <n>          - search & download directly from YTS
/clear_requests        - clear all requests
/requests_stats        - stats & top requesters
/activity              - recent activity log
/restart               - restart bot
/restart server        - reboot server""")

# ─── Main ─────────────────────────────────────────────────────────────────────


async def debug_plex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /debugplex <name>")
        return

    query = " ".join(context.args)

    results = search_media(query)
    if not results:
        await update.message.reply_text("TMDb: No results found.")
        return

    for m in results:
        plex = search_plex(m["title"], m["type"], year=m.get("year"), imdb_id=m.get("imdb_id"))
        if plex:
            await update.message.reply_text(
                f"✅ Found on Plex!\n"
                f"TMDb: {m['title']} ({m['year']})\n"
                f"Plex: {plex['title']} ({plex['year']})"
            )
            return

    await update.message.reply_text("❌ Not found on Plex.")



async def stream_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /stream <title>"""
    if not context.args:
        await update.message.reply_text("Usage: /stream <title>\nExample: /stream Seinfeld\nExample: /stream Iron Man")
        return

    show = " ".join(context.args)
    await update.message.reply_text(f"🔍 Looking for {show} on Plex...")

    # Try movie first
    movie = get_movie_plex(show)
    if movie:
        text = (
            f"🎬 *{movie['title']}* ({movie['year']})"
        )
        buttons = [InlineKeyboardButton("🖥 Watch on Web", url=movie["stream_url"])]
        if movie.get("direct_url"):
            buttons.append(InlineKeyboardButton("📁 Direct File", url=movie["direct_url"]))
        keyboard = InlineKeyboardMarkup([buttons])

        if movie.get("plex_app_url"):
            text += f"\n\n📱 *Open in Plex app:*\n`{movie['plex_app_url']}`"

        if movie.get("thumb"):
            try:
                await update.message.reply_photo(
                    photo=movie["thumb"],
                    caption=text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
                return
            except Exception:
                pass
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
        return

    # Try TV show
    seasons = get_show_seasons(show)

    if not seasons:
        await update.message.reply_text(f"❌ Could not find *{show}* on Plex.", parse_mode="Markdown")
        return

    context.user_data["stream_seasons"] = {str(s["key"]): s for s in seasons}

    # Build seasons keyboard — 3 per row
    buttons = [
        InlineKeyboardButton(
            f"S{s['season_num']:02d} ({s['episode_count']} ep)",
            callback_data=f"strs:{s['key']}"
        )
        for s in seasons
    ]
    keyboard = [buttons[i:i+3] for i in range(0, len(buttons), 3)]

    show_title = seasons[0]["show_title"]
    await update.message.reply_text(
        f"📺 *{show_title}*\nSelect a season:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def stream_season_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User selected a season — show episodes."""
    query = update.callback_query
    await query.answer()

    season_key = query.data.split(":")[1]
    season_info = context.user_data.get("stream_seasons", {}).get(season_key, {})

    episodes = get_season_episodes(season_key)
    if not episodes:
        await query.edit_message_text("❌ No episodes found.")
        return

    context.user_data["stream_episodes"] = {str(e["key"]): e for e in episodes}

    # Build episodes keyboard — 4 per row
    buttons = [
        InlineKeyboardButton(
            f"E{e['episode_num']:02d}",
            callback_data=f"strep:{e['key']}"
        )
        for e in episodes
    ]
    keyboard = [buttons[i:i+4] for i in range(0, len(buttons), 4)]
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="strback")])

    show_title = episodes[0]["show"] if episodes else "Show"
    season_num = season_info.get("season_num", "?")

    await query.edit_message_text(
        f"📺 *{show_title}* — Season {season_num}\nSelect an episode:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def stream_episode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User selected an episode — show Plex link."""
    query = update.callback_query
    await query.answer()

    ep_key = query.data.split(":")[1]
    ep = context.user_data.get("stream_episodes", {}).get(ep_key)

    if not ep or not ep.get("stream_url"):
        await query.edit_message_text("❌ Episode not found.")
        return

    text = (
        f"📺 *{ep['show']}* — S{ep['season']:02d}E{ep['episode_num']:02d}\n"
        f"*{ep['title']}*\n"
        f"⏱ {ep['duration']}min"
    )

    # Buttons
    buttons = [InlineKeyboardButton("🖥 Watch on Web", url=ep["stream_url"])]
    if ep.get("direct_url"):
        buttons.append(InlineKeyboardButton("📁 Direct File", url=ep["direct_url"]))
    keyboard = InlineKeyboardMarkup([buttons])

    # plex:// deep link as plain text for mobile
    if ep.get("plex_app_url"):
        text += f"\n\n📱 *Open in Plex app:*\n`{ep['plex_app_url']}`"

    if ep.get("thumb"):
        try:
            await query.message.reply_photo(
                photo=ep["thumb"],
                caption=text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            await query.edit_message_text(f"✅ {ep['show']} S{ep['season']:02d}E{ep['episode_num']:02d}")
            return
        except Exception:
            pass

    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)

async def restart_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Not allowed.")
        return

    args = context.args
    target = args[0].lower() if args else "bot"

    if target not in ("bot", "server"):
        await update.message.reply_text(
            "Usage:\n"
            "/restart — restart bot\n"
            "/restart server — reboot server"
        )
        return

    label = "bot service" if target == "bot" else "SERVER"
    keyboard = [
        [InlineKeyboardButton(f"Yes ✅", callback_data=f"rst1:{target}")],
        [InlineKeyboardButton("No ❌", callback_data="rst:cancel")]
    ]
    await update.message.reply_text(
        f"⚠️ Are you sure you want to restart the {label}?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def restart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    data = query.data

    if data == "rst:cancel":
        await query.edit_message_text("Restart canceled ❌")
        return

    if data.startswith("rst1:"):
        target = data.split(":")[1]
        label = "bot service" if target == "bot" else "SERVER"
        keyboard = [
            [InlineKeyboardButton(f"Yes, really ✅", callback_data=f"rst2:{target}")],
            [InlineKeyboardButton("No ❌", callback_data="rst:cancel")]
        ]
        await query.edit_message_text(
            f"⚠️ Are you REALLY sure you want to restart the {label}?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if data.startswith("rst2:"):
        target = data.split(":")[1]
        if target == "server":
            await query.edit_message_text("🔄 Rebooting server...")
            subprocess.Popen(["sudo", "reboot"])
        else:
            await query.edit_message_text("🔄 Restarting bot service...")
            subprocess.Popen(["sudo", "systemctl", "restart", "mediaman.service"])

def main():
    request = HTTPXRequest(connection_pool_size=8, read_timeout=30, write_timeout=30, connect_timeout=15, http_version="1.1")
    app = ApplicationBuilder().token(TOKEN).request(request).build()

    app.add_handler(CommandHandler("start",              start))
    app.add_handler(CommandHandler("request",            request_media))
    app.add_handler(CommandHandler("my_requests",        my_requests))
    app.add_handler(CommandHandler("delete_request",     delete_request))
    app.add_handler(CommandHandler("trending",           trending))
    app.add_handler(CommandHandler("help",               help_command))
    app.add_handler(CommandHandler("all_requests",       all_requests))
    app.add_handler(CommandHandler("clear_requests",     clear_requests))
    app.add_handler(CommandHandler("download",           download_media))
    app.add_handler(CommandHandler("download_requests",  download_requests))
    app.add_handler(CommandHandler("requests_stats",      requests_stats))
    app.add_handler(CommandHandler("activity",            activity_log))
    app.add_handler(CommandHandler("debugplex",           debug_plex))
    app.add_handler(CommandHandler("restart",             restart_bot))
    app.add_handler(CommandHandler("stream",              stream_episode))
    app.add_handler(CallbackQueryHandler(stream_season_callback,  pattern="^strs:"))
    app.add_handler(CallbackQueryHandler(stream_episode_callback, pattern="^strep:"))
    app.add_handler(CallbackQueryHandler(restart_callback, pattern="^rst"))

    app.add_handler(CallbackQueryHandler(clear_callback,             pattern="^clear:"))
    app.add_handler(CallbackQueryHandler(delete_callback,            pattern="^del:"))
    app.add_handler(CallbackQueryHandler(toggle_callback,            pattern="^tog:"))
    app.add_handler(CallbackQueryHandler(download_selected_callback, pattern="^dlsel:"))
    app.add_handler(CallbackQueryHandler(queue_movie_callback,       pattern="^qmov:"))
    app.add_handler(CallbackQueryHandler(queue_quality_callback,     pattern="^qqdl:"))
    app.add_handler(CallbackQueryHandler(yts_movie_callback,         pattern="^yts:"))
    app.add_handler(CallbackQueryHandler(yts_quality_callback,       pattern="^ytsdl:"))
    app.add_handler(CallbackQueryHandler(button_callback))

    app.run_polling(timeout=30)

if __name__ == "__main__":
    main()