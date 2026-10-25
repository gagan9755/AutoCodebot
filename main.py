import asyncio
import time
import re
import os
import json
import random
import string
from datetime import datetime, timedelta
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from flask import Flask
from threading import Thread

# --- 🌐 KEEP-ALIVE SERVER ---
app = Flask(__name__)
@app.route('/')
def home():
    return "🤖 Smart Affiliate Scraper is SECURE and RUNNING 24/7!"
def run_server():
    app.run(host='0.0.0.0', port=8080)
Thread(target=run_server).start()

# --- ⚙️ BOT CONFIGURATION ---
API_ID = 21601452
API_HASH = 'cc8257993f2553fec9f43bcd6b8f79c4'
BOT_TOKEN = '8848334437:AAE82vDGyudr7HkSwyT32jhNAYvmwQsCBaU' 
MASTER_ID = 8845438009  # Your Admin ID

master_bot = TelegramClient('affiliate_master', API_ID, API_HASH)

# Directories
if not os.path.exists('photos'):
    os.makedirs('photos')

ADMIN_DB_FILE = "admin_db.json"
USERS_DB_FILE = "users_db.json"
SESSIONS_FILE = "sessions.json"

# --- 📁 DATABASE FUNCTIONS ---
def load_json(filepath, default):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception: return default
    return default

def save_json(filepath, data):
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e: pass

# Load DBs
admin_db = load_json(ADMIN_DB_FILE, {"keys": {}, "users": {}})
users_db = load_json(USERS_DB_FILE, {})
sessions_db = load_json(SESSIONS_FILE, {})

def save_admin(): save_json(ADMIN_DB_FILE, admin_db)
def save_users(): save_json(USERS_DB_FILE, users_db)
def save_sessions(): save_json(SESSIONS_FILE, sessions_db)

# Init User
def init_user(user_id):
    uid = str(user_id)
    if uid not in users_db:
        users_db[uid] = {
            "apps": {}, 
            "photos": {"yono": None, "diwa": None},
            "sources": {}, 
            "destinations": {},
            "memory": {"date": "", "codes": {}},
            "is_running": False
        }
        save_users()

# Name Cleaner (Mbm Bet -> mbmbet)
def clean_app_name(name):
    return re.sub(r'[^a-zA-Z0-9]', '', name).lower()

user_states = {}
user_clients = {}

# --- 🔐 LICENSE LOGIC ---
def generate_key(days):
    key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    expiry = datetime.now() + timedelta(days=days)
    admin_db["keys"][key] = {"expires": expiry.isoformat(), "used_by": None}
    save_admin()
    return key

def check_sub(user_id):
    uid = str(user_id)
    if uid not in admin_db["users"]: return False
    return datetime.now() < datetime.fromisoformat(admin_db["users"][uid]["expires"])

def get_validity(user_id):
    if not check_sub(user_id): return "Expired"
    exp = datetime.fromisoformat(admin_db["users"][str(user_id)]["expires"])
    days = (exp - datetime.now()).days
    return f"{days} Days"

# --- 🧠 UI MENUS ---
def get_main_menu(uid):
    is_running = users_db[str(uid)].get("is_running", False)
    status = "🟢 STOP SCRAPER" if is_running else "🚀 START SCRAPER"
    cb_data = b"stop_bot" if is_running else b"start_bot"
    
    return [
        [Button.inline(status, cb_data)],
        [Button.inline("📱 App Manager", b"menu_apps"), Button.inline("🖼️ Photo Manager", b"menu_photos")],
        [Button.inline("📥 Sources Manager", b"menu_source"), Button.inline("📤 Dest Manager", b"menu_dest")],
        [Button.inline("📊 My Stats / Validity", b"my_stats")]
    ]

def get_app_menu():
    return [
        [Button.inline("➕ Add New App", b"app_add")],
        [Button.inline("✏️ Edit App Link/Name", b"app_edit")],
        [Button.inline("🗑️ Delete App", b"app_del"), Button.inline("📋 List All Apps", b"app_list")],
        [Button.inline("🔙 Back to Main", b"main_menu")]
    ]

def get_photo_menu():
    return [
        [Button.inline("🎰 Set YONO Photo", b"photo_set_yono"), Button.inline("👑 Set DIWA Photo", b"photo_set_diwa")],
        [Button.inline("🗑️ Remove YONO Photo", b"photo_rem_yono"), Button.inline("🗑️ Remove DIWA Photo", b"photo_rem_diwa")],
        [Button.inline("🔙 Back to Main", b"main_menu")]
    ]

async def get_dialogs_buttons(client, action_prefix):
    try:
        dialogs = await client.get_dialogs(limit=50)
        btns = []
        for d in dialogs:
            if d.is_channel or d.is_group:
                name = d.name[:20] if d.name else "Chat"
                btns.append([Button.inline(name, f"{action_prefix}_{d.id}".encode())])
        
        back_route = b"menu_source" if action_prefix == "setsrc" else b"menu_dest"
        btns.append([Button.inline("🔙 Back", back_route)])
        return btns
    except: return [[Button.inline("🔙 Back", b"main_menu")]]

# --- 🎯 SCRAPER ENGINE (Background Loop) ---
async def start_scraper_client(user_id):
    uid = str(user_id)
    session_str = sessions_db.get(uid)
    if not session_str: return
    
    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
    await client.connect()
    user_clients[uid] = client

    @client.on(events.NewMessage())
    async def scraper_handler(event):
        if not users_db[uid].get("is_running") or not check_sub(user_id): return
        if not users_db[uid]["sources"] or not users_db[uid]["destinations"]: return
        if str(event.chat_id) not in users_db[uid]["sources"]: return

        text = event.message.message or ""
        clean_msg = clean_app_name(text)
        
        detected_app_id = None
        for a_id in users_db[uid]["apps"]:
            if a_id in clean_msg:
                detected_app_id = a_id
                break
                
        if not detected_app_id: return # Koi app match nahi hui

        # Extract Code
        code = None
        if "mail box" in text.lower() or "mailbox" in text.lower():
            code = "Check Mail Box 🎁"
        else:
            match = re.search(r'(?i)code\s*[-:👉=>]+\s*([a-zA-Z0-9_]+)', text)
            if match: code = match.group(1)
            
        if not code: return # Code nahi mila

        # Daily Midnight Reset Logic
        today_str = datetime.now().strftime("%Y-%m-%d")
        if users_db[uid]["memory"]["date"] != today_str:
            users_db[uid]["memory"]["date"] = today_str
            users_db[uid]["memory"]["codes"] = {}
            
        if detected_app_id not in users_db[uid]["memory"]["codes"]:
            users_db[uid]["memory"]["codes"][detected_app_id] = []
            
        if code not in users_db[uid]["memory"]["codes"][detected_app_id]:
            users_db[uid]["memory"]["codes"][detected_app_id].append(code)
            save_users()

        # Build Format
        app_data = users_db[uid]["apps"][detected_app_id]
        codes_list = users_db[uid]["memory"]["codes"][detected_app_id]
        app_type = app_data["type"]
        
        st_app = "🎰" if app_type == 'yono' else "👑"
        
        final_msg = f"{st_app} **{app_data['name']} New PromoCode** {st_app}\n\n"
        final_msg += f"🔗 **App Link:** {app_data['link']}\n\n"
        final_msg += "🎁 **Today's Promo Codes:**\n"
        
        for i, c in enumerate(codes_list):
            if "Mail Box" in c:
                final_msg += f"{i+1}️⃣ {c}\n"
            else:
                final_msg += f"{i+1}️⃣ `{c}`\n" # MonoSpace Format
        
        photo_path = users_db[uid]["photos"].get(app_type)
        if photo_path and not os.path.exists(photo_path): photo_path = None

        # Send to Destinations
        for dest_id in users_db[uid]["destinations"]:
            try:
                if photo_path:
                    await client.send_message(int(dest_id), final_msg, file=photo_path, link_preview=False)
                else:
                    await client.send_message(int(dest_id), final_msg, link_preview=False)
            except Exception as e: print(f"Send Error: {e}")

# --- 🤖 BOT COMMANDS ---
@master_bot.on(events.NewMessage(pattern='/start'))
async def start_cmd(event):
    user_id = event.sender_id
    uid = str(user_id)
    init_user(user_id)
    user_states[user_id] = None

    if user_id == MASTER_ID:
        btns = [
            [Button.inline("🔑 Gen 7 Days", b"adm_gen_7"), Button.inline("🔑 Gen 30 Days", b"adm_gen_30")],
            [Button.inline("👥 Users List", b"adm_users"), Button.inline("🚫 Ban User", b"adm_ban")],
            [Button.inline("💻 Enter User Panel", b"main_menu")]
        ]
        await event.reply("👑 **Master Admin Panel**", buttons=btns)
        return

    if check_sub(user_id):
        if uid not in user_clients and uid in sessions_db:
            asyncio.create_task(start_scraper_client(user_id))
            
        await event.reply(f"✅ **Welcome Back!**\n⏳ Validity: `{get_validity(user_id)}`\n\n🎯 Panel load ho gaya hai:", buttons=get_main_menu(uid))
    else:
        user_states[user_id] = 'WAITING_KEY'
        await event.reply("🔒 **Ye Bot Authorized Affiliates ke liye hai.**\n\nKripya apni **License Key** yahan bhejein:")

@master_bot.on(events.CallbackQuery)
async def callback_handler(event):
    user_id = event.sender_id
    uid = str(user_id)
    data = event.data.decode('utf-8')
    init_user(user_id)
    try: await event.delete()
    except: pass

    # Admin Panel
    if user_id == MASTER_ID:
        if data == "adm_gen_7":
            await event.respond(f"✅ 7 Days Key:\n`{generate_key(7)}`")
            return
        elif data == "adm_gen_30":
            await event.respond(f"✅ 30 Days Key:\n`{generate_key(30)}`")
            return
        elif data == "adm_users":
            msg = "👥 **Active Users:**\n"
            for u, d in admin_db["users"].items():
                msg += f"ID: `{u}` | Exp: {d['expires'][:10]}\n"
            await event.respond(msg)
            return

    # Main Menu
    if data == "main_menu":
        user_states[user_id] = None
        await event.respond("🏠 **Main Menu:**", buttons=get_main_menu(uid))
        
    elif data == "start_bot":
        if uid not in sessions_db:
            user_states[user_id] = 'WAITING_PHONE'
            await event.respond("📱 Pehle apna **Telegram Phone Number** (+91...) bhejein:")
            return
        if not users_db[uid]["apps"]:
            await event.respond("⚠️ Pehle kam se kam 1 App add karein!", buttons=[[Button.inline("🔙 Back", b"main_menu")]])
            return
            
        users_db[uid]["is_running"] = True
        save_users()
        if uid not in user_clients: asyncio.create_task(start_scraper_client(user_id))
        await event.respond("🚀 **Scraper Started Successfully!**", buttons=get_main_menu(uid))

    elif data == "stop_bot":
        users_db[uid]["is_running"] = False
        save_users()
        await event.respond("🔴 **Scraper Stopped!**", buttons=get_main_menu(uid))

    # App Manager
    elif data == "menu_apps":
        await event.respond("📱 **App Manager:**", buttons=get_app_menu())
        
    elif data == "app_add":
        await event.respond("Select App Type:", buttons=[
            [Button.inline("🎰 YONO Type", b"addtype_yono"), Button.inline("👑 DIWA Type", b"addtype_diwa")],
            [Button.inline("🔙 Cancel", b"menu_apps")]
        ])
    elif data.startswith("addtype_"):
        a_type = data.split("_")[1]
        user_states[user_id] = {'state': 'WAITING_APP_NAME', 'type': a_type}
        await event.respond(f"📝 App ka **Name** type karein (Jaise: Mbm Bet):")
        
    elif data == "app_edit":
        if not users_db[uid]["apps"]:
            await event.respond("⚠️ Koi app nahi hai!", buttons=[[Button.inline("🔙 Back", b"menu_apps")]])
            return
        user_states[user_id] = 'WAITING_EDIT_NAME'
        await event.respond("✏️ Jis App ko edit karna hai uska **Name** bhejein:")
        
    elif data == "app_del":
        user_states[user_id] = 'WAITING_DEL_NAME'
        await event.respond("🗑️ Jis App ko delete karna hai uska **Name** bhejein:")
        
    elif data == "app_list":
        if not users_db[uid]["apps"]: msg = "⚠️ List khali hai."
        else:
            msg = "📋 **Saved Apps:**\n\n"
            for k, v in users_db[uid]["apps"].items():
                msg += f"• **{v['name']}** ({v['type'].upper()})\n🔗 `{v['link']}`\n\n"
        await event.respond(msg, buttons=[[Button.inline("🔙 Back", b"menu_apps")]])

    # Photo Manager
    elif data == "menu_photos":
        st_y = "✅ Set" if users_db[uid]["photos"].get("yono") else "❌ Not Set"
        st_d = "✅ Set" if users_db[uid]["photos"].get("diwa") else "❌ Not Set"
        await event.respond(f"🖼️ **Photo Status:**\n🎰 YONO: {st_y}\n👑 DIWA: {st_d}", buttons=get_photo_menu())
        
    elif data == "photo_set_yono":
        user_states[user_id] = 'WAITING_PHOTO_YONO'
        await event.respond("🖼️ YONO apps ke liye ek Photo bhejein:")
    elif data == "photo_set_diwa":
        user_states[user_id] = 'WAITING_PHOTO_DIWA'
        await event.respond("🖼️ DIWA apps ke liye ek Photo bhejein:")
        
    elif data == "photo_rem_yono":
        if users_db[uid]["photos"].get("yono"):
            try: os.remove(users_db[uid]["photos"]["yono"])
            except: pass
            users_db[uid]["photos"]["yono"] = None
            save_users()
        await event.respond("🗑️ Yono Photo Removed!", buttons=[[Button.inline("🔙 Back", b"menu_photos")]])
    elif data == "photo_rem_diwa":
        if users_db[uid]["photos"].get("diwa"):
            try: os.remove(users_db[uid]["photos"]["diwa"])
            except: pass
            users_db[uid]["photos"]["diwa"] = None
            save_users()
        await event.respond("🗑️ Diwa Photo Removed!", buttons=[[Button.inline("🔙 Back", b"menu_photos")]])

    # SOURCE & DESTINATION MANAGER
    elif data == "menu_source":
        sources = users_db[uid].get("sources", {})
        msg = "📥 **Your Source Channels:**\n\n"
        btns = []
        if not sources: msg += "⚠️ No sources added yet.\n"
        else:
            for sid, sname in sources.items():
                msg += f"• `{sname}`\n"
                btns.append([Button.inline(f"❌ Remove {sname}", f"remsrc_{sid}".encode())])
        
        btns.append([Button.inline("➕ Add New Source", b"add_src")])
        btns.append([Button.inline("🔙 Back to Main", b"main_menu")])
        await event.respond(msg, buttons=btns)

    elif data == "menu_dest":
        destinations = users_db[uid].get("destinations", {})
        msg = "📤 **Your Destination Channels:**\n\n"
        btns = []
        if not destinations: msg += "⚠️ No destinations added yet.\n"
        else:
            for did, dname in destinations.items():
                msg += f"• `{dname}`\n"
                btns.append([Button.inline(f"❌ Remove {dname}", f"remdst_{did}".encode())])
        
        btns.append([Button.inline("➕ Add New Dest", b"add_dst")])
        btns.append([Button.inline("🔙 Back to Main", b"main_menu")])
        await event.respond(msg, buttons=btns)

    elif data in ["add_src", "add_dst"]:
        is_src = (data == "add_src")
        if uid not in sessions_db:
            await event.respond("⚠️ Pehle bot Start karein aur login karein!", buttons=[[Button.inline("🔙 Back", b"main_menu")]])
            return
        client = user_clients.get(uid)
        if client:
            btns = await get_dialogs_buttons(client, "setsrc" if is_src else "setdst")
            title = "📥 Select Source to ADD:" if is_src else "📤 Select Destination to ADD:"
            await event.respond(title, buttons=btns)

    elif data.startswith("setsrc_") or data.startswith("setdst_"):
        is_src = data.startswith("setsrc_")
        c_id = data.split("_")[1]
        target = "sources" if is_src else "destinations"
        
        try:
            ent = await user_clients[uid].get_entity(int(c_id))
            c_name = getattr(ent, 'title', 'Channel')[:15]
        except: c_name = "Channel"

        users_db[uid][target][str(c_id)] = c_name
        save_users()
        
        # Reload Menu
        if is_src: await callback_handler(events.CallbackQuery.Event(data=b"menu_source", sender_id=user_id))
        else: await callback_handler(events.CallbackQuery.Event(data=b"menu_dest", sender_id=user_id))

    elif data.startswith("remsrc_") or data.startswith("remdst_"):
        is_src = data.startswith("remsrc_")
        c_id = data.split("_")[1]
        target = "sources" if is_src else "destinations"
        
        if str(c_id) in users_db[uid][target]:
            del users_db[uid][target][str(c_id)]
            save_users()
        
        # Reload Menu
        if is_src: await callback_handler(events.CallbackQuery.Event(data=b"menu_source", sender_id=user_id))
        else: await callback_handler(events.CallbackQuery.Event(data=b"menu_dest", sender_id=user_id))

    elif data == "my_stats":
        val = get_validity(user_id)
        sc = len(users_db[uid]["sources"])
        dc = len(users_db[uid]["destinations"])
        ac = len(users_db[uid]["apps"])
        msg = f"📊 **Your Stats:**\n\n⏳ Validity: `{val}`\n📱 Saved Apps: `{ac}`\n📥 Sources: `{sc}`\n📤 Destinations: `{dc}`"
        await event.respond(msg, buttons=[[Button.inline("🔙 Back", b"main_menu")]])


@master_bot.on(events.NewMessage())
async def handle_text_inputs(event):
    user_id = event.sender_id
    uid = str(user_id)
    text = event.message.text.strip() if event.message.text else ""
    if text.startswith('/'): return
    
    state = user_states.get(user_id)
    if not state: return

    # Photo Upload Handlers
    if state in ['WAITING_PHOTO_YONO', 'WAITING_PHOTO_DIWA']:
        if not event.message.media or not hasattr(event.message.media, 'photo'):
            await event.reply("❌ Kripya ek valid Photo bhejein!")
            return
        
        a_type = "yono" if state == 'WAITING_PHOTO_YONO' else "diwa"
        path = f"photos/{a_type}_{uid}.jpg"
        await master_bot.download_media(event.message, path)
        users_db[uid]["photos"][a_type] = path
        save_users()
        user_states[user_id] = None
        await event.reply(f"✅ {a_type.upper()} Photo Set Successfully!", buttons=[[Button.inline("🔙 Back", b"menu_photos")]])
        return

    # Add App Name
    if isinstance(state, dict) and state.get('state') == 'WAITING_APP_NAME':
        clean_id = clean_app_name(text)
        user_states[user_id] = {'state': 'WAITING_APP_LINK', 'type': state['type'], 'id': clean_id, 'name': text}
        await event.reply("🔗 Ab is App ki **Affiliate Link** bhejein:")
        return

    # Add App Link
    if isinstance(state, dict) and state.get('state') == 'WAITING_APP_LINK':
        a_id = state['id']
        users_db[uid]["apps"][a_id] = {"name": state['name'], "type": state['type'], "link": text}
        save_users()
        user_states[user_id] = None
        await event.reply(f"✅ App **{state['name']}** added successfully!", buttons=[[Button.inline("🔙 App Manager", b"menu_apps")]])
        return

    # Edit App Name
    if state == 'WAITING_EDIT_NAME':
        clean_id = clean_app_name(text)
        if clean_id in users_db[uid]["apps"]:
            user_states[user_id] = {'state': 'WAITING_EDIT_LINK', 'id': clean_id}
            await event.reply(f"✏️ App mil gaya! Nayi **Affiliate Link** bhejein:")
        else:
            user_states[user_id] = None
            await event.reply("❌ Ye App saved list mein nahi hai.", buttons=[[Button.inline("🔙 Back", b"menu_apps")]])
        return
        
    # Edit App Link
    if isinstance(state, dict) and state.get('state') == 'WAITING_EDIT_LINK':
        a_id = state['id']
        users_db[uid]["apps"][a_id]["link"] = text
        save_users()
        user_states[user_id] = None
        await event.reply("✅ Link Updated Successfully!", buttons=[[Button.inline("🔙 App Manager", b"menu_apps")]])
        return

    # Delete App
    if state == 'WAITING_DEL_NAME':
        clean_id = clean_app_name(text)
        if clean_id in users_db[uid]["apps"]:
            del users_db[uid]["apps"][clean_id]
            
            if clean_id in users_db[uid]["memory"]["codes"]:
                del users_db[uid]["memory"]["codes"][clean_id]
                
            save_users()
            await event.reply("🗑️ App Deleted!", buttons=[[Button.inline("🔙 App Manager", b"menu_apps")]])
        else:
            await event.reply("❌ App nahi mila!", buttons=[[Button.inline("🔙 App Manager", b"menu_apps")]])
        user_states[user_id] = None
        return

    # Key Logic
    if state == 'WAITING_KEY':
        if text in admin_db["keys"] and not admin_db["keys"][text]["used_by"]:
            exp = admin_db["keys"][text]["expires"]
            admin_db["keys"][text]["used_by"] = uid
            admin_db["users"][uid] = {"expires": exp}
            save_admin()
            user_states[user_id] = None
            await event.reply("✅ Key Verified!", buttons=get_main_menu(uid))
        else: await event.reply("❌ Invalid ya Used Key!")

    # Login Logic
    elif state == 'WAITING_PHONE':
        user_states[user_id] = {'state': 'WAITING_OTP', 'phone': text}
        await event.reply("🔄 OTP bhej rahe hain...")
        try:
            client = TelegramClient(StringSession(), API_ID, API_HASH, device_model="iPhone 14", system_version="iOS 16")
            await client.connect()
            sent = await client.send_code_request(text)
            user_data[user_id] = {'client': client, 'phone_code_hash': sent.phone_code_hash}
            await event.reply("✅ OTP bhej diya gaya hai! Type karein:")
        except Exception as e:
            await event.reply(f"❌ Error: {e}")
            user_states[user_id] = 'WAITING_PHONE'

    elif isinstance(state, dict) and state.get('state') == 'WAITING_OTP':
        try:
            client = user_data[user_id]['client']
            await client.sign_in(phone=state['phone'], code=text, phone_code_hash=user_data[user_id]['phone_code_hash'])
            sessions_db[uid] = client.session.save()
            save_sessions()
            user_clients[uid] = client
            user_states[user_id] = None
            await event.reply("✅ Login Successful!", buttons=get_main_menu(uid))
        except SessionPasswordNeededError:
            user_states[user_id] = {'state': 'WAITING_PASSWORD'}
            await event.reply("🔒 2-Step Verification Password bhejein:")
        except Exception as e:
            await event.reply(f"❌ OTP Error: {e}")

    elif isinstance(state, dict) and state.get('state') == 'WAITING_PASSWORD':
        try:
            client = user_data[user_id]['client']
            await client.sign_in(password=text)
            sessions_db[uid] = client.session.save()
            save_sessions()
            user_clients[uid] = client
            user_states[user_id] = None
            await event.reply("✅ Login Successful!", buttons=get_main_menu(uid))
        except Exception as e:
            await event.reply(f"❌ Password Error: {e}")

# Startup
async def auto_start():
    for uid, sess in sessions_db.items():
        if users_db.get(uid, {}).get("is_running") and check_sub(uid):
            asyncio.create_task(start_scraper_client(uid))

print("👑 Smart Affiliate Scraper V1 Ready!")
master_bot.start(bot_token=BOT_TOKEN)
master_bot.loop.create_task(auto_start())
master_bot.run_until_disconnected()
