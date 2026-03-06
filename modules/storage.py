import os
import json

# Path to JSON file for storing requests
DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "requests.json")

def load_requests():
    """Load all requests from JSON file"""
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_requests(requests):
    """Save all requests to JSON file"""
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(requests, f, indent=2)

def add_request(user_id, movie):
    """
    Add a movie request for a specific user
    user_id: str or int
    movie: dict with keys 'id', 'title', 'year'
    """
    requests = load_requests()
    user_id = str(user_id)
    if user_id not in requests:
        requests[user_id] = []
    requests[user_id].append(movie)
    save_requests(requests)

def get_user_requests(user_id):
    """Return all requests for a specific user"""
    requests = load_requests()
    return requests.get(str(user_id), [])

def get_all_requests():
    """Return all requests (for admin)"""
    return load_requests()

def clear_all_requests():
    """Delete all requests (admin)"""
    save_requests({})