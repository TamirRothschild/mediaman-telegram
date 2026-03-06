## הסבר של כל שלב וכיצד לממש אותו

---

### 1. קבלת בקשה מהמשתמש
* **מה קורה:** המשתמש שולח הודעה לבוט עם הפקודה `/request <movie name>`.
* **איך לממש ב-Python:**
```python
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext

def request_movie(update: Update, context: CallbackContext):
    movie_name = ' '.join(context.args)
    # המשך לשלב החיפוש
```

### 2. חיפוש הסרט ב-API חיצוני
* **מה קורה:** הבוט שולח בקשה ל-OMDb או IMDb API כדי לקבל רשימת סרטים עם השם, השנה והפוסטר שלהם.
* **איך לממש:**
```python
import requests

API_KEY = "your_omdb_key"
url = f"[http://www.omdbapi.com/?apikey=](http://www.omdbapi.com/?apikey=){API_KEY}&s={movie_name}"
response = requests.get(url).json()
movies = response.get('Search', [])
```

### 3. הצגת אפשרויות לבחירה (Inline Keyboard)
* **מה קורה:** הבוט מציג למשתמש רשימה של סרטים באמצעות כפתורים אינטראקטיביים לבחירה.
* **איך לממש:**
```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

keyboard = [
    [InlineKeyboardButton(f"{m['Title']} ({m['Year']})", callback_data=m['imdbID'])]
    for m in movies
]
reply_markup = InlineKeyboardMarkup(keyboard)
update.message.reply_text('בחר סרט:', reply_markup=reply_markup)
```

### 4. המשתמש בוחר סרט
* **מה קורה:** המשתמש לוחץ על כפתור → הבוט מקבל `callback_query` המכיל את ה-`imdbID`.
* **איך לממש:**
```python
def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    selected_id = query.data
    # שמירה ברשימת הבקשות
```

### 5. שמירת הבקשה ברשימת הבקשות
* **מה קורה:** הבוט שומר את הבחירה בקובץ JSON או במסד נתונים SQLite, יחד עם שם המשתמש, התאריך והסטטוס.
* **איך לממש:**
```python
import json, datetime

new_request = {
    "user": update.effective_user.username,
    "title": movie_title, # בהנחה שמשתנים אלו נשלפו בהתבסס על ה-selected_id
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

### 6. שליחת הודעת אישור למשתמש
* **מה קורה:** הבוט שולח הודעה למשתמש: "הבקשה נשמרה בהצלחה!".
* **איך לממש:**
```python
query.edit_message_text(f"בקשתך עבור {movie_title} נשמרה בהצלחה!")
```

### 7. ניהול הרשימה עבור משתמש רגיל
* **מה קורה:** משתמש רגיל יכול לראות רק את הבקשות שלו.
* **איך לממש:**
```python
def my_requests(update: Update, context: CallbackContext):
    user = update.effective_user.username
    with open("requests.json") as f:
        data = json.load(f)
    user_requests = [r for r in data if r["user"] == user]
    msg = "\n".join([f"{r['title']} ({r['year']}) - {r['status']}" for r in user_requests])
    update.message.reply_text(msg or "לא נמצאו בקשות.")
```

### 8. פקודות אדמין
* **מה קורה:** מנהל (אתה) יכול לראות את כל הבקשות, לנקות את הרשימה או לעדכן סטטוס.
* **איך לממש:**
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

### 9. טיפול במצב "המתנה" (Pending)
* ניתן להקצות סטטוס לכל בקשה:
    * `pending` – ממתין לבחירה או טיפול.
    * `approved` – הבקשה אושרה.
    * `done` – הסרט נוסף לשרת.
* זה מאפשר למשתמשים לראות רק את הבקשות הפתוחות שלהם ומאפשר לאדמין לנהל את כולן ביעילות.

### 10. הרצת הבוט על שרת
* מומלץ מאוד להריץ את הבוט כשירות `systemd` ב-Debian:
    * זה מבטיח שהבוט יישאר פעיל גם לאחר הפעלה מחדש של השרת.
* ניתן להשתמש ב-`python-telegram-bot` עם שיטת long polling.

---

### 💡 טיפים לפיתוח והרחבה
1. **הוספת תיעוד (Logging):** מעקב אחר מי ביקש איזה סרט ומתי.
2. **שילוב עם Plex API:** אוטומציה של הוספת סרטים שאושרו.
3. **שימוש ב-SQLite במקום JSON:** ביצועים ואמינות טובים יותר עבור מספר רב של משתמשים.
4. **אבטחה:** הבטחה שמשתמשים רגילים לא יוכלו למחוק או לשנות בקשות של משתמשים אחרים.