import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# Load environment variables from .env file
load_dotenv()

# Get Telegram token from environment variable
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Function to handle the /request command
def request_movie(update: Update, context: CallbackContext):
    # Check if user provided a movie name
    if not context.args:
        update.message.reply_text("Please provide a movie name after the /request command")
        return

    # Join all arguments to form the full movie name
    movie_name = ' '.join(context.args)

    # Reply to user acknowledging receipt of the request
    update.message.reply_text(f"Received your request: {movie_name}\nProceeding to search…")

    # TODO: Send movie_name to OMDb/IMDb API in the next step

def main():
    # Create the Updater and pass the bot token
    updater = Updater(TOKEN)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Register the /request command handler
    dp.add_handler(CommandHandler("request", request_movie))

    # Start polling Telegram for updates
    updater.start_polling()

    # Run the bot until you press Ctrl-C
    updater.idle()

if __name__ == "__main__":
    main()