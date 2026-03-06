import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from modules.tmdb import search_movie
from modules.storage import add_request, get_all_requests, clear_all_requests, get_user_requests

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

# ---------- Admin Helper ----------
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# ---------- /request command ----------
async def request_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide a movie name after the /request command")
        return

    movie_name = ' '.join(context.args)
    results = search_movie(movie_name)

    if not results:
        await update.message.reply_text(f"No results found for '{movie_name}'")
        return

    context.user_data["last_search"] = results

    keyboard = [
        [InlineKeyboardButton(f"{m['title']} ({m['year']})", callback_data=str(m['id']))]
        for m in results[:5]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select the correct movie:", reply_markup=reply_markup)

# ---------- Callback for movie selection ----------
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    movie_id = query.data
    movie_title = None
    movie_year = None
    poster_path = None

    # Find movie in last search
    for m in context.user_data.get("last_search", []):
        if str(m["id"]) == movie_id:
            movie_title = m["title"]
            movie_year = m["year"]
            poster_path = m.get("poster_path")
            break

    if movie_title:
        # Save request
        add_request(query.from_user.id, {"id": movie_id, "title": movie_title, "year": movie_year})

        # Send poster if available
        if poster_path:
            poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
            await query.message.reply_photo(
                photo=poster_url,
                caption=f"You selected: {movie_title} ({movie_year})\nSaved to your requests!"
            )
        else:
            await query.edit_message_text(f"You selected: {movie_title} ({movie_year})\nSaved to your requests!")
    else:
        await query.edit_message_text("Error: movie not found in your search results.")

# ---------- User Commands ----------
async def my_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    movies = get_user_requests(user_id)
    if not movies:
        await update.message.reply_text("You have no requests.")
        return
    text = "Your requests:\n" + "\n".join([f" - {m['title']} ({m['year']})" for m in movies])
    await update.message.reply_text(text)

# ---------- Admin Commands ----------
async def all_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return

    requests = get_all_requests()
    if not requests:
        await update.message.reply_text("No requests found.")
        return

    text = ""
    for user_id, movies in requests.items():
        text += f"User {user_id}:\n"
        for m in movies:
            text += f" - {m['title']} ({m['year']})\n"
    await update.message.reply_text(text)

async def clear_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return
    clear_all_requests()
    await update.message.reply_text("All requests have been cleared.")

# ---------- Help Command ----------
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
Available Commands:
/request <movie name> - Search and request a new movie
/my_requests - Show your requests

Admin Commands:
/all_requests - Show all requests from all users
/clear_requests - Clear all requests
"""
    await update.message.reply_text(help_text)

# ---------- Main ----------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # User commands
    app.add_handler(CommandHandler("request", request_movie))
    app.add_handler(CommandHandler("my_requests", my_requests))
    app.add_handler(CommandHandler("help", help_command))

    # Admin commands
    app.add_handler(CommandHandler("all_requests", all_requests))
    app.add_handler(CommandHandler("clear_requests", clear_requests))

    # Callback buttons
    app.add_handler(CallbackQueryHandler(button_callback))

    # Run the bot
    app.run_polling()

if __name__ == "__main__":
    main()