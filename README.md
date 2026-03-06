# Telegram Media Manager Bot 🎬

A smart Telegram bot that allows users to search and request movies directly from chat. The bot uses the TMDb API to provide accurate search results, manages personal request lists, and includes administrator commands to manage the system.

## Key Features ✨
* **Smart Movie Search:** Search movies by title using the TMDb API.  
* **Inline Keyboard Interface:** Users select movies from interactive buttons to prevent mistakes.  
* **Personal Request Tracking:** Each user can view only their own requests.  
* **Admin Commands:** Administrators can view all requests, clear requests, and manage the system.  
* **Poster Support:** Sends movie posters when available for better visual feedback.  

## Prerequisites 📋
* Python 3.8 or higher  
* Telegram Bot Token from BotFather  
* TMDb API Key  

## Installation & Setup 🚀

1. **Clone the repository:**
```bash
git clone https://github.com/TamirRothschild/telegram-movie-request-bot.git
cd telegram-movie-request-bot
```

2. **Install required Python libraries:**
```python 
pip install python-telegram-bot requests python-dotenv
```

3.	**Configure environment variables:**
Create a .env file in the project root with the following:
```env
TELEGRAM_TOKEN=your_bot_token_here
ADMIN_IDS=123456789   # comma-separated list if multiple admins
TMDB_API_KEY=your_tmdb_api_key_here
```

4.	**Optional: Create an empty JSON storage file for requests:**
```bash
mkdir -p data
echo "{}" > data/requests.json
```
5.	**Run the bot:**
```bash
python bot.py
```
##### For production, consider running the bot as a systemd service to keep it running in the background.

## Available Commands 💬

### Standard User Commands:
   * /request <movie name> - Search and request a new movie.
   *	/my_requests - View your own requests and their statuses.

### Admin Commands:
   *	/all_requests - View all requests from all users.
   *	/clear_requests - Clear all stored requests.

### Future Improvements 🗺️
   *	Migrate storage from JSON to SQLite for better performance with many users.
   *	Integrate with Plex or Radarr to automatically fetch approved movies.
   * 	Add logging for activity and errors.
   *	Add user “Cancel Request” functionality.
