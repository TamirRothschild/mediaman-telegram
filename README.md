# MediaMan Telegram Bot 🎬

A Telegram bot for managing movie and series requests, with YTS search and direct Transmission integration.

---

## Features ✨

- 🔍 **Smart Search** — Search movies and TV shows via TMDb API
- 📋 **Request Management** — Users submit requests, admin handles them
- ⬇️ **YTS Integration** — Search and download torrents via YTS API
- 🔗 **Transmission Integration** — Add torrents directly to Transmission
- 📈 **Trending** — Browse trending movies and TV shows from TMDb
- 🗃️ **SQLite Storage** — Reliable database with full activity logging
- 🖼️ **Poster Support** — Movie posters shown throughout the UI

---

## Project Structure

```
mediaman-bot/
├── bot.py                  ← Main bot file
├── requirements.txt        ← Python dependencies
├── .env                    ← Environment variables (never commit this)
├── .env.example            ← Template for environment variables
├── .gitignore
├── data/
│   ├── mediaman.db         ← SQLite database (auto-created)
│   └── mediaman.log        ← Activity log (auto-created)
└── modules/
    ├── tmdb.py             ← TMDb API (search, details, trending)
    ├── yts.py              ← YTS API (search, magnet links)
    └── storage.py          ← SQLite storage + activity log
```

---

## Setup & Installation 🚀

### 1. Clone the repository

```bash
git clone https://github.com/your-username/mediaman-bot.git
cd mediaman-bot
```

### 2. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
TELEGRAM_TOKEN=your_bot_token_here
ADMIN_IDS=123456789
TMDB_API_KEY=your_tmdb_key_here
TRANSMISSION_HOST=127.0.0.1:9091
TRANSMISSION_USER=your_transmission_user
TRANSMISSION_PASS=your_transmission_password
```

| Variable | Description | Where to get it |
|---|---|---|
| `TELEGRAM_TOKEN` | Bot token | [@BotFather](https://t.me/BotFather) |
| `ADMIN_IDS` | Comma-separated Telegram user IDs | [@userinfobot](https://t.me/userinfobot) |
| `TMDB_API_KEY` | TMDb API key | [themoviedb.org](https://www.themoviedb.org/settings/api) |
| `TRANSMISSION_HOST` | Transmission RPC address | Your Transmission settings |
| `TRANSMISSION_USER` | Transmission RPC username | Your Transmission settings |
| `TRANSMISSION_PASS` | Transmission RPC password | Your Transmission settings |

### 5. Configure Transmission for remote access

If the bot runs on a different machine than Transmission, edit `/etc/transmission-daemon/settings.json`:

```json
"rpc-whitelist-enabled": false,
"rpc-bind-address": "0.0.0.0"
```

Then restart:
```bash
sudo systemctl restart transmission-daemon
```

### 6. Run the bot

```bash
python3 bot.py
```

---

## Running as a systemd Service (Linux)

Create `/etc/systemd/system/mediaman.service`:

```ini
[Unit]
Description=MediaMan Telegram Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_username/mediaman-bot
ExecStart=/home/your_username/mediaman-bot/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable mediaman.service
sudo systemctl start mediaman.service
sudo systemctl status mediaman.service
```

---

## Commands 💬

### User Commands
| Command | Description |
|---|---|
| `/request <name>` | Search and request a movie or series |
| `/my_requests` | View your submitted requests |
| `/delete_request` | Delete one of your requests |
| `/trending` | Browse trending movies and TV shows |
| `/help` | Show all available commands |

### Admin Commands
| Command | Description |
|---|---|
| `/all_requests` | View all requests from all users |
| `/download_requests` | Multi-select requests and download via YTS |
| `/download <name>` | Search YTS directly and download |
| `/clear_requests` | Clear all requests (double confirmation) |
| `/activity` | View recent activity log |

---

## Download Flow

```
/download_requests
       ↓
Select requests (⬜/✅ toggle)
       ↓
⬇️ Download Selected
       ↓
For each selected movie:
  → Search YTS → Select correct match → Select quality
       ↓
✅ Added to Transmission
```

---

## Future Improvements 🗺️

- `/status` — Show active Transmission downloads with progress
- Notify users when their requested movie has been added
- Rate limiting — limit requests per user
- `/delete_download` — Remove a torrent from Transmission via bot