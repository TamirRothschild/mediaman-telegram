import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from modules.tmdb import search_movie
from modules.storage import add_request, get_all_requests, clear_all_requests, get_user_requests

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

# --------- Admin helper ----------
def is_admin(user_id):
    return user_id in ADMIN_IDS

# --------- /request command ----------
def request_movie(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Please provide a movie name after the /request command")
        return

    movie_name = ' '.join(context.args)
    results = search_movie(movie_name)  # <-- call module function

    if not results:
        update.message.reply_text(f"No results found for '{movie_name}'")
        return

    # Save last search in user_data for callback
    context.user_data["last_search"] = results

    # Build InlineKeyboard for top 5 results
    keyboard = [
        [InlineKeyboardButton(f"{m['title']} ({m['year']})", callback_data=str(m['id']))] 
        for m in results[:5]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Select the correct movie:", reply_markup=reply_markup)
    if not context.args:
        update.message.reply_text("Please provide a movie name after the /request command")
        return

    movie_name = ' '.join(context.args)
    results = search_movie(movie_name)
    if not results:
        update.message.reply_text(f"No results found for '{movie_name}'")
        return

    # Save last search in user_data for callback
    context.user_data["last_search"] = results

    # Build InlineKeyboard
    keyboard = [
        [InlineKeyboardButton(f"{m['title']} ({m['year']})", callback_data=str(m['id']))] 
        for m in results[:5]  # first 5 results
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Select the correct movie:", reply_markup=reply_markup)
    url = f"{BASE_URL}/search/movie"
    params = {
        "api_key": TMDB_API_KEY,
        "query": query,
        "include_adult": False,
        "language": "en-US",
    }
    resp = requests.get(url, params=params).json()
    results = []
    for m in resp.get("results", []):
        results.append({
            "id": m["id"],
            "title": m["title"],
            "year": m.get("release_date", "")[:4] if m.get("release_date") else "",
            "poster_path": m.get("poster_path")  # <-- new field
        })
    return results

# --------- Callback for movie selection ----------
def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    movie_id = query.data
    movie_title = None
    movie_year = None
    poster_path = None

    # Find selected movie in last search
    for m in context.user_data.get("last_search", []):
        if str(m["id"]) == movie_id:
            movie_title = m["title"]
            movie_year = m["year"]
            poster_path = m.get("poster_path")
            break

    if movie_title:
        # Save request
        add_request(query.from_user.id, {"id": movie_id, "title": movie_title, "year": movie_year})

        # Send poster with caption if available
        if poster_path:
            poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
            query.message.reply_photo(photo=poster_url,
                                      caption=f"You selected: {movie_title} ({movie_year})\nSaved to your requests!")
            query.edit_message_text("Poster sent!")  # optional update of inline message
        else:
            query.edit_message_text(f"You selected: {movie_title} ({movie_year})\nSaved to your requests!")
    else:
        query.edit_message_text("Error: movie not found in your search results.")
    query = update.callback_query
    query.answer()
    movie_id = query.data
    movie_title = None
    movie_year = None

    # Find selected movie in last search
    for m in context.user_data.get("last_search", []):
        if str(m["id"]) == movie_id:
            movie_title = m["title"]
            movie_year = m["year"]
            break

    if movie_title:
        # Save request to JSON
        add_request(query.from_user.id, {"id": movie_id, "title": movie_title, "year": movie_year})
        query.edit_message_text(f"You selected: {movie_title} ({movie_year})\nSaved to your requests!")
    else:
        query.edit_message_text("Error: movie not found in your search results.")

# --------- Admin Commands ----------
def all_requests(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("You are not authorized to use this command.")
        return

    requests = get_all_requests()
    if not requests:
        update.message.reply_text("No requests found.")
        return

    text = ""
    for user_id, movies in requests.items():
        text += f"User {user_id}:\n"
        for m in movies:
            text += f" - {m['title']} ({m['year']})\n"
    update.message.reply_text(text or "No requests found.")

def clear_requests(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("You are not authorized to use this command.")
        return

    clear_all_requests()
    update.message.reply_text("All requests have been cleared.")

def my_requests(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    movies = get_user_requests(user_id)
    if not movies:
        update.message.reply_text("You have no requests.")
        return

    text = "Your requests:\n"
    for m in movies:
        text += f" - {m['title']} ({m['year']})\n"
    update.message.reply_text(text)

# --------- Main function ----------
def main():
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    # User commands
    dp.add_handler(CommandHandler("request", request_movie))
    dp.add_handler(CommandHandler("my_requests", my_requests))

    # Admin commands
    dp.add_handler(CommandHandler("all_requests", all_requests))
    dp.add_handler(CommandHandler("clear_requests", clear_requests))

    # Callback handler for inline buttons
    dp.add_handler(CallbackQueryHandler(button_callback))

    # Start bot
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()