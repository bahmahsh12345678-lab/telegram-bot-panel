# ============================================================
# 🤖 MULTI-BOT SYSTEM - VERCEL (Tek Dosya, JSON DB, GitHub Backup)
# ============================================================
import os, sys, json, time, uuid, random, string, base64, threading, re
from datetime import datetime
import requests

try:
    import telebot
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    from flask import Flask, request
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install",
                           "pyTelegramBotAPI", "requests", "flask"])
    import telebot
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    from flask import Flask, request

# ============================================================
# ⚙️ AYARLAR
# ============================================================
MASTER_TOKEN = os.environ.get("MASTER_TOKEN", "9013867167:AAFY078asKpu325681EmbprfaRBDoHz5IFA")
MASTER_OWNER_ID = int(os.environ.get("MASTER_OWNER_ID", "8947359034"))
VERCEL_URL = os.environ.get("VERCEL_URL", "https://senin-projen.vercel.app")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")

DATA_DIR = "/tmp"
DB_FILE = os.path.join(DATA_DIR, "data.json")

# ============================================================
# 💾 JSON DB + GitHub Yedekleme
# ============================================================
def load_db():
    # GitHub'dan çek
    if GITHUB_TOKEN and GITHUB_REPO:
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/data.json?ref={GITHUB_BRANCH}"
            r = requests.get(url, headers={"Authorization": f"token {GITHUB_TOKEN}"}, timeout=5)
            if r.status_code == 200:
                data = json.loads(base64.b64decode(r.json()["content"]).decode())
                with open(DB_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f)
                return data
        except:
            pass

    if not os.path.exists(DB_FILE):
        default = {"clons": {}, "states": {}}
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(default, f)
        return default
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"clons": {}, "states": {}}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    # GitHub'a yedekle
    if GITHUB_TOKEN and GITHUB_REPO:
        def _backup():
            try:
                url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/data.json"
                headers = {"Authorization": f"token {GITHUB_TOKEN}"}
                r = requests.get(url, headers=headers, timeout=5)
                sha = r.json().get("sha") if r.status_code == 200 else None
                content = base64.b64encode(json.dumps(data, indent=2).encode()).decode()
                payload = {"message": "bot data update", "content": content, "branch": GITHUB_BRANCH}
                if sha:
                    payload["sha"] = sha
                requests.put(url, headers=headers, json=payload, timeout=5)
            except:
                pass
        threading.Thread(target=_backup, daemon=True).start()

def get_clon(token):
    return load_db()["clons"].get(token)

def save_clon(token, clon):
    db = load_db()
    db["clons"][token] = clon
    save_db(db)

def del_clon(token):
    db = load_db()
    db["clons"].pop(token, None)
    save_db(db)

def all_clons():
    return load_db()["clons"]

def get_state(uid):
    return load_db()["states"].get(str(uid))

def set_state(uid, state):
    db = load_db()
    if state is None:
        db["states"].pop(str(uid), None)
    else:
        db["states"][str(uid)] = state
    save_db(db)

# ============================================================
# 📦 ŞABLONLAR
# ============================================================
TEMPLATES = {
    "sms":        {"emoji": "📨", "name": "SMS Bomber", "desc": "Numaraya toplu SMS"},
    "market":     {"emoji": "🛒", "name": "Market Bot", "desc": "Ref ile ürün sat"},
    "protection": {"emoji": "🛡", "name": "Koruma Bot", "desc": "Grup koruma"},
    "query":      {"emoji": "🔍", "name": "Sorgu Bot", "desc": "TC/GSM sorgu"},
    "cekilis":    {"emoji": "🎉", "name": "Çekiliş Bot", "desc": "Kanala çekiliş"},
    "otp":        {"emoji": "📨", "name": "OTP Bot", "desc": "OTP topla"},
}

# ============================================================
# 🤖 ANA BOT
# ============================================================
master = telebot.TeleBot(MASTER_TOKEN, threaded=False)

def master_menu():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📖 Yardım", callback_data="help"),
           InlineKeyboardButton("🤖 Bot Kullanımı", callback_data="usage"))
    kb.add(InlineKeyboardButton("📢 Kanal", url="https://t.me/logsuzlarpanelvip"))
    kb.add(InlineKeyboardButton("🧩 Şablon Seç", callback_data="templates"))
    kb.add(InlineKeyboardButton("🤖 Botlarım", callback_data="my_bots"))
    return kb

@master.message_handler(commands=["start"])
def master_start(m):
    set_state(m.from_user.id, None)
    master.send_message(m.chat.id,
        "🇹🇷 <b>Hoş geldin!</b>\n\n"
        "Kendi Telegram botunu oluşturmak için aşağıdan başla.",
        reply_markup=master_menu())

@master.callback_query_handler(func=lambda c: True)
def master_cb(c):
    uid = c.from_user.id
    d = c.data
    chat_id = c.message.chat.id
    msg_id = c.message.message_id
    master.answer_callback_query(c.id)

    if d == "help":
        master.send_message(chat_id,
            "📖 <b>Yardım</b>\n\n"
            "1️⃣ Şablon seç\n"
            "2️⃣ Bot Token gönder\n"
            "3️⃣ Admin ID gönder\n"
            "4️⃣ Zorunlu kanal (0/1/2)\n"
            "5️⃣ Bot ismi\n"
            "6️⃣ Destek linki\n"
            "7️⃣ Admin @kullanıcı\n"
            "8️⃣ Onayla → Bot hazır!")
    elif d == "usage":
        master.send_message(chat_id,
            "🤖 Botun oluşunca:\n"
            "• Kullanıcılar <code>/start</code> yazar\n"
            "• Sen <code>/admin</code> ile paneli açarsın")
    elif d == "templates":
        kb = InlineKeyboardMarkup()
        for k, t in TEMPLATES.items():
            kb.add(InlineKeyboardButton(f"{t['emoji']} {t['name']}", callback_data=f"tpl:{k}"))
        kb.add(InlineKeyboardButton("⬅️ Geri", callback_data="home"))
        master.edit_message_text("🧩 <b>Bir şablon seç</b>", chat_id, msg_id, reply_markup=kb)
    elif d == "home":
        master.edit_message_text("🏠 Ana Menü", chat_id, msg_id, reply_markup=master_menu())
    elif d == "my_bots":
        bots = [c for c in all_clons().values() if c.get("owner_id") == uid]
        if not bots:
            master.send_message(chat_id, "📭 Henüz botun yok.")
            return
        txt = "🤖 <b>Botların</b>\n\n"
        for b in bots:
            txt += f"• <b>{b['bot_name']}</b> (@{b['bot_username']}) — {TEMPLATES.get(b['template'],{}).get('name','?')}\n"
        master.send_message(chat_id, txt)
    elif d.startswith("tpl:"):
        template = d[4:]
        set_state(uid, {"template": template, "step": "token", "data": {}})
        master.edit_message_text(
            f"{TEMPLATES[template]['emoji']} <b>{TEMPLATES[template]['name']}</b>\n\n"
            f"<b>Adım 1:</b> Bot Tokenini gönder (BotFather'dan):\n"
            f"<code>123456:ABC...</code>", chat_id, msg_id)
    elif d.startswith("fc:"):
        n = int(d[3:])
        st = get_state(uid)
        if not st:
            return
        st["data"]["forced_channels"] = []
        if n == 0:
            st["step"] = "bot_name"
            set_state(uid, st)
            master.edit_message_text("<b>Adım 4:</b> Bot ismini gönder:", chat_id, msg_id)
        else:
            st["data"]["_fc_rem"] = n
            st["step"] = "fc_link"
            set_state(uid, st)
            master.edit_message_text(
                "<b>1. kanal linkini gönder:</b>\n"
                "<code>@kanal</code> veya <code>https://t.me/kanal</code>",
                chat_id, msg_id)
    elif d == "confirm_yes":
        st = get_state(uid)
        set_state(uid, None)
        _create_bot(master, uid, chat_id, st)
    elif d == "cancel":
        set_state(uid, None)
        master.edit_message_text("❌ İptal edildi.", chat_id, msg_id, reply_markup=master_menu())

@master.message_handler(func=lambda m: get_state(m.from_user.id) is not None)
def master_step(m):
    uid = m.from_user.id
    st = get_state(uid)
    if not st or "step" not in st:
        return
    step = st["step"]
    data = st["data"]
    txt = m.text.strip() if m.text else ""

    if step == "token":
        if ":" not in txt:
            master.send_message(m.chat.id, "❌ Geçersiz token.")
            return
        try:
            r = requests.get(f"https://api.telegram.org/bot{txt}/getMe", timeout=5).json()
            if not r.get("ok"):
                master.send_message(m.chat.id, "❌ Token doğrulanamadı.")
                return
            data["token"] = txt
            data["bot_username"] = r["result"]["username"]
        except:
            master.send_message(m.chat.id, "❌ Hata, tekrar dene.")
            return
        st["step"] = "admin_id"
        set_state(uid, st)
        master.send_message(m.chat.id, "<b>Adım 2:</b> Admin ID'ni gönder:\n<code>123456789</code>")

    elif step == "admin_id":
        if not txt.isdigit():
            master.send_message(m.chat.id, "❌ Sadece rakam.")
            return
        data["owner_id"] = int(txt)
        st["step"] = "fc_count"
        set_state(uid, st)
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("❌ Yok", callback_data="fc:0"))
        kb.add(InlineKeyboardButton("1️⃣ 1 Kanal", callback_data="fc:1"))
        kb.add(InlineKeyboardButton("2️⃣ 2 Kanal", callback_data="fc:2"))
        master.send_message(m.chat.id, "<b>Adım 3:</b> Zorunlu kanal sayısı?", reply_markup=kb)

    elif step == "fc_link":
        if txt.startswith("https://t.me/"):
            txt = "@" + txt.replace("https://t.me/", "")
        if not txt.startswith("@"):
            master.send_message(m.chat.id, "❌ Format: @kanal veya t.me/kanal")
            return
        data["forced_channels"].append(txt)
        data["_fc_rem"] -= 1
        if data["_fc_rem"] > 0:
            set_state(uid, st)
            master.send_message(m.chat.id, f"<b>{len(data['forced_channels'])+1}. kanal linkini gönder:</b>")
        else:
            st["step"] = "bot_name"
            set_state(uid, st)
            master.send_message(m.chat.id, "<b>Adım 4:</b> Bot ismini gönder:")

    elif step == "bot_name":
        data["bot_name"] = txt[:64]
        st["step"] = "support"
        set_state(uid, st)
        master.send_message(m.chat.id, "<b>Adım 5:</b> Destek linki (t.me/...):")

    elif step == "support":
        if not txt.startswith("https://t.me/"):
            master.send_message(m.chat.id, "❌ https://t.me/... olmalı.")
            return
        data["support"] = txt
        st["step"] = "admin_username"
        set_state(uid, st)
        master.send_message(m.chat.id, "<b>Adım 6:</b> Admin @kullanıcı adı (@ornek):")

    elif step == "admin_username":
        if not txt.startswith("@"):
            master.send_message(m.chat.id, "❌ @ ile başlamalı.")
            return
        data["admin_username"] = txt
        if st["template"] == "otp":
            st["step"] = "otp_channel_id"
            set_state(uid, st)
            master.send_message(m.chat.id, "<b>Adım 7:</b> OTP Kanal ID (-100...):")
        else:
            _show_confirm(master, uid, st)

    elif step == "otp_channel_id":
        if not txt.startswith("-100"):
            master.send_message(m.chat.id, "❌ -100 ile başlamalı.")
            return
        data["otp_channel_id"] = txt
        st["step"] = "otp_channel_username"
        set_state(uid, st)
        master.send_message(m.chat.id, "<b>Adım 8:</b> OTP Kanal @kullanıcı adı:")

    elif step == "otp_channel_username":
        if not txt.startswith("@"):
            master.send_message(m.chat.id, "❌ @ ile başlamalı.")
            return
        data["otp_channel_username"] = txt
        _show_confirm(master, uid, st)

def _show_confirm(bot, uid, st):
    d = st["data"]
    txt = (
        f"📋 <b>ÖZET</b>\n\n"
        f"📦 Şablon: {TEMPLATES[st['template']]['name']}\n"
        f"🤖 Bot: @{d.get('bot_username')}\n"
        f"📝 İsim: {d.get('bot_name')}\n"
        f"👑 Admin: <code>{d.get('owner_id')}</code>\n"
        f"🩵 Destek: {d.get('support')}\n"
        f"👤 Admin @: {d.get('admin_username')}\n"
        f"📢 Kanallar: {', '.join(d.get('forced_channels', [])) or 'Yok'}"
    )
    if st["template"] == "otp":
        txt += f"\n📨 OTP: <code>{d.get('otp_channel_id')}</code> {d.get('otp_channel_username')}"
    txt += "\n\n✅ Onaylıyor musun?"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Onayla ve Kur", callback_data="confirm_yes"))
    kb.add(InlineKeyboardButton("❌ İptal", callback_data="cancel"))
    bot.send_message(uid, txt, reply_markup=kb)

def _create_bot(bot, uid, chat_id, st):
    d = st["data"]
    token = d["token"]

    clon = {
        "token": token,
        "bot_username": d["bot_username"],
        "owner_id": d["owner_id"],
        "template": st["template"],
        "bot_name": d["bot_name"],
        "status": "active",
        "support": d.get("support", ""),
        "channel": "",
        "developer": "",
        "forced_channels": d.get("forced_channels", []),
        "admin_username": d.get("admin_username", ""),
        "start_text": f"👋 <b>Hoş geldin!</b>\n\n<b>{d['bot_name']}</b>'a hoş geldin.",
        "buttons": [],
        "otp_channel_id": d.get("otp_channel_id", ""),
        "otp_channel_username": d.get("otp_channel_username", ""),
        "banned": [],
        "users": [],
        "created": datetime.now().isoformat(),
    }

    save_clon(token, clon)

    # Webhook kur
    webhook_url = f"{VERCEL_URL}/clon/{token}"
    try:
        requests.get(f"https://api.telegram.org/bot{token}/setWebhook?url={webhook_url}", timeout=10)
    except:
        pass

    # Bot ismini ayarla
    try:
        requests.post(f"https://api.telegram.org/bot{token}/setMyName",
                      json={"name": d["bot_name"]}, timeout=5)
    except:
        pass

    bot.send_message(chat_id,
        f"✅ <b>Bot başarıyla oluşturuldu!</b>\n\n"
        f"🤖 <b>{d['bot_name']}</b>\n"
        f"🔗 https://t.me/{d['bot_username']}\n\n"
        f"<b>Kullanıcı:</b> /start\n"
        f"<b>Sen (admin):</b> /admin")

# ============================================================
# 🎛 CLON BOT HANDLER (panel + kullanıcı menüsü)
# ============================================================
def handle_clon_update(token, update):
    clon = get_clon(token)
    if not clon:
        return

    bot = telebot.TeleBot(token, threaded=False)

    # ────── MESAJ ──────
    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        from_id = msg["from"]["id"]
        text = (msg.get("text") or "").strip()

        # Kanal kontrolü
        if not _check_channel(bot, clon, from_id):
            kb = InlineKeyboardMarkup()
            for ch in clon.get("forced_channels", []):
                kb.add(InlineKeyboardButton(f"📢 {ch}", url=f"https://t.me/{ch.lstrip('@')}"))
            kb.add(InlineKeyboardButton("✅ Katıldım", callback_data="check_join"))
            bot.send_message(chat_id, "⚠️ Önce kanallara katıl:", reply_markup=kb)
            return

        if text == "/start":
            # kullanıcı kaydı
            db = load_db()
            users = clon.get("users", [])
            if from_id not in users:
                users.append(from_id)
                clon["users"] = users
                db["clons"][token] = clon
                save_db(db)

            bot.send_message(chat_id, clon.get("start_text", "Hoş geldin!"),
                             reply_markup=_clon_user_menu(clon))

        elif text == "/admin":
            if from_id != clon["owner_id"]:
                bot.send_message(chat_id, "❌ Bu botun admini değilsin.")
                return
            _show_clon_panel(bot, chat_id, clon)

        # Şablon komutları
        elif text.startswith("/sms") and clon["template"] == "sms":
            try:
                number = text.split()[1]
                bot.send_message(chat_id, f"📨 {number} için SMS gönderiliyor...")
            except:
                bot.send_message(chat_id, "Örnek: /sms 5551234567")

    # ────── CALLBACK ──────
    elif "callback_query" in update:
        cb = update["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        from_id = cb["from"]["id"]
        data = cb["data"]
        bot.answer_callback_query(cb["id"])

        if data == "check_join":
            if _check_channel(bot, clon, from_id):
                bot.send_message(chat_id, "✅ Onaylandı! /start tekrar yaz.")
            else:
                bot.send_message(chat_id, "❌ Hâlâ eksik kanallar var.")
            return

        # Admin panel callback'leri
        if from_id == clon["owner_id"] and data.startswith("m_"):
            _clon_panel_callback(bot, chat_id, clon, data, cb)

def _check_channel(bot, clon, uid):
    if uid == clon["owner_id"]:
        return True
    for ch in clon.get("forced_channels", []):
        try:
            r = bot.get_chat_member(ch, uid)
            if r.status in ("left", "kicked"):
                return False
        except:
            return False
    return True

def _clon_user_menu(clon):
    kb = InlineKeyboardMarkup()
    tpl = clon["template"]
    if tpl == "sms":
        kb.add(InlineKeyboardButton("📨 SMS Gönder", callback_data="u_sms"))
    elif tpl == "market":
        kb.add(InlineKeyboardButton("👤 Profilim", callback_data="u_profile"),
               InlineKeyboardButton("🛒 Market", callback_data="u_market"))
    elif tpl == "query":
        kb.add(InlineKeyboardButton("🔍 Sorgu Yap", callback_data="u_query"))
    elif tpl == "cekilis":
        kb.add(InlineKeyboardButton("➕ Çekiliş", callback_data="u_cekilis"))
    elif tpl == "otp":
        kb.add(InlineKeyboardButton("📲 Numara Al", callback_data="u_otp"))
    elif tpl == "protection":
        kb.add(InlineKeyboardButton("📢 Gruba Ekle",
                url=f"https://t.me/{clon['bot_username']}?startgroup=0"))
    if clon.get("support"):
        kb.add(InlineKeyboardButton("🩵 Destek", url=clon["support"]))
    if clon.get("channel"):
        kb.add(InlineKeyboardButton("📢 Kanal", url=clon["channel"]))
    return kb

def _show_clon_panel(bot, chat_id, clon):
    emoji = {"active": "🟢", "passive": "🔴", "maintenance": "🛠"}.get(clon["status"], "⚪")
    txt = (
        f"🎛 <b>Bot Yönetim Paneli</b>\n\n"
        f"🤖 <b>{clon['bot_name']}</b>\n"
        f"🆔 @{clon['bot_username']}\n"
        f"📦 {TEMPLATES.get(clon['template'],{}).get('name','?')}\n"
        f"👥 Kullanıcı: <b>{len(clon.get('users', []))}</b>\n"
        f"📊 Durum: {emoji} <b>{clon['status']}</b>"
    )
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("▶️ Aktif", callback_data="m_active"),
           InlineKeyboardButton("⏸ Durdur", callback_data="m_passive"))
    kb.add(InlineKeyboardButton("✏️ İsim Değiştir", callback_data="m_name"),
           InlineKeyboardButton("🎨 Başlangıç", callback_data="m_start"))
    kb.add(InlineKeyboardButton("🩵 Destek", callback_data="m_support"),
           InlineKeyboardButton("📢 Kanal", callback_data="m_channel"))
    kb.add(InlineKeyboardButton("🔒 Zorunlu Kanal", callback_data="m_forced"))
    kb.add(InlineKeyboardButton("📣 Duyuru", callback_data="m_announce"))
    kb.add(InlineKeyboardButton("🚫 Ban", callback_data="m_ban"))
    kb.add(InlineKeyboardButton("📊 Statik", callback_data="m_stats"))
    kb.add(InlineKeyboardButton("🗑 Botu Sil", callback_data="m_del"))
    bot.send_message(chat_id, txt, reply_markup=kb)

# ────── CLON PANEL İŞLEMLERİ ──────
PENDING_ACTION = {}   # uid -> {"token","action"}

def _clon_panel_callback(bot, chat_id, clon, data, cb):
    token = clon["token"]
    uid = cb["from"]["id"]

    if data == "m_active":
        _update_clon(token, status="active")
        bot.send_message(chat_id, "🟢 Aktif edildi.")
    elif data == "m_passive":
        _update_clon(token, status="passive")
        bot.send_message(chat_id, "🔴 Durduruldu.")
    elif data == "m_name":
        PENDING_ACTION[uid] = {"token": token, "action": "name"}
        bot.send_message(chat_id, "✏️ Yeni bot ismini gönder:")
    elif data == "m_start":
        PENDING_ACTION[uid] = {"token": token, "action": "start"}
        bot.send_message(chat_id, "🎨 Yeni başlangıç metnini gönder (HTML destekli):")
    elif data == "m_support":
        PENDING_ACTION[uid] = {"token": token, "action": "support"}
        bot.send_message(chat_id, "🩵 Yeni destek linki (t.me/...):")
    elif data == "m_channel":
        PENDING_ACTION[uid] = {"token": token, "action": "channel"}
        bot.send_message(chat_id, "📢 Yeni kanal linki (t.me/...):")
    elif data == "m_forced":
        PENDING_ACTION[uid] = {"token": token, "action": "forced"}
        bot.send_message(chat_id, "🔒 Zorunlu kanallar (virgülle): @kanal1,@kanal2\nTemizlemek için: sil")
    elif data == "m_announce":
        PENDING_ACTION[uid] = {"token": token, "action": "announce"}
        bot.send_message(chat_id, "📣 Duyuru metnini gönder:")
    elif data == "m_ban":
        PENDING_ACTION[uid] = {"token": token, "action": "ban"}
        bot.send_message(chat_id, "🚫 Banlanacak user ID:")
    elif data == "m_stats":
        bot.send_message(chat_id,
            f"📊 <b>Statik</b>\n\n"
            f"👥 Kullanıcı: {len(clon.get('users', []))}\n"
            f"🚫 Banlı: {len(clon.get('banned', []))}\n"
            f"📅 Kurulma: {clon.get('created', '')[:10]}")
    elif data == "m_del":
        del_clon(token)
        bot.send_message(chat_id, "🗑 Bot silindi.")

def _update_clon(token, **kw):
    db = load_db()
    if token not in db["clons"]:
        return
    db["clons"][token].update(kw)
    save_db(db)

# ────── PENDING ACTIONS (panelden text input) ──────
def handle_pending_action(token, update):
    msg = update.get("message", {})
    uid = msg.get("from", {}).get("id")
    chat_id = msg.get("chat", {}).get("id")
    txt = (msg.get("text") or "").strip()

    if uid not in PENDING_ACTION:
        return False

    act = PENDING_ACTION.pop(uid)
    clon = get_clon(act["token"])
    if not clon:
        return True

    action = act["action"]
    if action == "name":
        clon["bot_name"] = txt[:64]
        try:
            requests.post(f"https://api.telegram.org/bot{clon['token']}/setMyName",
                          json={"name": txt[:64]}, timeout=5)
        except:
            pass
    elif action == "start":
        clon["start_text"] = txt
    elif action == "support":
        clon["support"] = txt
    elif action == "channel":
        clon["channel"] = txt
    elif action == "forced":
        if txt.lower() == "sil":
            clon["forced_channels"] = []
        else:
            clon["forced_channels"] = [x.strip() for x in txt.split(",") if x.strip()]
    elif action == "announce":
        sent = 0
        bot = telebot.TeleBot(act["token"])
        for u in clon.get("users", []):
            try:
                bot.send_message(u, f"📣 {txt}")
                sent += 1
            except:
                pass
        save_clon(act["token"], clon)
        bot.send_message(chat_id, f"✅ {sent} kişiye gönderildi.")
        return True
    elif action == "ban":
        if txt.isdigit():
            banned = clon.get("banned", [])
            if int(txt) not in banned:
                banned.append(int(txt))
                clon["banned"] = banned

    save_clon(act["token"], clon)
    bot = telebot.TeleBot(act["token"])
    bot.send_message(chat_id, "✅ Kaydedildi.")
    return True

# ============================================================
# 🚀 FLASK WEBHOOKS
# ============================================================
app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return {"status": "ok", "clons": len(all_clons())}

@app.route("/master", methods=["POST"])
def master_webhook():
    try:
        update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
        master.process_new_updates([update])
        return "OK", 200
    except Exception as e:
        return str(e), 500

@app.route("/clon/<token>", methods=["POST"])
def clon_webhook(token):
    try:
        data = request.get_json(force=True)
        # Önce pending action kontrolü
        if "message" in data:
            uid = data["message"]["from"]["id"]
            if uid in PENDING_ACTION:
                handle_pending_action(token, data)
                return "OK", 200
        handle_clon_update(token, data)
        return "OK", 200
    except Exception as e:
        return str(e), 500

@app.route("/setup", methods=["GET"])
def setup():
    """İlk deploydan sonra 1 kere çalıştır — webhook kurar"""
    r = requests.get(f"https://api.telegram.org/bot{MASTER_TOKEN}/setWebhook?url={VERCEL_URL}/master")
    # tüm clonları da webhook'a al
    for t, c in all_clons().items():
        try:
            requests.get(f"https://api.telegram.org/bot{t}/setWebhook?url={VERCEL_URL}/clon/{t}")
        except:
            pass
    return {"master": r.json(), "clons": len(all_clons())}

@app.route("/cron", methods=["GET"])
def cron():
    """Her 5 dakikada bir çalışır — webhook'ları tazeler"""
    try:
        requests.get(f"https://api.telegram.org/bot{MASTER_TOKEN}/setWebhook?url={VERCEL_URL}/master")
        for t in all_clons():
            requests.get(f"https://api.telegram.org/bot{t}/setWebhook?url={VERCEL_URL}/clon/{t}")
    except:
        pass
    return {"status": "cron ok"}

# ============================================================
# ▶️ YEREL TEST
# ============================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
