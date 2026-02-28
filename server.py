from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import secrets

app = Flask(__name__)
CORS(app, origins=["http://127.0.0.1:5500", "http://localhost:5500"], supports_credentials=True)

import os
from dotenv import load_dotenv
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")


# ========== DATABASE ==========
def init_db():
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS tokens (
        token TEXT PRIMARY KEY,
        user_id INTEGER,
        username TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        user_id INTEGER,
        title TEXT,
        created_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        sender TEXT,
        text TEXT,
        time TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

def get_user_from_token(req):
    token = req.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        return None
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("SELECT user_id, username FROM tokens WHERE token = ?", (token,))
    row = c.fetchone()
    conn.close()
    if row:
        return { "user_id": row[0], "username": row[1] }
    return None

# ========== CRYPTO DATA ==========
def get_crypto_price(coin_id):
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true&include_market_cap=true"
        headers = { "x-cg-demo-api-key": COINGECKO_API_KEY }
        res = requests.get(url, headers=headers)
        data = res.json()
        if coin_id in data:
            price = data[coin_id]["usd"]
            change = data[coin_id].get("usd_24h_change", 0)
            market_cap = data[coin_id].get("usd_market_cap", 0)
            return f"${price:,.2f} USD | 24h change: {change:.2f}% | Market cap: ${market_cap:,.0f}"
        return None
    except:
        return None

def get_crypto_news():
    try:
        import xml.etree.ElementTree as ET
        url = "https://feeds.feedburner.com/CoinDesk"
        res = requests.get(url, timeout=5)
        print("NEWS STATUS:", res.status_code)
        root = ET.fromstring(res.content)
        items = root.findall(".//item")[:5]
        if not items:
            return None
        news_text = ""
        for item in items:
            title = item.find("title")
            if title is not None:
                news_text += f"- {title.text}\n"
        return news_text
    except Exception as e:
        print("NEWS ERROR:", e)
        return None

def get_top_cryptos():
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=10&page=1"
        headers = { "x-cg-demo-api-key": COINGECKO_API_KEY }
        res = requests.get(url, headers=headers)
        data = res.json()
        result = ""
        for coin in data:
            result += f"- {coin['name']} ({coin['symbol'].upper()}): ${coin['current_price']:,.2f} | 24h: {coin['price_change_percentage_24h']:.2f}%\n"
        return result
    except:
        return None

# ========== SMART CONTEXT BUILDER ==========
def build_crypto_context(user_message):
    msg = user_message.lower()
    context = ""

    coin_map = {
        "bitcoin": "bitcoin", "btc": "bitcoin",
        "ethereum": "ethereum", "eth": "ethereum",
        "solana": "solana", "sol": "solana",
        "bnb": "binancecoin", "binance": "binancecoin",
        "xrp": "ripple", "ripple": "ripple",
        "cardano": "cardano", "ada": "cardano",
        "dogecoin": "dogecoin", "doge": "dogecoin",
        "polygon": "matic-network", "matic": "matic-network",
        "avalanche": "avalanche-2", "avax": "avalanche-2",
        "chainlink": "chainlink", "link": "chainlink",
        "litecoin": "litecoin", "ltc": "litecoin",
        "polkadot": "polkadot", "dot": "polkadot",
        "shiba": "shiba-inu", "shib": "shiba-inu",
        "tron": "tron", "trx": "tron",
        "pepe": "pepe", "toncoin": "the-open-network", "ton": "the-open-network"
    }

    for keyword, coin_id in coin_map.items():
        if keyword in msg:
            price_data = get_crypto_price(coin_id)
            print(f"PRICE DATA for {keyword}:", price_data)
            if price_data:
                context += f"\n[Live {keyword.upper()} data: {price_data}]"
            break

    if any(word in msg for word in ["news", "latest", "update", "happening", "today"]):
        news = get_crypto_news()
        print("NEWS DATA:", news)
        if news:
            context += f"\n[Latest crypto news:\n{news}]"

    if any(word in msg for word in ["top", "best", "market", "ranking", "list"]):
        top = get_top_cryptos()
        print("TOP CRYPTOS:", top)
        if top:
            context += f"\n[Top 10 cryptos by market cap:\n{top}]"

    print("FINAL CONTEXT:", context)
    
    return context

# ========== AUTH ==========
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({ "error": "Username and password required" }), 400

    hashed = generate_password_hash(password)

    try:
        conn = sqlite3.connect("chat_history.db")
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed))
        conn.commit()
        conn.close()
        return jsonify({ "success": True })
    except sqlite3.IntegrityError:
        return jsonify({ "error": "Username already taken" }), 400

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("SELECT id, password FROM users WHERE username = ?", (username,))
    user = c.fetchone()

    if not user or not check_password_hash(user[1], password):
        conn.close()
        return jsonify({ "error": "Invalid username or password" }), 401

    token = secrets.token_hex(32)
    c.execute("INSERT INTO tokens (token, user_id, username) VALUES (?, ?, ?)", (token, user[0], username))
    conn.commit()
    conn.close()

    return jsonify({ "success": True, "token": token, "username": username })

@app.route("/logout", methods=["POST"])
def logout():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("DELETE FROM tokens WHERE token = ?", (token,))
    conn.commit()
    conn.close()
    return jsonify({ "success": True })

@app.route("/me", methods=["GET"])
def me():
    user = get_user_from_token(request)
    if not user:
        return jsonify({ "error": "Not logged in" }), 401
    return jsonify({ "user_id": user["user_id"], "username": user["username"] })

# ========== CHAT ==========
@app.route("/chat", methods=["POST"])
def chat():
    user = get_user_from_token(request)
    if not user:
        return jsonify({ "error": "Not logged in" }), 401

    data = request.get_json()
    messages = data.get("messages", [])
    session_id = data.get("session_id")
    user_message = data.get("user_message")
    session_title = data.get("session_title", "New Chat")

    # Build live crypto context
    crypto_context = build_crypto_context(user_message)

    # Inject context into the last user message if we have live data
    enriched_messages = messages.copy()
    if crypto_context and enriched_messages:
        enriched_messages[-1] = {
            "role": "user",
            "content": enriched_messages[-1]["content"] + crypto_context
        }

    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO sessions (id, user_id, title, created_at) VALUES (?, ?, ?, ?)",
              (session_id, user["user_id"], session_title, datetime.now().isoformat()))

    time_now = datetime.now().strftime("%I:%M %p")
    c.execute("INSERT INTO messages (session_id, sender, text, time) VALUES (?, ?, ?, ?)",
              (session_id, "user", user_message, time_now))
    conn.commit()

    # System prompt specialized for crypto
    system_message = {
        "role": "system",
        "content": """You are Annon AI, a specialized cryptocurrency and finance assistant. 
        You have access to live crypto market data and news which will be provided in the user's message as context in square brackets.
        Always use this live data when answering questions about prices, market trends, and news.
        Be concise, accurate, and helpful. When discussing prices always mention they are live data.
        Never make up prices or market data — only use what's provided to you.
        You can also help with general crypto education, DeFi, NFTs, blockchain technology, and investment strategies."""
    }

    final_messages = [system_message] + enriched_messages[1:]  # Skip old system message

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}"
        },
        json={ "model": "llama-3.3-70b-versatile", "messages": final_messages }
    )

    print("GROQ RESPONSE:", response.status_code, response.text)
    reply = response.json()["choices"][0]["message"]["content"]

    c.execute("INSERT INTO messages (session_id, sender, text, time) VALUES (?, ?, ?, ?)",
              (session_id, "bot", reply, time_now))
    c.execute("UPDATE sessions SET title = ? WHERE id = ?", (session_title, session_id))
    conn.commit()
    conn.close()

    return jsonify({ "reply": reply, "time": time_now })

# ========== SESSIONS ==========
@app.route("/sessions", methods=["GET"])
def get_sessions():
    user = get_user_from_token(request)
    if not user:
        return jsonify({ "error": "Not logged in" }), 401

    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("SELECT id, title, created_at FROM sessions WHERE user_id = ? ORDER BY created_at DESC", (user["user_id"],))
    rows = c.fetchall()
    conn.close()
    return jsonify([{ "id": r[0], "title": r[1], "created_at": r[2] } for r in rows])

@app.route("/sessions/<session_id>", methods=["GET"])
def get_session_messages(session_id):
    user = get_user_from_token(request)
    if not user:
        return jsonify({ "error": "Not logged in" }), 401

    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("SELECT sender, text, time FROM messages WHERE session_id = ? ORDER BY id", (session_id,))
    rows = c.fetchall()
    conn.close()
    return jsonify([{ "sender": r[0], "text": r[1], "time": r[2] } for r in rows])

@app.route("/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    user = get_user_from_token(request)
    if not user:
        return jsonify({ "error": "Not logged in" }), 401

    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("DELETE FROM sessions WHERE id = ? AND user_id = ?", (session_id, user["user_id"]))
    c.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()
    return jsonify({ "success": True })

if __name__ == "__main__":
    app.run(debug=True)
