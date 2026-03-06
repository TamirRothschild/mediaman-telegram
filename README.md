# Telegram Media Manger Bot 🎬

A smart Telegram bot that allows users to search and request movies directly from the chat. The bot interfaces with the TMDb API to provide accurate results, manages a request list, and includes a built-in authorization system for administrators.

## Key Features ✨
* **Smart Search:** Find movies by title using the TMDb API.
* **User-Friendly Interface:** Displays search results using interactive buttons (Inline Keyboard) to prevent errors.
* **Personal Request Management:** Each user can only view the status of their own requests.
* **Admin Panel:** Dedicated commands for the administrator to view all requests and manage the system.
* **Status Tracking:** Supports various request states (`pending`, `approved`, `done`).

## Prerequisites 📋
* Python 3.8 or higher
* Telegram Bot Token from BotFather
* TMDb API Key

## Installation and Setup 🚀

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/TamirRothschild/telegram-movie-request-bot.git](https://github.com/TamirRothschild/telegram-movie-request-bot.git)
   cd telegram-movie-request-bot
   ```

2. **Install required libraries:**
   ```bash
   pip install python-telegram-bot requests
   ```

3. **Configuration:**
   * Open the main code file.
   * Update the `API_KEY` (for TMDb) and the Telegram Bot Token variables.
   * Set `ADMIN_ID` to the numerical Telegram ID of the bot administrator.
   * Ensure a valid `requests.json` file exists with an initial empty array: `[]`.

4. **Run the bot from the terminal:**
   ```bash
   python bot.py
   ```
   *(For production environments, it is highly recommended to configure the bot as a `systemd` service so it runs continuously in the background).*

## Available Commands 💬

### Standard User Commands:
* `/request <movie name>` - Start the process of searching and requesting a new movie.
* `/my_requests` - View the user's personal list of requests and their statuses.

### Admin Commands:
* `/list_all` - Display all open and closed requests in the system from all users.

## Roadmap & Future Improvements 🗺️
* Migrate the database from JSON to SQLite to better handle a large number of users.
* Integrate with Plex API (or Radarr) to automatically fetch approved content.
* Incorporate a built-in Logging module to document activity and errors.
* Add a "Cancel Request" button for users.