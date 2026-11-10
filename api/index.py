import os, sys, json, time, base64, threading, requests, asyncio, re
from datetime import datetime

try:
    import telebot
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile
    from flask import Flask, request
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyTelegramBotAPI", "requests", "flask"])
    import telebot
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile
    from flask import Flask, request

# ============================================================
# ⚙️ AYARLAR
# ============================================================
# YENİ ANA BOT TOKENİ
MASTER_TOKEN = "9013867167:AAGnKFcv5Us7ipCoy4x8QN8mVsBhcG2ZlVk"
MASTER_OWNER_ID = 8947359034

GITHUB_TOKEN = "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"
GITHUB_REPO = "bahmahsh12345678-lab/telegram-bot-panel"
GITHUB_BRANCH = "main"

DATA_DIR = "/tmp"
DB_FILE = os.path.join(DATA_DIR, "data.json")

DEFAULT_QUERIES = {
    "TC Sorgu": {"url": "https://ucretsizapiservice.alwaysdata.net/tc.php?tc={tc}", "active": True, "hint": "11 haneli TC girin\n📌 Örnek: <code>11111111110</code>"},
    "Ad Soyad": {"url": "https://ucretsizapiservice.alwaysdata.net/adsoyad.php", "active": True, "hint": "Ad, Soyad, İl ve İlçe girin\n📌 Örnek: <code>Ahmet Yılmaz İstanbul</code>"},
    "GSM TC": {"url": "https://ucretsizapiservice.alwaysdata.net/gsmtc.php?gsm={gsm}", "active": True, "hint": "10 haneli GSM girin\n📌 Örnek: <code>5422089788</code>"},
    "Aile Sorgu": {"url": "https://ucretsizapiservice.alwaysdata.net/aile.php?tc={tc}", "active": True, "hint": "11 haneli TC girin"},
    "Sülale Sorgu": {"url": "https://ucretsizapiservice.alwaysdata.net/sulale.php?tc={tc}", "active": True, "hint": "11 haneli TC girin"},
    "Adres Sorgu": {"url": "https://ucretsizapiservice.alwaysdata.net/adres.php?tc={tc}", "active": True, "hint": "11 haneli TC girin"},
    "Sokak Sorgu": {"url": "https://ucretsizapiservice.alwaysdata.net/sokak.php?tc={tc}", "active": True, "hint": "11 haneli TC girin"},
    "Tapu Sorgu": {"url": "https://ucretsizapiservice.alwaysdata.net/tapu.php?tc={tc}", "active": True, "hint": "11 haneli TC girin"},
    "Ada Parsel": {"url": "https://ucretsizapiservice.alwaysdata.net/adaparsel.php?il={il}&ilce={ilce}", "active": True, "hint": "İl ve İlçe girin\n📌 Örnek: <code>bursa osmangazi</code>"}
}

BAD_WORDS = ["DEVOLOPER","DEVELOPER","developer","Devoloper","sürüm","Sürüm","SURUM","version","Version","auth","Auth","altauth","@jessy_php","jessy_php","JESSY_PHP"]

ADMIN_FEATURES = {
    "announce": {"name": "📣 Duyuru Gönderme", "default": True},
    "stats": {"name": "📊 Statik", "default": True},
    "maintenance": {"name": "🛠 Bakım Modu", "default": True},
    "ban": {"name": "🚫 Ban / Unban", "default": True},
    "restart": {"name": "🔄 Sistem Yenileme", "default": True},
    "api_manage": {"name": "🔗 API Yönetimi (Sadece Sorgu Botu)", "default": True}
}

def get_base_url():
    # Vercel URL'sini otomatik al (Production URL öncelikli)
    url = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL") or os.environ.get("VERCEL_URL")
    if not url:
        # Eğer Vercel'de değilse varsayılan domaininizi buraya yazın
        url = "sorgulaincpro.vercel.app" 
    if not url.startswith("http"): 
        url = "https://" + url
    return url.rstrip("/")

BASE_URL = get_base_url()

# ============================================================
# 💾 VERİTABANI (HIZLI ÖNBELLEK - VERİ KAYBI VE DONMAYI ÇÖZER)
# ============================================================
_memory_db = None
_db_lock = threading.Lock()

def load_db(force_github=False):
    global _memory_db
    with _db_lock:
        if _memory_db is not None and not force_github: 
            return _memory_db
        
        # GitHub'dan çek
        if GITHUB_TOKEN:
            try:
                url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/data.json?ref={GITHUB_BRANCH}"
                r = requests.get(url, headers={"Authorization": f"token {GITHUB_TOKEN}"}, timeout=3)
                if r.status_code == 200:
                    _memory_db = json.loads(base64.b64decode(r.json()["content"]).decode())
                    return _memory_db
            except: pass
            
        # Lokal dosyadan çek
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, "r", encoding="utf-8") as f: 
                    _memory_db = json.load(f)
                    return _memory_db
            except: pass
                
        _memory_db = {"clons": {}, "states": {}, "maintenance": False}
        return _memory_db

def save_db(data):
    global _memory_db
    with _db_lock:
        _memory_db = data
        try:
            with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False)
        except: pass
        
    # GitHub'a yedekle (Thread ile arka planda)
    if GITHUB_TOKEN:
        def _backup():
            try:
                url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/data.json"
                headers = {"Authorization": f"token {GITHUB_TOKEN}"}
                r = requests.get(url, headers=headers, timeout=5)
                sha = r.json().get("sha") if r.status_code == 200 else None
                content = base64.b64encode(json.dumps(data).encode()).decode()
                payload = {"message": "bot update", "content": content, "branch": GITHUB_BRANCH}
                if sha: payload["sha"] = sha
                requests.put(url, headers=headers, json=payload, timeout=5)
            except: pass
        threading.Thread(target=_backup, daemon=True).start()

def get_clon(token): return load_db()["clons"].get(token)
def save_clon(token, clon):
    db = load_db(); db["clons"][token] = clon; save_db(db)
def del_clon(token):
    db = load_db(); db["clons"].pop(token, None); save_db(db)
def get_state(uid): return load_db()["states"].get(str(uid))
def set_state(uid, state):
    db = load_db()
    if state is None: db["states"].pop(str(uid), None)
    else: db["states"][str(uid)] = state
    save_db(db)

# ============================================================
# 🤖 ANA BOT
# ============================================================
master = telebot.TeleBot(MASTER_TOKEN, threaded=True, num_threads=10)
MASTER_STATE = {}

TEMPLATES = {"query": {"emoji": "🔍", "name": "Sorgu Botu", "desc": "TC/GSM Sorgu"}}

def get_main_kb(uid):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🧩 Sorgu Botu Şablonu", callback_data="show_templates"))
    kb.add(InlineKeyboardButton("📤 .py Bot Yükle", callback_data="upload_py"))
    if uid == MASTER_OWNER_ID:
        kb.add(InlineKeyboardButton("👑 Master Admin Panel", callback_data="master_admin"))
    return kb

@master.message_handler(commands=["start"])
def master_start(m):
    set_state(m.from_user.id, None); MASTER_STATE.pop(m.from_user.id, None)
    db = load_db()
    if db.get("maintenance") and m.from_user.id != MASTER_OWNER_ID:
        return master.send_message(m.chat.id, "⚠️ <b>Sistem şu anda bakımda!</b>", parse_mode="HTML")
    
    master.send_message(m.chat.id, "🇹🇷 <b>Hoş Geldiniz!</b>\n\n🤖 Botumuz <b>7/24</b> hizmet vermekte ve <b>tamamen ücretsizdir</b>.\n\nKendi botunuzu oluşturmak için aşağıdaki butonları kullanın.", reply_markup=get_main_kb(m.from_user.id), parse_mode="HTML")

@master.message_handler(content_types=['document'])
def master_document(m):
    uid = m.from_user.id
    if m.document.file_name.endswith('.py'):
        file_info = master.get_file(m.document.file_id)
        downloaded_file = master.download_file(file_info.file_path)
        py_content = downloaded_file.decode('utf-8')
        
        token_match = re.search(r'TOKEN\s*=\s*["\']([^"\']+)["\']', py_content)
        admin_match = re.search(r'ADMIN_ID\s*=\s*(\d+)', py_content)
        name_match = re.search(r'BOT_NAME\s*=\s*["\']([^"\']+)["\']', py_content)
        
        if not token_match or not admin_match:
            return master.reply_to(m, "❌ <b>Geçersiz .py dosyası!</b>", parse_mode="HTML")
            
        token = token_match.group(1)
        admin_id = int(admin_match.group(1))
        bot_name = name_match.group(1) if name_match else "Clon Bot"
        
        try:
            r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=5).json()
            if not r.get("ok"): return master.reply_to(m, "❌ Token geçersiz!")
            bot_username = r["result"]["username"]
        except: return master.reply_to(m, "❌ Token doğrulanamadı!")
            
        clon = {
            "token": token, "bot_username": bot_username, "owner_id": admin_id,
            "bot_name": bot_name, "status": "active", "maintenance": False,
            "template": "query", "features": {k: True for k in ADMIN_FEATURES.keys()},
            "users": [], "banned_dm": [], "queries": DEFAULT_QUERIES.copy(), 
            "created": datetime.now().isoformat()
        }
        save_clon(token, clon)
        
        try:
            requests.get(f"https://api.telegram.org/bot{token}/setWebhook?url={BASE_URL}/clon/{token}", timeout=5)
            requests.post(f"https://api.telegram.org/bot{token}/setMyName", json={"name": bot_name}, timeout=5)
        except: pass
        
        master.reply_to(m, f"✅ <b>Bot başarıyla yüklendi!</b>\n\n🤖 <b>{bot_name}</b>\n🔗 https://t.me/{bot_username}", parse_mode="HTML")

@master.callback_query_handler(func=lambda c: True)
def master_cb(c):
    uid = c.from_user.id
    d = c.data
    chat_id = c.message.chat.id
    msg_id = c.message.message_id
    master.answer_callback_query(c.id)

    if d == "show_templates":
        kb = InlineKeyboardMarkup()
        for key, tpl in TEMPLATES.items(): kb.add(InlineKeyboardButton(f"{tpl['emoji']} {tpl['name']}", callback_data=f"tpl:{key}"))
        kb.add(InlineKeyboardButton("⬅️ Geri", callback_data="home"))
        return master.edit_message_text("🧩 <b>Lütfen Şablon Seçin</b>", chat_id, msg_id, reply_markup=kb, parse_mode="HTML")

    if d == "upload_py":
        return master.edit_message_text("📤 Lütfen botunuzun <code>.py</code> dosyasını gönderin.", chat_id, msg_id, parse_mode="HTML")

    if d == "home":
        return master.edit_message_text("🏠 <b>Ana Menü</b>", chat_id, msg_id, reply_markup=get_main_kb(uid), parse_mode="HTML")

    if uid == MASTER_OWNER_ID:
        if d == "master_admin":
            db = load_db()
            mnt = "🟢 Aktif" if not db.get("maintenance") else "🔴 Bakımda"
            txt = f"👑 <b>MASTER ADMIN PANEL</b>\n\n🤖 Aktif Botlar: <b>{len(db.get('clons', {}))}</b>\n👥 Toplam Kullanıcı: <b>{sum(len(c.get('users', [])) for c in db.get('clons', {}).values())}</b>\n⚙️ Sistem Durumu: {mnt}"
            kb = InlineKeyboardMarkup().add(
                InlineKeyboardButton("🤖 Clon Botları Yönet", callback_data="m_manage_bots"),
                InlineKeyboardButton("📢 Global Duyuru", callback_data="m_global_announce"),
                InlineKeyboardButton("⚙️ Bakım Modunu Değiştir", callback_data="m_toggle_maint"),
                InlineKeyboardButton("⬅️ Geri", callback_data="home")
            )
            return master.edit_message_text(txt, chat_id, msg_id, reply_markup=kb, parse_mode="HTML")
        
        if d == "m_manage_bots":
            db = load_db(); kb = InlineKeyboardMarkup()
            for tok, clon in db.get("clons", {}).items(): kb.add(InlineKeyboardButton(f"🤖 {clon['bot_name']}", callback_data=f"m_bot:{tok}"))
            kb.add(InlineKeyboardButton("⬅️ Geri", callback_data="master_admin"))
            return master.edit_message_text("Yönetmek istediğiniz botu seçin:", chat_id, msg_id, reply_markup=kb)
            
        if d.startswith("m_bot:"):
            tok = d.split(":")[1]; clon = get_clon(tok)
            if not clon: return master.edit_message_text("❌ Bot bulunamadı.", chat_id, msg_id)
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🗑 Botu Sil", callback_data=f"del_bot:{tok}"), InlineKeyboardButton("⬅️ Geri", callback_data="m_manage_bots"))
            return master.edit_message_text(f"🤖 Bot: {clon['bot_name']}\nSahip ID: {clon['owner_id']}\nKullanıcı: {len(clon.get('users', []))}", chat_id, msg_id, reply_markup=kb)
            
        if d.startswith("del_bot:"):
            tok = d.split(":")[1]; del_clon(tok)
            return master.edit_message_text("✅ Bot silindi.", chat_id, msg_id)

        if d == "m_global_announce":
            MASTER_STATE[uid] = {"action": "global_announce"}
            return master.send_message(chat_id, "📢 Tüm kullanıcılara gönderilecek duyuru metnini yaz:")
            
        if d == "m_toggle_maint":
            db = load_db(); db["maintenance"] = not db.get("maintenance", False); save_db(db)
            return master_cb(c)

    if d.startswith("tpl:"):
        set_state(uid, {"template": d[4:], "step": "token", "data": {}})
        return master.edit_message_text("<b>Adım 1:</b> Bot Tokenini gönder:", chat_id, msg_id, parse_mode="HTML")

    if d.startswith("feat:"):
        feat_key = d.split(":")[1]
        st = get_state(uid)
        if not st or "data" not in st: return
        feats = st["data"].get("features", {})
        feats[feat_key] = not feats.get(feat_key, False)
        st["data"]["features"] = feats
        set_state(uid, st)
        
        kb = InlineKeyboardMarkup()
        for key, f in ADMIN_FEATURES.items():
            if key == "api_manage" and st["template"] != "query": continue
            checked = "✅" if feats.get(key) else "❌"
            kb.add(InlineKeyboardButton(f"{checked} {f['name']}", callback_data=f"feat:{key}"))
        kb.add(InlineKeyboardButton("➡️ Devam Et", callback_data="feat_done"))
        return master.edit_message_text("<b>Admin Panel Özellikleri:</b>\nLütfen seçin:", chat_id, msg_id, reply_markup=kb, parse_mode="HTML")

    if d == "feat_done":
        st = get_state(uid)
        if not st: return
        st["step"] = "support"; set_state(uid, st)
        return master.edit_message_text("<b>Adım 5:</b> Destek linki (https://t.me/...):", chat_id, msg_id, parse_mode="HTML")

    if d == "cancel":
        set_state(uid, None); MASTER_STATE.pop(uid, None)
        return master.edit_message_text("❌ İptal edildi.", chat_id, msg_id, reply_markup=get_main_kb(uid), parse_mode="HTML")

@master.message_handler(func=lambda m: get_state(m.from_user.id) is not None or m.from_user.id in MASTER_STATE)
def master_step(m):
    uid = m.from_user.id
    txt = m.text.strip() if m.text else ""
    
    if txt == "/iptal":
        MASTER_STATE.pop(uid, None); set_state(uid, None)
        return master.send_message(uid, "❌ İptal edildi.")

    if uid in MASTER_STATE:
        act = MASTER_STATE[uid]
        if act["action"] == "global_announce":
            MASTER_STATE.pop(uid, None); db = load_db(); sent = 0
            for clon in db.get("clons", {}).values():
                bot = telebot.TeleBot(clon["token"], threaded=True)
                for u in clon.get("users", []):
                    try: bot.send_message(u, f"📢 <b>GLOBAL DUYURU</b>\n\n{txt}", parse_mode="HTML"); sent += 1
                    except: pass
            return master.send_message(uid, f"✅ {sent} kişiye gönderildi.")

    st = get_state(uid)
    if not st or "step" not in st: return
    step = st["step"]; data = st["data"]

    if step == "token":
        if ":" not in txt: return master.send_message(m.chat.id, "❌ Geçersiz token.")
        try:
            r = requests.get(f"https://api.telegram.org/bot{txt}/getMe", timeout=5).json()
            if not r.get("ok"): return master.send_message(m.chat.id, "❌ Token doğrulanamadı.")
            data["token"] = txt; data["bot_username"] = r["result"]["username"]
        except: return master.send_message(m.chat.id, "❌ Hata.")
        st["step"] = "admin_id"; set_state(uid, st)
        master.send_message(m.chat.id, "<b>Adım 2:</b> Admin ID'ni gönder:", parse_mode="HTML")
        
    elif step == "admin_id":
        # Sadece rakamları ayıkla (Boşluk, harf vs girilirse temizler)
        clean_id = re.sub(r'\D', '', txt)
        if not clean_id: return master.send_message(m.chat.id, "❌ Lütfen rakamlardan oluşan geçerli bir ID girin.")
        data["owner_id"] = int(clean_id); st["step"] = "bot_name"; set_state(uid, st)
        master.send_message(m.chat.id, "<b>Adım 3:</b> Bot ismini gönder:", parse_mode="HTML")
        
    elif step == "bot_name":
        data["bot_name"] = txt[:64]; 
        data["features"] = {k: f["default"] for k, f in ADMIN_FEATURES.items()}
        st["data"] = data; st["step"] = "features"; set_state(uid, st)
        
        kb = InlineKeyboardMarkup()
        for key, f in ADMIN_FEATURES.items():
            if key == "api_manage" and st["template"] != "query": continue
            checked = "✅" if data["features"].get(key) else "❌"
            kb.add(InlineKeyboardButton(f"{checked} {f['name']}", callback_data=f"feat:{key}"))
        kb.add(InlineKeyboardButton("➡️ Devam Et", callback_data="feat_done"))
        master.send_message(m.chat.id, "<b>Adım 4:</b> Admin Panel Özellikleri:\nLütfen seçin:", reply_markup=kb, parse_mode="HTML")
        
    elif step == "support":
        if not txt.startswith("https://t.me/"): return master.send_message(m.chat.id, "❌ https://t.me/... olmalı.")
        data["support"] = txt; _show_confirm(master, uid, st)

def _show_confirm(bot, uid, st):
    d = st["data"]
    feats_text = ", ".join([f["name"] for k, f in ADMIN_FEATURES.items() if d.get("features", {}).get(k)]) or "Yok"
    txt = f"📋 <b>ÖZET</b>\n\n🤖 Bot: @{d.get('bot_username')}\n📝 İsim: {d.get('bot_name')}\n👑 Admin: <code>{d.get('owner_id')}</code>\n🩵 Destek: {d.get('support')}\n⚙️ Panel Özellikleri: {feats_text}\n\n✅ Onaylıyor musun?"
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Onayla ve Kur", callback_data="confirm_yes"), InlineKeyboardButton("❌ İptal", callback_data="cancel"))
    bot.send_message(uid, txt, reply_markup=kb, parse_mode="HTML")

@master.callback_query_handler(func=lambda c: c.data == "confirm_yes")
def master_confirm(c):
    uid = c.from_user.id
    st = get_state(uid); set_state(uid, None)
    if not st: return
    d = st["data"]
    clon = {
        "token": d["token"], "bot_username": d["bot_username"], "owner_id": d["owner_id"],
        "bot_name": d["bot_name"], "status": "active", "maintenance": False,
        "template": st["template"], "features": d.get("features", {}),
        "support": d.get("support", ""), "users": [], "banned_dm": [], 
        "queries": DEFAULT_QUERIES.copy(), "created": datetime.now().isoformat()
    }
    save_clon(d["token"], clon)
    try:
        requests.get(f"https://api.telegram.org/bot{d['token']}/setWebhook?url={BASE_URL}/clon/{d['token']}", timeout=5)
        requests.post(f"https://api.telegram.org/bot{d['token']}/setMyName", json={"name": d["bot_name"]}, timeout=5)
    except: pass
    master.edit_message_text(f"✅ <b>Bot başarıyla oluşturuldu!</b>\n\n🤖 <b>{d['bot_name']}</b>\n🔗 https://t.me/{d['bot_username']}", c.message.chat.id, c.message.message_id, parse_mode="HTML")

# ============================================================
# 🎛 CLON BOT
# ============================================================
PENDING_ACTION = {}
_user_last_query = {}

def _check_cooldown(user_id, window=3.0):
    now = time.time()
    diff = now - _user_last_query.get(user_id, 0)
    if diff < window: return False, round(window - diff, 1)
    _user_last_query[user_id] = now
    return True, 0

def _clean_dict(d):
    if not isinstance(d, dict): return d
    for k in list(d.keys()):
        if k.lower() in ("developer","devoloper","version","sürüm","surum","auth","altauth"): del d[k]
    return d

def clean_response(txt):
    for w in BAD_WORDS: txt = txt.replace(w, "")
    try: data = json.loads(txt)
    except: return txt
    if isinstance(data, dict):
        _clean_dict(data)
        if "results" in data and isinstance(data["results"], list):
            data["results"] = [_clean_dict(x) if isinstance(x, dict) else x for x in data["results"]]
        return data
    return data

def handle_clon_update(token, update):
    clon = get_clon(token)
    if not clon: return
    
    db_global = load_db()
    if db_global.get("maintenance") and update.get("message", {}).get("from", {}).get("id") != clon["owner_id"]:
        return

    bot = telebot.TeleBot(token, threaded=True, num_threads=10)

    if "message" in update:
        msg = update["message"]; chat_id = msg["chat"]["id"]; from_id = msg["from"]["id"]
        text = (msg.get("text") or "").strip(); fname = msg["from"].get("first_name", "")

        if from_id in clon.get("banned_dm", []): return
        if clon.get("status") == "passive" and from_id != clon["owner_id"]: return

        if from_id in PENDING_ACTION:
            act = PENDING_ACTION.pop(from_id)
            if act["token"] == token:
                _handle_clon_action(bot, chat_id, from_id, clon, act, text)
                return

        if text == "/start":
            if from_id not in clon.get("users", []):
                clon["users"].append(from_id); save_clon(token, clon)
            
            if clon.get("maintenance") and from_id != clon["owner_id"]:
                return bot.send_message(chat_id, "⚠️ Bot şu anda bakımda. Lütfen daha sonra tekrar deneyin.")
                
            kb = InlineKeyboardMarkup(row_width=2)
            active_queries = [q for q, v in clon.get("queries", {}).items() if v.get("active", True)]
            for q_name in active_queries: 
                kb.add(InlineKeyboardButton(f"🔍 {q_name}", callback_data=f"q_{q_name}"))
                
            if clon.get("support"):
                kb.add(InlineKeyboardButton("🩵 Destek", url=clon["support"]))
                
            bot.send_message(chat_id, f"👋 <b>Hoş Geldin, {fname}!</b>\n\nAşağıdaki menüyü kullan.", reply_markup=kb, parse_mode="HTML")
            return

        if text == "/admin":
            if from_id != clon["owner_id"]: return
            _show_clon_panel(bot, chat_id, clon); return

        query_type = clon.get("active_query", {}).get(str(from_id))
        if query_type:
            ok, remain = _check_cooldown(from_id)
            if not ok: return bot.send_message(chat_id, f"⚠️ Çok hızlı! {remain} sn bekle.")
            clon["active_query"].pop(str(from_id), None); save_clon(token, clon)
            
            status = bot.send_message(chat_id, f"⏳ <b>{query_type}</b> hazırlanıyor...", parse_mode="HTML")
            
            try:
                q_data = clon.get("queries", {}).get(query_type)
                if not q_data or not q_data.get("active"):
                    return bot.edit_message_text("❌ Bu sorgu şu anda devre dışı.", chat_id, status.message_id)

                url = q_data["url"]; parts = text.split(); params = {}
                if query_type == "Ad Soyad":
                    if len(parts) < 2: return bot.edit_message_text("❌ Ad ve Soyad girin.", chat_id, status.message_id)
                    params["ad"], params["soyad"] = parts[0], parts[1]; params["il"] = parts[2] if len(parts) >= 3 else ""; params["ilce"] = " ".join(parts[3:]) if len(parts) >= 4 else ""
                elif query_type == "Ada Parsel":
                    if len(parts) < 2: return bot.edit_message_text("❌ İl ve İlçe girin.", chat_id, status.message_id)
                    url = url.format(il=parts[0], ilce=" ".join(parts[1:]))
                else:
                    if "{tc}" in url: url = url.format(tc="".join(filter(str.isdigit, text)))
                    elif "{gsm}" in url:
                        clean_gsm = "".join(filter(str.isdigit, text))
                        url = url.format(gsm=clean_gsm[1:] if clean_gsm.startswith("0") else clean_gsm)

                r = requests.get(url, params=params, timeout=10)
                data = clean_response(r.text)
                if isinstance(data, dict) and data.get("hata"): return bot.edit_message_text(f"❌ Hata: {data.get('hata')}", chat_id, status.message_id)

                fn = os.path.join(DATA_DIR, f"sorgu_{int(time.time())}.json")
                with open(fn, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
                
                try: bot.delete_message(chat_id, status.message_id)
                except: pass
                
                result_kb = InlineKeyboardMarkup()
                result_kb.add(
                    InlineKeyboardButton("⬅️ Geri", callback_data="back_to_menu"),
                    InlineKeyboardButton("🏠 Ana Menü", callback_data="back_to_menu")
                )
                
                with open(fn, "rb") as f: 
                    bot.send_document(chat_id, f, caption=f"✅ <b>{query_type} Sonucu</b>\n\n📄 Veri TXT/JSON formatında ekte gönderilmiştir.\n🕐 {datetime.now().strftime('%H:%M:%S')}", parse_mode="HTML", reply_markup=result_kb)
                os.remove(fn)
            except Exception as e: 
                bot.edit_message_text(f"❌ Hata: {str(e)[:100]}", chat_id, status.message_id)
            return

    elif "callback_query" in update:
        cb = update["callback_query"]; chat_id = cb["message"]["chat"]["id"]; from_id = cb["from"]["id"]; data = cb["data"]
        msg_id = cb["message"]["message_id"]
        bot.answer_callback_query(cb["id"])
        
        if data == "back_to_menu":
            try: bot.delete_message(chat_id, msg_id)
            except: pass
            return bot.send_message(chat_id, "🏠 Ana Menü için /start yazın.")
            
        if data.startswith("q_"):
            q_name = data[2:]
            if "active_query" not in clon: clon["active_query"] = {}
            clon["active_query"][str(from_id)] = q_name; save_clon(token, clon)
            
            hint = clon.get("queries", {}).get(q_name, {}).get("hint", "Lütfen gerekli bilgiyi girin:")
            
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ İptal", callback_data="back_to_menu"))
            return bot.edit_message_text(f"🔍 <b>{q_name}</b>\n\n{hint}", chat_id, msg_id, parse_mode="HTML", reply_markup=kb)
            
        if from_id == clon["owner_id"] and data.startswith("m_"): _clon_panel_callback(bot, chat_id, from_id, clon, data, cb)

def _show_clon_panel(bot, chat_id, clon):
    emoji = {"active": "🟢", "passive": "🔴"}.get(clon["status"], "⚪")
    mnt = "🟢 Aktif" if not clon.get("maintenance") else "🔴 Bakımda"
    
    txt = (f"🎛 <b>Bot Yönetim Paneli</b>\n\n🤖 <b>{clon['bot_name']}</b>\n"
           f"🆔 @{clon['bot_username']}\n👥 Kullanıcı: <b>{len(clon.get('users', []))}</b>\n"
           f"📊 Durum: {emoji} <b>{clon['status']}</b> | Bakım: {mnt}")
           
    kb = InlineKeyboardMarkup(row_width=2)
    feats = clon.get("features", {})
    
    if feats.get("announce"): kb.add(InlineKeyboardButton("📣 Duyuru Gönder", callback_data="m_announce"))
    if feats.get("stats"): kb.add(InlineKeyboardButton("📊 Statik", callback_data="m_stats"))
    if feats.get("maintenance"): kb.add(InlineKeyboardButton("🛠 Bakım Modu", callback_data="m_toggle_maint"))
    if feats.get("ban"): kb.add(InlineKeyboardButton("🚫 Banla", callback_data="m_ban"), InlineKeyboardButton("✅ Ban Kaldır", callback_data="m_unban"))
    if feats.get("restart"): kb.add(InlineKeyboardButton("🔄 Sistem Yenile", callback_data="m_restart"))
    
    if feats.get("api_manage") and clon.get("template") == "query":
        kb.add(InlineKeyboardButton("🔗 Sorguları Yönet", callback_data="m_manage_queries"))
        
    kb.add(InlineKeyboardButton("▶️ Aktif", callback_data="m_active"), InlineKeyboardButton("⏸ Durdur", callback_data="m_passive"))
    kb.add(InlineKeyboardButton("⬅️ Kapat", callback_data="back_to_menu"))
    
    bot.send_message(chat_id, txt, reply_markup=kb, parse_mode="HTML")

def _clon_panel_callback(bot, chat_id, uid, clon, data, cb):
    token = clon["token"]
    
    if data == "m_active": clon["status"] = "active"; save_clon(token, clon); bot.send_message(chat_id, "🟢 Aktif edildi.")
    elif data == "m_passive": clon["status"] = "passive"; save_clon(token, clon); bot.send_message(chat_id, "🔴 Durduruldu.")
    elif data == "m_toggle_maint":
        clon["maintenance"] = not clon.get("maintenance", False); save_clon(token, clon)
        bot.send_message(chat_id, f"🛠 Bakım modu: {'Açık' if clon['maintenance'] else 'Kapalı'}")
    elif data == "m_manage_queries":
        kb = InlineKeyboardMarkup()
        for q_name, q_data in clon.get("queries", {}).items():
            icon = "🟢" if q_data.get("active") else "🔴"
            kb.add(InlineKeyboardButton(f"{icon} {q_name}", callback_data=f"q_edit:{q_name}"))
        kb.add(InlineKeyboardButton("➕ Yeni API Ekle", callback_data="q_add"))
        kb.add(InlineKeyboardButton("⬅️ Geri", callback_data="back_to_menu"))
        bot.send_message(chat_id, "🔗 Sorguları yönet:", reply_markup=kb)
    elif data == "q_add":
        PENDING_ACTION[uid] = {"token": token, "action": "add_query"}
        bot.send_message(chat_id, "Yeni sorgu adını girin (Örn: Ehliyet Sorgu):")
    elif data.startswith("q_edit:"):
        q_name = data.split(":")[1]
        q = clon["queries"][q_name]
        kb = InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔴 Durdur / 🟢 Başlat", callback_data=f"q_toggle:{q_name}"),
            InlineKeyboardButton("✏️ API Linkini Değiştir", callback_data=f"q_url:{q_name}"),
            InlineKeyboardButton("🗑 Sorguyu Sil", callback_data=f"q_del:{q_name}"),
            InlineKeyboardButton("⬅️ Geri", callback_data="m_manage_queries")
        )
        bot.send_message(chat_id, f"🔍 <b>{q_name}</b>\nDurum: {q.get('active')}\nLink: <code>{q.get('url')}</code>", reply_markup=kb, parse_mode="HTML")
    elif data.startswith("q_toggle:"):
        q_name = data.split(":")[1]
        clon["queries"][q_name]["active"] = not clon["queries"][q_name]["active"]
        save_clon(token, clon); bot.send_message(chat_id, "✅ Durum değiştirildi.")
    elif data.startswith("q_del:"):
        q_name = data.split(":")[1]
        clon["queries"].pop(q_name, None); save_clon(token, clon)
        bot.send_message(chat_id, "✅ Sorgu silindi.")
    elif data.startswith("q_url:"):
        q_name = data.split(":")[1]
        PENDING_ACTION[uid] = {"token": token, "action": "set_url", "q_name": q_name}
        bot.send_message(chat_id, f"<b>{q_name}</b> için yeni API linkini girin:")
        
    elif data == "m_announce": PENDING_ACTION[uid] = {"token": token, "action": "announce"}; bot.send_message(chat_id, "📣 Duyuru metnini gönder:")
    elif data == "m_ban": PENDING_ACTION[uid] = {"token": token, "action": "ban"}; bot.send_message(chat_id, "🚫 Banlanacak user ID:")
    elif data == "m_unban": PENDING_ACTION[uid] = {"token": token, "action": "unban"}; bot.send_message(chat_id, "✅ Banı kaldırılacak user ID:")
    elif data == "m_stats": bot.send_message(chat_id, f"📊 <b>Statik</b>\n\n👥 Kullanıcı: {len(clon.get('users', []))}\n🚫 Banlı DM: {len(clon.get('banned_dm', []))}", parse_mode="HTML")
    elif data == "m_restart":
        bot.send_message(chat_id, "🔄 Sistem yenileniyor... Lütfen bekleyin.")
        try:
            requests.get(f"https://api.telegram.org/bot{token}/setWebhook?url={BASE_URL}/clon/{token}", timeout=5)
            bot.send_message(chat_id, "✅ Sistem başarıyla yenilendi.")
        except:
            bot.send_message(chat_id, "❌ Yenileme sırasında hata oluştu.")

def _handle_clon_action(bot, chat_id, uid, clon, act, txt):
    token = clon["token"]; action = act["action"]
    
    if action == "add_query":
        PENDING_ACTION[uid] = {"token": token, "action": "add_url", "q_name": txt}
        bot.send_message(chat_id, f"<b>{txt}</b> için API linkini girin (Örn: http://site.com/api?tc={{tc}}):")
    elif action == "add_url":
        clon["queries"][act["q_name"]] = {"url": txt, "active": True, "hint": "11 haneli TC girin"}
        save_clon(token, clon)
        bot.send_message(chat_id, "✅ Yeni API eklendi.")
    elif action == "set_url":
        clon["queries"][act["q_name"]]["url"] = txt; save_clon(token, clon)
        bot.send_message(chat_id, "✅ API linki güncellendi.")
    elif action == "announce":
        sent = 0
        for u in clon.get("users", []):
            try: bot.send_message(u, f"📣 <b>DUYURU</b>\n\n{txt}", parse_mode="HTML"); sent += 1
            except: pass
        bot.send_message(chat_id, f"✅ {sent} kişiye gönderildi.")
    elif action == "ban":
        if txt.isdigit():
            if "banned_dm" not in clon: clon["banned_dm"] = []
            if int(txt) not in clon["banned_dm"]: clon["banned_dm"].append(int(txt))
            save_clon(token, clon)
            bot.send_message(chat_id, "🚫 Kullanıcı DM'den banlandı.")
    elif action == "unban":
        if txt.isdigit():
            if "banned_dm" in clon and int(txt) in clon["banned_dm"]:
                clon["banned_dm"].remove(int(txt))
                save_clon(token, clon)
                bot.send_message(chat_id, "✅ Ban kaldırıldı.")

# ============================================================
# 🚀 FLASK WEBHOOKS
# ============================================================
app = Flask(__name__)

@app.route("/", methods=["GET"])
def home(): return "Bot aktif."

@app.route("/master", methods=["POST"])
def master_webhook():
    try:
        update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
        master.process_new_updates([update])
        return "OK", 200
    except Exception as e: return str(e), 500

@app.route("/clon/<token>", methods=["POST"])
def clon_webhook(token):
    try:
        data = request.get_json(force=True)
        handle_clon_update(token, data)
        return "OK", 200
    except Exception as e: return str(e), 500

@app.route("/setup", methods=["GET"])
def setup():
    # Webhook'ları kur
    requests.get(f"https://api.telegram.org/bot{MASTER_TOKEN}/setWebhook?url={BASE_URL}/master")
    for t in load_db().get("clons", {}):
        try: requests.get(f"https://api.telegram.org/bot{t}/setWebhook?url={BASE_URL}/clon/{t}")
        except: pass
    return {"ok": True, "base_url": BASE_URL, "clons": len(load_db().get("clons", {}))}

@app.route("/cron", methods=["GET"])
def cron():
    # Vercel uyanık kalsın diye ping atılır
    try:
        requests.get(f"https://api.telegram.org/bot{MASTER_TOKEN}/setWebhook?url={BASE_URL}/master")
        for t in load_db().get("clons", {}):
            requests.get(f"https://api.telegram.org/bot{t}/setWebhook?url={BASE_URL}/clon/{t}")
    except: pass
    return {"status": "cron ok"}

if __name__ == "__main__": 
    app.run(host="0.0.0.0", port=5000)
