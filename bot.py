import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from modules.tmdb import search_movie
from modules.storage import add_request

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

# /request command
def request_movie(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Please provide a movie name after the /request command")
        return

    movie_name = ' '.join(context.args)

    # Search TMDb
    results = search_movie(movie_name)
    if not results:
        update.message.reply_text(f"No results found for '{movie_name}'")
        return

    # Save last search in user_data for callback
    context.user_data["last_search"] = results
    
    # Build InlineKeyboard with movie options
    keyboard = [
        [InlineKeyboardButton(f"{m['title']} ({m['year']})", callback_data=str(m['id']))] 
        for m in results[:5]  # limit to first 5 results
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Select the correct movie:", reply_markup=reply_markup)

def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    movie_id = query.data
    movie_title = None
    movie_year = None

    # Find the movie info from last search results
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
    query = update.callback_query
    query.answer()
    movie_id = query.data
    movie_title = None
    movie_year = None

    # Find the movie info from last search results (could be improved with session tracking)
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
    query = update.callback_query
    query.answer()
    movie_id = query.data
    query.edit_message_text(f"You selected movie ID: {movie_id}\nSaved to requests!")
    # TODO: save movie selection to JSON / SQLite for this user

def main():
    updater = Updater(TOKEN)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("request", request_movie))
    dp.add_handler(CallbackQueryHandler(button_callback))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()