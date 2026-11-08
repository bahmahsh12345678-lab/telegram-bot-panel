import os, sys, json, time, base64, threading, requests, asyncio
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
# ⚙️ AYARLAR (KODUN İÇİNE GÖMÜLDÜ)
# ============================================================
MASTER_TOKEN = "9013867167:AAHbNDNHqW9tf4eCqCrkkErXVQRZmbVzkzQ"
MASTER_OWNER_ID = 8947359034

# GitHub Yedekleme (Verilerin silinmemesi için)
GITHUB_TOKEN = "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" # <-- BURAYA KENDİ GITHUB TOKENİNİ YAPIŞTIR
GITHUB_REPO = "bahmahsh12345678-lab/telegram-bot-panel"
GITHUB_BRANCH = "main"

# Vercel Linki (Webhook için)
VERCEL_URL = "https://babaprogamsessshostkkk.vercel.app/"

DATA_DIR = "/tmp"
DB_FILE = os.path.join(DATA_DIR, "data.json")

# ══════════════════════════════════════════
# VARSAYILAN API ADRESLERİ VE SORGULAR
# ══════════════════════════════════════════
DEFAULT_QUERIES = {
    "TC Sorgu": {"url": "https://logsuzlarsystempro.alwaysdata.net/api/tcgsm.php?tc={tc}", "active": True, "hint": "11 haneli TC girin\n📌 Örnek: <code>11111111110</code>"},
    "Ad Soyad": {"url": "https://logsuzlarsystempro.alwaysdata.net/api/adsoyad.php", "active": True, "hint": "Ad, Soyad, İl ve İlçe girin\n📌 Örnek: <code>Ahmet Yılmaz İstanbul</code>"},
    "GSM TC": {"url": "https://logsuzlarsystempro.alwaysdata.net/api/gsmtc.php?gsm={gsm}", "active": True, "hint": "10 haneli GSM girin\n📌 Örnek: <code>5422089788</code>"},
    "Aile Sorgu": {"url": "https://logsuzlarsystempro.alwaysdata.net/api/aile.php?tc={tc}", "active": True, "hint": "11 haneli TC girin"},
    "Sülale Sorgu": {"url": "https://logsuzlarsystempro.alwaysdata.net/api/sulale.php?tc={tc}", "active": True, "hint": "11 haneli TC girin"},
    "Adres Sorgu": {"url": "https://logsuzlarsystempro.alwaysdata.net/api/adres.php?tc={tc}", "active": True, "hint": "11 haneli TC girin"},
    "Sokak Sorgu": {"url": "https://logsuzlarsystempro.alwaysdata.net/api/sokak.php?tc={tc}", "active": True, "hint": "11 haneli TC girin"},
    "Tapu Sorgu": {"url": "https://logsuzlarsystempro.alwaysdata.net/api/tapu.php?tc={tc}", "active": True, "hint": "11 haneli TC girin"},
    "Ada Parsel": {"url": "https://logsuzlarsystempro.alwaysdata.net/api/adaparsel.php?il={il}&ilce={ilce}", "active": True, "hint": "İl ve İlçe girin\n📌 Örnek: <code>bursa osmangazi</code>"}
}
BAD_WORDS = ["DEVOLOPER","DEVELOPER","developer","Devoloper","sürüm","Sürüm","SURUM","version","Version","auth","Auth","altauth","@jessy_php","jessy_php","JESSY_PHP"]

# ============================================================
# 💾 VERİTABANI
# ============================================================
def load_db():
    if GITHUB_TOKEN and "senin_github" not in GITHUB_TOKEN:
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/data.json?ref={GITHUB_BRANCH}"
            r = requests.get(url, headers={"Authorization": f"token {GITHUB_TOKEN}"}, timeout=5)
            if r.status_code == 200:
                data = json.loads(base64.b64decode(r.json()["content"]).decode())
                with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(data, f)
                return data
        except: pass
    if not os.path.exists(DB_FILE):
        default = {"clons": {}, "states": {}, "queries": DEFAULT_QUERIES.copy()}
        with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(default, f)
        return default
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f: 
            d = json.load(f)
            if "queries" not in d: d["queries"] = DEFAULT_QUERIES.copy()
            return d
    except: return {"clons": {}, "states": {}, "queries": DEFAULT_QUERIES.copy()}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False)
    if GITHUB_TOKEN and "senin_github" not in GITHUB_TOKEN:
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
# 🤖 ANA BOT (Master)
# ============================================================
master = telebot.TeleBot(MASTER_TOKEN, threaded=False)
MASTER_STATE = {}

@master.message_handler(commands=["start"])
def master_start(m):
    set_state(m.from_user.id, None); MASTER_STATE.pop(m.from_user.id, None)
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🧩 Sorgu Botu Oluştur", callback_data="tpl:query"))
    if m.from_user.id == MASTER_OWNER_ID:
        kb.add(InlineKeyboardButton("👑 Master Admin Panel", callback_data="master_admin"))
    welcome_text = "🇹🇷 <b>Hoş Geldiniz!</b>\n\n🤖 Botumuz <b>7/24</b> hizmet vermekte ve <b>tamamen ücretsizdir</b>.\n\nKendi sorgu botunuzu oluşturmak için aşağıdaki butonu kullanın."
    master.send_message(m.chat.id, welcome_text, reply_markup=kb, parse_mode="HTML")

@master.callback_query_handler(func=lambda c: True)
def master_cb(c):
    uid = c.from_user.id; d = c.data; chat_id = c.message.chat.id; msg_id = c.message.message_id
    master.answer_callback_query(c.id)

    if uid == MASTER_OWNER_ID:
        if d == "master_admin":
            db = load_db()
            txt = f"👑 <b>MASTER ADMIN PANEL</b>\n\n🤖 Aktif Botlar: <b>{len(db.get('clons', {}))}</b>\n👥 Toplam Kullanıcı: <b>{sum(len(c.get('users', [])) for c in db.get('clons', {}).values())}</b>"
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("🤖 Clon Botları Yönet", callback_data="m_manage_bots"))
            kb.add(InlineKeyboardButton("🔗 Sorguları Yönet", callback_data="m_manage_queries"))
            kb.add(InlineKeyboardButton("📢 Global Duyuru", callback_data="m_global_announce"))
            kb.add(InlineKeyboardButton("⬅️ Geri", callback_data="home"))
            return master.edit_message_text(txt, chat_id, msg_id, reply_markup=kb, parse_mode="HTML")
        
        if d == "m_manage_bots":
            db = load_db(); kb = InlineKeyboardMarkup()
            for tok, clon in db.get("clons", {}).items():
                kb.add(InlineKeyboardButton(f"🤖 {clon['bot_name']}", callback_data=f"m_bot:{tok}"))
            kb.add(InlineKeyboardButton("⬅️ Geri", callback_data="master_admin"))
            return master.edit_message_text("Yönetmek istediğiniz botu seçin:", chat_id, msg_id, reply_markup=kb)
            
        if d.startswith("m_bot:"):
            tok = d.split(":")[1]; clon = get_clon(tok)
            kb = InlineKeyboardMarkup().add(
                InlineKeyboardButton("🗑 Botu Sil", callback_data=f"del_bot:{tok}"),
                InlineKeyboardButton("⬅️ Geri", callback_data="m_manage_bots")
            )
            return master.edit_message_text(f"🤖 Bot: {clon['bot_name']}\nSahip ID: {clon['owner_id']}\nKullanıcı: {len(clon.get('users', []))}", chat_id, msg_id, reply_markup=kb)
            
        if d.startswith("del_bot:"):
            tok = d.split(":")[1]; del_clon(tok)
            return master.edit_message_text("✅ Bot silindi.", chat_id, msg_id)

        if d == "m_manage_queries":
            db = load_db(); kb = InlineKeyboardMarkup()
            for q_name, q_data in db.get("queries", {}).items():
                icon = "🟢" if q_data.get("active") else "🔴"
                kb.add(InlineKeyboardButton(f"{icon} {q_name}", callback_data=f"q_edit:{q_name}"))
            kb.add(InlineKeyboardButton("➕ Yeni Sorgu Ekle", callback_data="q_add"))
            kb.add(InlineKeyboardButton("⬅️ Geri", callback_data="master_admin"))
            return master.edit_message_text("🔗 Sorguları yönet:", chat_id, msg_id, reply_markup=kb)

        if d == "q_add":
            MASTER_STATE[uid] = {"action": "add_query"}
            return master.send_message(chat_id, "Yeni sorgu adını girin (Örn: Ehliyet Sorgu):")
            
        if d.startswith("q_edit:"):
            q_name = d.split(":")[1]; db = load_db(); q = db["queries"][q_name]
            kb = InlineKeyboardMarkup().add(
                InlineKeyboardButton("🔴 Durdur / 🟢 Başlat", callback_data=f"q_toggle:{q_name}"),
                InlineKeyboardButton("✏️ API Linkini Değiştir", callback_data=f"q_url:{q_name}"),
                InlineKeyboardButton("🗑 Sorguyu Sil", callback_data=f"q_del:{q_name}"),
                InlineKeyboardButton("⬅️ Geri", callback_data="m_manage_queries")
            )
            return master.edit_message_text(f"🔍 <b>{q_name}</b>\nDurum: {q.get('active')}\nLink: <code>{q.get('url')}</code>", chat_id, msg_id, reply_markup=kb, parse_mode="HTML")

        if d.startswith("q_toggle:"):
            q_name = d.split(":")[1]; db = load_db(); db["queries"][q_name]["active"] = not db["queries"][q_name]["active"]; save_db(db)
            return master_cb(c)
            
        if d.startswith("q_url:"):
            q_name = d.split(":")[1]; MASTER_STATE[uid] = {"action": "set_url", "q_name": q_name}
            return master.send_message(chat_id, f"<b>{q_name}</b> için yeni API linkini girin:")
            
        if d.startswith("q_del:"):
            q_name = d.split(":")[1]; db = load_db(); db["queries"].pop(q_name, None); save_db(db)
            return master.edit_message_text("✅ Sorgu silindi.", chat_id, msg_id)

        if d == "m_global_announce":
            MASTER_STATE[uid] = {"action": "global_announce"}
            return master.send_message(chat_id, "📢 Tüm kullanıcılara gönderilecek duyuru metnini yaz:")

    if d == "home": master_start(c.message)
    elif d.startswith("tpl:"):
        set_state(uid, {"template": d[4:], "step": "token", "data": {}})
        master.edit_message_text("<b>Adım 1:</b> Bot Tokenini gönder:", chat_id, msg_id, parse_mode="HTML")
    elif d.startswith("fc:"):
        n = int(d[3:]); st = get_state(uid); st["data"]["forced_channels"] = []
        if n == 0:
            st["step"] = "bot_name"; set_state(uid, st)
            master.edit_message_text("<b>Adım 4:</b> Bot ismini gönder:", chat_id, msg_id, parse_mode="HTML")
        else:
            st["data"]["_fc_rem"] = n; st["step"] = "fc_link"; set_state(uid, st)
            master.edit_message_text("<b>1. kanal linkini gönder:</b>", chat_id, msg_id, parse_mode="HTML")
    elif d == "confirm_yes":
        st = get_state(uid); set_state(uid, None); _create_bot(master, uid, chat_id, st)
    elif d == "cancel":
        set_state(uid, None); MASTER_STATE.pop(uid, None)
        master.edit_message_text("❌ İptal edildi.", chat_id, msg_id)

@master.message_handler(func=lambda m: get_state(m.from_user.id) is not None or m.from_user.id in MASTER_STATE)
def master_step(m):
    uid = m.from_user.id; txt = m.text.strip() if m.text else ""
    if txt == "/iptal":
        MASTER_STATE.pop(uid, None); set_state(uid, None)
        return master.send_message(uid, "❌ İptal edildi.")

    if uid in MASTER_STATE:
        act = MASTER_STATE[uid]
        if act["action"] == "add_query":
            MASTER_STATE[uid] = {"action": "add_url", "q_name": txt}
            return master.send_message(uid, f"<b>{txt}</b> için API linkini girin (Örn: http://site.com/api?tc={{tc}}):")
        elif act["action"] == "add_url":
            db = load_db(); db["queries"][act["q_name"]] = {"url": txt, "active": True, "hint": "11 haneli TC girin"}
            save_db(db); MASTER_STATE.pop(uid, None)
            return master.send_message(uid, "✅ Yeni sorgu eklendi.")
        elif act["action"] == "set_url":
            db = load_db(); db["queries"][act["q_name"]]["url"] = txt; save_db(db)
            MASTER_STATE.pop(uid, None)
            return master.send_message(uid, "✅ API linki güncellendi.")
        elif act["action"] == "global_announce":
            MASTER_STATE.pop(uid, None); db = load_db(); sent = 0
            for clon in db.get("clons", {}).values():
                bot = telebot.TeleBot(clon["token"], threaded=False)
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
        if not txt.isdigit(): return master.send_message(m.chat.id, "❌ Sadece rakam.")
        data["owner_id"] = int(txt); st["step"] = "fc_count"; set_state(uid, st)
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Yok", callback_data="fc:0"), InlineKeyboardButton("1 Kanal", callback_data="fc:1"), InlineKeyboardButton("2 Kanal", callback_data="fc:2"))
        master.send_message(m.chat.id, "<b>Adım 3:</b> Zorunlu kanal sayısı?", reply_markup=kb, parse_mode="HTML")
    elif step == "fc_link":
        if txt.startswith("https://t.me/"): txt = "@" + txt.replace("https://t.me/", "")
        if not txt.startswith("@"): return master.send_message(m.chat.id, "❌ Format: @kanal")
        data["forced_channels"].append(txt); data["_fc_rem"] -= 1
        if data["_fc_rem"] > 0:
            set_state(uid, st); master.send_message(m.chat.id, f"<b>{len(data['forced_channels'])+1}. kanal linkini gönder:</b>", parse_mode="HTML")
        else:
            st["step"] = "bot_name"; set_state(uid, st); master.send_message(m.chat.id, "<b>Adım 4:</b> Bot ismini gönder:", parse_mode="HTML")
    elif step == "bot_name":
        data["bot_name"] = txt[:64]; st["step"] = "support"; set_state(uid, st)
        master.send_message(m.chat.id, "<b>Adım 5:</b> Destek linki (https://t.me/...):", parse_mode="HTML")
    elif step == "support":
        if not txt.startswith("https://t.me/"): return master.send_message(m.chat.id, "❌ https://t.me/... olmalı.")
        data["support"] = txt; st["step"] = "admin_username"; set_state(uid, st)
        master.send_message(m.chat.id, "<b>Adım 6:</b> Admin @kullanıcı adı (@ornek):", parse_mode="HTML")
    elif step == "admin_username":
        if not txt.startswith("@"): return master.send_message(m.chat.id, "❌ @ ile başlamalı.")
        data["admin_username"] = txt; _show_confirm(master, uid, st)

def _show_confirm(bot, uid, st):
    d = st["data"]
    txt = f"📋 <b>ÖZET</b>\n\n📦 Şablon: {st['template']}\n🤖 Bot: @{d.get('bot_username')}\n📝 İsim: {d.get('bot_name')}\n👑 Admin: <code>{d.get('owner_id')}</code>\n🩵 Destek: {d.get('support')}\n📢 Kanallar: {', '.join(d.get('forced_channels', [])) or 'Yok'}\n\n✅ Onaylıyor musun?"
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Onayla ve Kur", callback_data="confirm_yes"), InlineKeyboardButton("❌ İptal", callback_data="cancel"))
    bot.send_message(uid, txt, reply_markup=kb, parse_mode="HTML")

def _create_bot(bot, uid, chat_id, st):
    d = st["data"]
    clon = {
        "token": d["token"], "bot_username": d["bot_username"], "owner_id": d["owner_id"],
        "template": st["template"], "bot_name": d["bot_name"], "status": "active",
        "support": d.get("support", ""), "forced_channels": d.get("forced_channels", []),
        "start_text": f"👋 <b>Hoş Geldin, {{name}}!</b>\n\nAşağıdaki menüyü kullan.",
        "buttons_per_row": 2, "banned": [], "users": [], "created": datetime.now().isoformat()
    }
    save_clon(d["token"], clon)
    try:
        requests.get(f"https://api.telegram.org/bot{d['token']}/setWebhook?url={VERCEL_URL}/clon/{d['token']}", timeout=5)
        requests.post(f"https://api.telegram.org/bot{d['token']}/setMyName", json={"name": d["bot_name"]}, timeout=5)
    except: pass
    bot.send_message(chat_id, f"✅ <b>Bot başarıyla oluşturuldu!</b>\n\n🤖 <b>{d['bot_name']}</b>\n🔗 https://t.me/{d['bot_username']}\n\n<b>Kullanıcı:</b> /start\n<b>Sen:</b> /admin", parse_mode="HTML")

# ============================================================
# 🎛 CLON BOT (Gelişmiş Sorgu, TXT ve Temizleme)
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
    bot = telebot.TeleBot(token, threaded=False)

    if "message" in update:
        msg = update["message"]; chat_id = msg["chat"]["id"]; from_id = msg["from"]["id"]
        text = (msg.get("text") or "").strip(); fname = msg["from"].get("first_name", "")

        if from_id in clon.get("banned", []): return
        if clon.get("status") == "passive": return

        eksik = []
        for ch in clon.get("forced_channels", []):
            try:
                r = requests.get(f"https://api.telegram.org/bot{token}/getChatMember", params={"chat_id": ch, "user_id": from_id}).json()
                if not r.get("ok") or r["result"]["status"] in ("left", "kicked"): eksik.append(ch)
            except: eksik.append(ch)
        
        if eksik:
            kb = InlineKeyboardMarkup().add(*[InlineKeyboardButton(f"📢 {ch}", url=f"https://t.me/{ch.lstrip('@')}") for ch in eksik])
            kb.add(InlineKeyboardButton("✅ Katıldım", callback_data="check_join"))
            return bot.send_message(chat_id, "⚠️ <b>Kanallara katılman gerekiyor!</b>", reply_markup=kb, parse_mode="HTML")

        if text == "/start":
            if from_id not in clon.get("users", []):
                clon["users"].append(from_id); save_clon(token, clon)
            
            db_queries = load_db().get("queries", DEFAULT_QUERIES)
            active_queries = [q for q, v in db_queries.items() if v.get("active", True)]
            
            per_row = clon.get("buttons_per_row", 2)
            kb = InlineKeyboardMarkup(row_width=per_row)
            for q_name in active_queries:
                kb.add(InlineKeyboardButton(f"🔍 {q_name}", callback_data=f"q_{q_name}"))
            
            if clon.get("support"): kb.add(InlineKeyboardButton("🩵 Destek", url=clon["support"]))
            
            bot.send_message(chat_id, clon.get("start_text", "Hoş geldin!").replace("{name}", fname), reply_markup=kb, parse_mode="HTML")
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
                db_queries = load_db().get("queries", DEFAULT_QUERIES)
                q_data = db_queries.get(query_type)
                if not q_data or not q_data.get("active"):
                    return bot.edit_message_text("❌ Bu sorgu şu anda devre dışı.", chat_id, status.message_id)

                url = q_data["url"]; parts = text.split(); params = {}
                if query_type == "Ad Soyad":
                    if len(parts) < 2: return bot.edit_message_text("❌ Ad ve Soyad girin.", chat_id, status.message_id)
                    params["ad"], params["soyad"] = parts[0], parts[1]; params["il"] = parts[2] if len(parts) >= 3 else ""; params["ilce"] = " ".join(parts[3:]) if len(parts) >= 4 else ""
                elif query_type == "GSM TC":
                    clean_gsm = "".join(filter(str.isdigit, text)); url = url.format(gsm=clean_gsm[1:] if clean_gsm.startswith("0") else clean_gsm)
                elif query_type == "Ada Parsel":
                    if len(parts) < 2: return bot.edit_message_text("❌ İl ve İlçe girin.", chat_id, status.message_id)
                    url = url.format(il=parts[0], ilce=" ".join(parts[1:]))
                else:
                    if "{tc}" in url: url = url.format(tc="".join(filter(str.isdigit, text)))

                r = requests.get(url, params=params, timeout=None)
                data = clean_response(r.text)
                if isinstance(data, dict) and data.get("hata"): return bot.edit_message_text(f"❌ Hata: {data.get('hata')}", chat_id, status.message_id)

                fn = f"sorgu_{int(time.time())}.json"
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
        
        if data == "check_join": return bot.send_message(chat_id, "✅ Onaylandı! /start yaz.")
        
        if data == "back_to_menu":
            try: bot.delete_message(chat_id, msg_id)
            except: pass
            db_queries = load_db().get("queries", DEFAULT_QUERIES)
            active_queries = [q for q, v in db_queries.items() if v.get("active", True)]
            per_row = clon.get("buttons_per_row", 2)
            kb = InlineKeyboardMarkup(row_width=per_row)
            for q_name in active_queries: kb.add(InlineKeyboardButton(f"🔍 {q_name}", callback_data=f"q_{q_name}"))
            if clon.get("support"): kb.add(InlineKeyboardButton("🩵 Destek", url=clon["support"]))
            return bot.send_message(chat_id, "🏠 Ana Menü:", reply_markup=kb)
            
        if data.startswith("q_"):
            q_name = data[2:]
            if "active_query" not in clon: clon["active_query"] = {}
            clon["active_query"][str(from_id)] = q_name; save_clon(token, clon)
            
            db_queries = load_db().get("queries", DEFAULT_QUERIES)
            hint = db_queries.get(q_name, {}).get("hint", "Lütfen gerekli bilgiyi girin:")
            
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ İptal", callback_data="back_to_menu"))
            return bot.edit_message_text(f"🔍 <b>{q_name}</b>\n\n{hint}", chat_id, msg_id, parse_mode="HTML", reply_markup=kb)
            
        if from_id == clon["owner_id"] and data.startswith("m_"): _clon_panel_callback(bot, chat_id, clon, data, cb)

def _show_clon_panel(bot, chat_id, clon):
    emoji = {"active": "🟢", "passive": "🔴"}.get(clon["status"], "⚪")
    txt = (f"🎛 <b>Bot Yönetim Paneli</b>\n\n🤖 <b>{clon['bot_name']}</b>\n"
           f"🆔 @{clon['bot_username']}\n👥 Kullanıcı: <b>{len(clon.get('users', []))}</b>\n📊 Durum: {emoji} <b>{clon['status']}</b>")
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("▶️ Aktif", callback_data="m_active"), InlineKeyboardButton("⏸ Durdur", callback_data="m_passive"))
    kb.add(InlineKeyboardButton("✏️ İsim", callback_data="m_name"), InlineKeyboardButton("🎨 Başlangıç", callback_data="m_start"))
    kb.add(InlineKeyboardButton("🩵 Destek", callback_data="m_support"), InlineKeyboardButton("📢 Kanal", callback_data="m_channel"))
    kb.add(InlineKeyboardButton("🔒 Zorunlu Kanal", callback_data="m_forced"))
    kb.add(InlineKeyboardButton("🔘 Buton Düzeni", callback_data="m_buttons"))
    kb.add(InlineKeyboardButton("📣 Duyuru", callback_data="m_announce"))
    kb.add(InlineKeyboardButton("🚫 Ban", callback_data="m_ban"), InlineKeyboardButton("📊 Statik", callback_data="m_stats"))
    kb.add(InlineKeyboardButton("🗑 Botu Sil", callback_data="m_del"))
    bot.send_message(chat_id, txt, reply_markup=kb, parse_mode="HTML")

def _clon_panel_callback(bot, chat_id, clon, data, cb):
    token = clon["token"]; uid = cb["from"]["id"]
    if data == "m_active": clon["status"] = "active"; save_clon(token, clon); bot.send_message(chat_id, "🟢 Aktif edildi.")
    elif data == "m_passive": clon["status"] = "passive"; save_clon(token, clon); bot.send_message(chat_id, "🔴 Durduruldu.")
    elif data == "m_name": PENDING_ACTION[uid] = {"token": token, "action": "name"}; bot.send_message(chat_id, "✏️ Yeni bot ismini gönder:")
    elif data == "m_start": PENDING_ACTION[uid] = {"token": token, "action": "start"}; bot.send_message(chat_id, "🎨 Yeni başlangıç metnini gönder (HTML):")
    elif data == "m_support": PENDING_ACTION[uid] = {"token": token, "action": "support"}; bot.send_message(chat_id, "🩵 Yeni destek linki (t.me/...):")
    elif data == "m_channel": PENDING_ACTION[uid] = {"token": token, "action": "channel"}; bot.send_message(chat_id, "📢 Yeni kanal linki (t.me/...):")
    elif data == "m_forced": PENDING_ACTION[uid] = {"token": token, "action": "forced"}; bot.send_message(chat_id, "🔒 Zorunlu kanallar (virgülle): @kanal1,@kanal2\nTemizlemek için: sil")
    elif data == "m_buttons":
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("1'li", callback_data="m_btn_1"), InlineKeyboardButton("2'li", callback_data="m_btn_2"), InlineKeyboardButton("3'lü", callback_data="m_btn_3"), InlineKeyboardButton("4'lü", callback_data="m_btn_4"))
        bot.send_message(chat_id, "🔘 Menüde butonlar kaçar kaçar dizilsin?", reply_markup=kb)
    elif data.startswith("m_btn_"):
        num = int(data.split("_")[-1])
        clon["buttons_per_row"] = num; save_clon(token, clon)
        bot.send_message(chat_id, f"✅ Butonlar {num}'li olarak ayarlandı. /start ile test edin.")
    elif data == "m_announce": PENDING_ACTION[uid] = {"token": token, "action": "announce"}; bot.send_message(chat_id, "📣 Duyuru metnini gönder:")
    elif data == "m_ban": PENDING_ACTION[uid] = {"token": token, "action": "ban"}; bot.send_message(chat_id, "🚫 Banlanacak user ID:")
    elif data == "m_stats": bot.send_message(chat_id, f"📊 <b>Statik</b>\n\n👥 Kullanıcı: {len(clon.get('users', []))}\n🚫 Banlı: {len(clon.get('banned', []))}", parse_mode="HTML")
    elif data == "m_del": del_clon(token); bot.send_message(chat_id, "🗑 Bot silindi.")

def handle_pending_action(token, update):
    msg = update.get("message", {})
    uid = msg.get("from", {}).get("id")
    chat_id = msg.get("chat", {}).get("id")
    txt = (msg.get("text") or "").strip()
    if uid not in PENDING_ACTION: return False
    act = PENDING_ACTION.pop(uid)
    clon = get_clon(act["token"])
    if not clon: return True
    action = act["action"]
    if action == "name":
        clon["bot_name"] = txt[:64]
        try: requests.post(f"https://api.telegram.org/bot{clon['token']}/setMyName", json={"name": txt[:64]}, timeout=5)
        except: pass
    elif action == "start": clon["start_text"] = txt
    elif action == "support": clon["support"] = txt
    elif action == "channel": clon["channel"] = txt
    elif action == "forced":
        if txt.lower() == "sil": clon["forced_channels"] = []
        else: clon["forced_channels"] = [x.strip() for x in txt.split(",") if x.strip()]
    elif action == "announce":
        sent = 0; bot = telebot.TeleBot(act["token"])
        for u in clon.get("users", []):
            try: bot.send_message(u, f"📣 {txt}"); sent += 1
            except: pass
        save_clon(act["token"], clon); bot.send_message(chat_id, f"✅ {sent} kişiye gönderildi."); return True
    elif action == "ban":
        if txt.isdigit():
            if "banned" not in clon: clon["banned"] = []
            if int(txt) not in clon["banned"]: clon["banned"].append(int(txt))
    save_clon(act["token"], clon)
    telebot.TeleBot(act["token"]).send_message(chat_id, "✅ Kaydedildi.")
    return True

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
        if "message" in data:
            if data["message"]["from"]["id"] in PENDING_ACTION:
                handle_pending_action(token, data); return "OK", 200
        handle_clon_update(token, data)
        return "OK", 200
    except Exception as e: return str(e), 500

@app.route("/setup", methods=["GET"])
def setup():
    r = requests.get(f"https://api.telegram.org/bot{MASTER_TOKEN}/setWebhook?url={VERCEL_URL}/master")
    for t in load_db().get("clons", {}):
        try: requests.get(f"https://api.telegram.org/bot{t}/setWebhook?url={VERCEL_URL}/clon/{t}")
        except: pass
    return {"ok": True, "clons": len(load_db().get("clons", {}))}

@app.route("/cron", methods=["GET"])
def cron():
    try:
        requests.get(f"https://api.telegram.org/bot{MASTER_TOKEN}/setWebhook?url={VERCEL_URL}/master")
        for t in load_db().get("clons", {}):
            requests.get(f"https://api.telegram.org/bot{t}/setWebhook?url={VERCEL_URL}/clon/{t}")
    except: pass
    return {"status": "cron ok"}

if __name__ == "__main__": app.run(host="0.0.0.0", port=5000)
