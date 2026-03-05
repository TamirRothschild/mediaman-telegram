## Explanation of Each Step and How to Implement It

---

### 1. Receiving a Request from the User
* **What happens:** The user sends a message to the bot with the command `/request <movie name>`.
* **How to implement in Python:**
```python
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext

def request_movie(update: Update, context: CallbackContext):
    movie_name = ' '.join(context.args)
    # Proceed to the search step
```

### 2. Searching for the Movie in an External API
* **What happens:** The bot sends a request to the OMDb or IMDb API to get a list of movies with their title, year, and poster.
* **How to implement:**
```python
import requests

API_KEY = "your_omdb_key"
url = f"[http://www.omdbapi.com/?apikey=](http://www.omdbapi.com/?apikey=){API_KEY}&s={movie_name}"
response = requests.get(url).json()
movies = response.get('Search', [])
```

### 3. Displaying Options for Selection (Inline Keyboard)
* **What happens:** The bot presents the user with a list of movies using interactive buttons for selection.
* **How to implement:**
```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

keyboard = [
    [InlineKeyboardButton(f"{m['Title']} ({m['Year']})", callback_data=m['imdbID'])]
    for m in movies
]
reply_markup = InlineKeyboardMarkup(keyboard)
update.message.reply_text('Select a movie:', reply_markup=reply_markup)
```

### 4. The User Selects a Movie
* **What happens:** The user clicks a button → the bot receives a `callback_query` containing the `imdbID`.
* **How to implement:**
```python
def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    selected_id = query.data
    # Save to the requests list
```

### 5. Saving the Request to the Requests List
* **What happens:** The bot saves the selection in a JSON file or an SQLite database, along with the username, date, and status.
* **How to implement:**
```python
import json, datetime

new_request = {
    "user": update.effective_user.username,
    "title": movie_title, # Assuming these variables were fetched based on the selected_id
    "year": movie_year,
    "status": "pending",
    "requested_at": datetime.datetime.now().isoformat()
}

with open("requests.json", "r+") as f:
    data = json.load(f)
    data.append(new_request)
    f.seek(0)
    json.dump(data, f, indent=4)
```

### 6. Sending a Confirmation Message to the User
* **What happens:** The bot sends a message to the user: "The request was saved successfully!".
* **How to implement:**
```python
query.edit_message_text(f"Your request for {movie_title} has been saved!")
```

### 7. List Management for a Regular User
* **What happens:** A regular user can only view their own requests.
* **How to implement:**
```python
def my_requests(update: Update, context: CallbackContext):
    user = update.effective_user.username
    with open("requests.json") as f:
        data = json.load(f)
    user_requests = [r for r in data if r["user"] == user]
    msg = "\n".join([f"{r['title']} ({r['year']}) - {r['status']}" for r in user_requests])
    update.message.reply_text(msg or "No requests found.")
```

### 8. Admin Commands
* **What happens:** An admin (you) can see all requests, clear the list, or update a status.
* **How to implement:**
```python
ADMIN_ID = 123456789

def list_all(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return
    with open("requests.json") as f:
        data = json.load(f)
    msg = "\n".join([f"{r['user']}: {r['title']} ({r['year']})" for r in data])
    update.message.reply_text(msg)
```

### 9. Handling the "Pending" State
* You can assign a status to each request:
    * `pending` – waiting for selection or handling.
    * `approved` – the request was approved.
    * `done` – the movie was added to the server.
* This allows users to see only their open requests and enables the admin to manage all of them efficiently.

### 10. Running the Bot on a Server
* It is highly recommended to run the bot as a `systemd` service on Debian:
    * This ensures the bot remains active even after a server reboot.
* You can utilize `python-telegram-bot` with long polling.

---

### 💡 Tips for Development and Expansion
1.  **Adding logging:** Track who requested which movie and when.
2.  **Integration with Plex API:** Automate the addition of approved movies.
3.  **Using SQLite instead of JSON:** Better performance and reliability for a large number of users.
4.  **Security:** Ensure regular users cannot delete or modify other users' requests.