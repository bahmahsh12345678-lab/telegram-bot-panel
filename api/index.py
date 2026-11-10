import os, sys, json, time, re, threading, requests
from datetime import datetime

try:
    from flask import Flask, request
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "flask"])
    from flask import Flask, request

# ============================================================
# ⚙️ AYARLAR
# ============================================================
MASTER_TOKEN = "9270110650:AAEJHCedTy7gGpxIxr3n_db6qawbJAN6gCo"
MASTER_OWNER_ID = 8947359034

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

ADMIN_FEATURES = {
    "announce": {"name": "📣 Duyuru Gönderme", "default": True},
    "stats": {"name": "📊 Statik", "default": True},
    "maintenance": {"name": "🛠 Bakım Modu", "default": True},
    "ban": {"name": "🚫 Ban / Unban", "default": True},
    "restart": {"name": "🔄 Sistem Yenileme", "default": True},
    "api_manage": {"name": "🔗 API Yönetimi", "default": True}
}

def get_base_url():
    url = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL") or os.environ.get("VERCEL_URL") or "sorgulaincpro.vercel.app"
    if not url.startswith("http"): url = "https://" + url
    return url.rstrip("/")

BASE_URL = get_base_url()

# ============================================================
# 🔒 DUPLICATE UPDATE ÖNLEYİCİ (TEKRAR MESAJ SORUNUNU ÇÖZER)
# ============================================================
_processed_updates = {}
_update_lock = threading.Lock()

def is_duplicate(update_id):
    """Aynı update_id 2 kez geldiyse True döner"""
    if not update_id: return False
    with _update_lock:
        now = time.time()
        # 60 saniyeden eski kayıtları temizle
        old_keys = [k for k, v in _processed_updates.items() if now - v > 60]
        for k in old_keys: del _processed_updates[k]
        
        if update_id in _processed_updates:
            return True
        _processed_updates[update_id] = now
        return False

# Kullanıcı bazlı kilit (aynı kullanıcıdan art arda gelen mesajları sıraya sokar)
_user_locks = {}
_user_locks_guard = threading.Lock()

def get_user_lock(uid):
    with _user_locks_guard:
        if uid not in _user_locks:
            _user_locks[uid] = threading.Lock()
        return _user_locks[uid]

# ============================================================
# 💾 HIZLI VERİTABANI
# ============================================================
_memory_db = None
_db_lock = threading.Lock()

def load_db():
    global _memory_db
    with _db_lock:
        if _memory_db is not None: return _memory_db
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
# 🚀 TELEGRAM API HELPER
# ============================================================
def tg_call(bot_token, method, **params):
    try:
        url = f"https://api.telegram.org/bot{bot_token}/{method}"
        r = requests.post(url, json=params, timeout=10)
        return r.json()
    except: return {"ok": False}

def send_message(bot_token, chat_id, text, reply_markup=None, parse_mode="HTML"):
    params = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup: params["reply_markup"] = reply_markup
    return tg_call(bot_token, "sendMessage", **params)

def edit_message(bot_token, chat_id, message_id, text, reply_markup=None, parse_mode="HTML"):
    params = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": parse_mode}
    if reply_markup: params["reply_markup"] = reply_markup
    return tg_call(bot_token, "editMessageText", **params)

def answer_callback(bot_token, callback_id):
    return tg_call(bot_token, "answerCallbackQuery", callback_query_id=callback_id)

def delete_message(bot_token, chat_id, message_id):
    return tg_call(bot_token, "deleteMessage", chat_id=chat_id, message_id=message_id)

def send_document(bot_token, chat_id, file_path, caption, reply_markup=None):
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
        with open(file_path, "rb") as f:
            files = {"document": f}
            data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
            if reply_markup: data["reply_markup"] = json.dumps(reply_markup)
            r = requests.post(url, data=data, files=files, timeout=30)
        return r.json()
    except: return {"ok": False}

def make_kb(buttons):
    keyboard = []
    for row in buttons:
        kb_row = []
        for btn in row:
            text = btn[0]
            data = btn[1] if len(btn) > 1 else ""
            is_url = btn[2] if len(btn) > 2 else False
            if is_url:
                kb_row.append({"text": text, "url": data})
            else:
                kb_row.append({"text": text, "callback_data": data})
        keyboard.append(kb_row)
    return {"inline_keyboard": keyboard}

# ============================================================
# 🤖 ANA BOT
# ============================================================
MASTER_STATE = {}

def master_handle(update):
    # DUPLICATE KONTROLÜ
    update_id = update.get("update_id")
    if is_duplicate(update_id): return
    
    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        from_id = msg["from"]["id"]
        text = (msg.get("text") or "").strip()
        
        if "document" in msg:
            handle_document(msg, chat_id, from_id)
            return
        
        if text == "/start":
            set_state(from_id, None); MASTER_STATE.pop(from_id, None)
            db = load_db()
            if db.get("maintenance") and from_id != MASTER_OWNER_ID:
                return send_message(MASTER_TOKEN, chat_id, "⚠️ <b>Sistem bakımda!</b>")
            
            kb = make_kb([
                [("🧩 Sorgu Botu Şablonu", "show_templates")],
                [("📤 .py Bot Yükle", "upload_py")],
                [("👑 Master Admin Panel", "master_admin")] if from_id == MASTER_OWNER_ID else []
            ])
            kb["inline_keyboard"] = [r for r in kb["inline_keyboard"] if r]
            return send_message(MASTER_TOKEN, chat_id, "🇹🇷 <b>Hoş Geldiniz!</b>\n\nKendi botunuzu oluşturmak için butonları kullanın.", reply_markup=kb)
        
        # KULLANICI KİLİDİ İLE SIRALI İŞLEME
        user_lock = get_user_lock(from_id)
        if not user_lock.acquire(blocking=False):
            # Aynı kullanıcıdan işlem devam ediyor, bu mesajı atla
            return
        try:
            if from_id in MASTER_STATE:
                handle_master_step(from_id, chat_id, text)
                return
            
            st = get_state(from_id)
            if st and "step" in st:
                handle_master_step(from_id, chat_id, text)
                return
        finally:
            user_lock.release()
    
    elif "callback_query" in update:
        cb = update["callback_query"]
        from_id = cb["from"]["id"]
        chat_id = cb["message"]["chat"]["id"]
        msg_id = cb["message"]["message_id"]
        data = cb["data"]
        answer_callback(MASTER_TOKEN, cb["id"])
        
        if data == "show_templates":
            kb = make_kb([
                [("🔍 Sorgu Botu", "tpl:query")],
                [("⬅️ Geri", "home")]
            ])
            return edit_message(MASTER_TOKEN, chat_id, msg_id, "🧩 <b>Lütfen Şablon Seçin</b>", reply_markup=kb)
        
        if data == "upload_py":
            return edit_message(MASTER_TOKEN, chat_id, msg_id, "📤 Lütfen botunuzun <code>.py</code> dosyasını gönderin.\n(Dosya içinde TOKEN, ADMIN_ID, BOT_NAME olmalı)")
        
        if data == "home":
            kb = make_kb([
                [("🧩 Sorgu Botu Şablonu", "show_templates")],
                [("📤 .py Bot Yükle", "upload_py")],
                [("👑 Master Admin Panel", "master_admin")] if from_id == MASTER_OWNER_ID else []
            ])
            kb["inline_keyboard"] = [r for r in kb["inline_keyboard"] if r]
            return edit_message(MASTER_TOKEN, chat_id, msg_id, "🏠 <b>Ana Menü</b>", reply_markup=kb)
        
        if data == "master_admin" and from_id == MASTER_OWNER_ID:
            db = load_db()
            mnt = "🟢 Aktif" if not db.get("maintenance") else "🔴 Bakımda"
            txt = f"👑 <b>MASTER ADMIN</b>\n\n🤖 Botlar: {len(db.get('clons', {}))}\n👥 Kullanıcı: {sum(len(c.get('users', [])) for c in db.get('clons', {}).values())}\n⚙️ Durum: {mnt}"
            kb = make_kb([
                [("📢 Global Duyuru", "m_global_announce")],
                [("⚙️ Bakım Modu", "m_toggle_maint")],
                [("⬅️ Geri", "home")]
            ])
            return edit_message(MASTER_TOKEN, chat_id, msg_id, txt, reply_markup=kb)
        
        if data == "m_global_announce":
            MASTER_STATE[from_id] = {"action": "global_announce"}
            return send_message(MASTER_TOKEN, chat_id, "📢 Duyuru metnini yaz:")
        
        if data == "m_toggle_maint":
            db = load_db()
            db["maintenance"] = not db.get("maintenance", False)
            save_db(db)
            status = "🟢 Aktif" if not db["maintenance"] else "🔴 Bakımda"
            return send_message(MASTER_TOKEN, chat_id, f"⚙️ Sistem: {status}")
        
        if data.startswith("tpl:"):
            # ÖNEMLİ: State'i set et, sonra mesaj gönder
            set_state(from_id, {"template": data[4:], "step": "token", "data": {}})
            return edit_message(MASTER_TOKEN, chat_id, msg_id, "<b>Adım 1:</b> Bot Tokenini gönder:")
        
        if data.startswith("feat:"):
            feat = data.split(":")[1]
            st = get_state(from_id)
            if not st: return
            feats = st["data"].get("features", {})
            feats[feat] = not feats.get(feat, False)
            st["data"]["features"] = feats
            set_state(from_id, st)
            
            btns = []
            for key, f in ADMIN_FEATURES.items():
                if key == "api_manage" and st["template"] != "query": continue
                check = "✅" if feats.get(key) else "❌"
                btns.append([(f"{check} {f['name']}", f"feat:{key}")])
            btns.append([("➡️ Devam Et", "feat_done")])
            return edit_message(MASTER_TOKEN, chat_id, msg_id, "<b>Admin Panel Özellikleri:</b>", reply_markup=make_kb(btns))
        
        if data == "feat_done":
            st = get_state(from_id)
            if not st: return
            st["step"] = "support"
            set_state(from_id, st)
            return edit_message(MASTER_TOKEN, chat_id, msg_id, "<b>Adım 5:</b> Destek linki (https://t.me/...):")
        
        if data == "confirm_yes":
            # Duplicate önleme - state zaten temizlenmişse çık
            st = get_state(from_id)
            if not st: 
                return edit_message(MASTER_TOKEN, chat_id, msg_id, "⚠️ Bu işlem zaten tamamlandı.")
            set_state(from_id, None)
            
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
                requests.get(f"https://api.telegram.org/bot{d['token']}/setWebhook?url={BASE_URL}/clon/{d['token']}", timeout=10)
                requests.post(f"https://api.telegram.org/bot{d['token']}/setMyName", json={"name": d["bot_name"]}, timeout=10)
            except: pass
            return edit_message(MASTER_TOKEN, chat_id, msg_id, f"✅ <b>Bot kuruldu!</b>\n\n🤖 {d['bot_name']}\n🔗 https://t.me/{d['bot_username']}")
        
        if data == "cancel":
            set_state(from_id, None); MASTER_STATE.pop(from_id, None)
            return edit_message(MASTER_TOKEN, chat_id, msg_id, "❌ İptal edildi.")

def handle_document(msg, chat_id, from_id):
    try:
        file_id = msg["document"]["file_id"]
        file_name = msg["document"]["file_name"]
        if not file_name.endswith(".py"):
            return send_message(MASTER_TOKEN, chat_id, "❌ Sadece .py dosyası kabul edilir.")
        
        r = tg_call(MASTER_TOKEN, "getFile", file_id=file_id)
        if not r.get("ok"):
            return send_message(MASTER_TOKEN, chat_id, "❌ Dosya alınamadı.")
        
        file_path = r["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{MASTER_TOKEN}/{file_path}"
        py_content = requests.get(file_url, timeout=15).text
        
        token_match = re.search(r'TOKEN\s*=\s*["\']([^"\']+)["\']', py_content)
        admin_match = re.search(r'ADMIN_ID\s*=\s*(\d+)', py_content)
        name_match = re.search(r'BOT_NAME\s*=\s*["\']([^"\']+)["\']', py_content)
        
        if not token_match or not admin_match:
            return send_message(MASTER_TOKEN, chat_id, "❌ Geçersiz .py: TOKEN ve ADMIN_ID bulunamadı.")
        
        token = token_match.group(1)
        admin_id = int(admin_match.group(1))
        bot_name = name_match.group(1) if name_match else "Clon Bot"
        
        r = tg_call(token, "getMe")
        if not r.get("ok"):
            return send_message(MASTER_TOKEN, chat_id, "❌ Token geçersiz!")
        bot_username = r["result"]["username"]
        
        clon = {
            "token": token, "bot_username": bot_username, "owner_id": admin_id,
            "bot_name": bot_name, "status": "active", "maintenance": False,
            "template": "query", "features": {k: True for k in ADMIN_FEATURES.keys()},
            "users": [], "banned_dm": [], "queries": DEFAULT_QUERIES.copy(), 
            "created": datetime.now().isoformat()
        }
        save_clon(token, clon)
        
        try:
            requests.get(f"https://api.telegram.org/bot{token}/setWebhook?url={BASE_URL}/clon/{token}", timeout=10)
            requests.post(f"https://api.telegram.org/bot{token}/setMyName", json={"name": bot_name}, timeout=10)
        except: pass
        
        send_message(MASTER_TOKEN, chat_id, f"✅ <b>Bot yüklendi!</b>\n\n🤖 {bot_name}\n🔗 https://t.me/{bot_username}")
    except Exception as e:
        send_message(MASTER_TOKEN, chat_id, f"❌ Hata: {str(e)[:100]}")

def handle_master_step(from_id, chat_id, text):
    if text == "/iptal":
        MASTER_STATE.pop(from_id, None); set_state(from_id, None)
        return send_message(MASTER_TOKEN, chat_id, "❌ İptal edildi.")
    
    if from_id in MASTER_STATE:
        act = MASTER_STATE[from_id]
        if act["action"] == "global_announce":
            MASTER_STATE.pop(from_id, None)
            db = load_db(); sent = 0
            for clon in db.get("clons", {}).values():
                for u in clon.get("users", []):
                    try:
                        send_message(clon["token"], u, f"📢 <b>GLOBAL DUYURU</b>\n\n{text}")
                        sent += 1
                    except: pass
            return send_message(MASTER_TOKEN, chat_id, f"✅ {sent} kişiye gönderildi.")
    
    st = get_state(from_id)
    if not st or "step" not in st: return
    step = st["step"]; data = st["data"]
    
    if step == "token":
        if ":" not in text:
            return send_message(MASTER_TOKEN, chat_id, "❌ Geçersiz token.")
        r = tg_call(text, "getMe")
        if not r.get("ok"):
            return send_message(MASTER_TOKEN, chat_id, "❌ Token doğrulanamadı.")
        data["token"] = text
        data["bot_username"] = r["result"]["username"]
        st["step"] = "admin_id"
        set_state(from_id, st)  # STATE ÖNCE KAYDET
        return send_message(MASTER_TOKEN, chat_id, "<b>Adım 2:</b> Admin ID'ni gönder:")
    
    elif step == "admin_id":
        clean_id = re.sub(r'\D', '', text)
        if not clean_id:
            return send_message(MASTER_TOKEN, chat_id, "❌ Sadece rakam girin.")
        data["owner_id"] = int(clean_id)
        st["step"] = "bot_name"
        set_state(from_id, st)  # STATE ÖNCE KAYDET
        return send_message(MASTER_TOKEN, chat_id, "<b>Adım 3:</b> Bot ismini gönder:")
    
    elif step == "bot_name":
        data["bot_name"] = text[:64]
        data["features"] = {k: f["default"] for k, f in ADMIN_FEATURES.items()}
        st["data"] = data
        st["step"] = "features"
        set_state(from_id, st)  # STATE ÖNCE KAYDET
        
        btns = []
        for key, f in ADMIN_FEATURES.items():
            if key == "api_manage" and st["template"] != "query": continue
            btns.append([(f"✅ {f['name']}", f"feat:{key}")])
        btns.append([("➡️ Devam Et", "feat_done")])
        return send_message(MASTER_TOKEN, chat_id, "<b>Adım 4:</b> Admin Panel Özellikleri:", reply_markup=make_kb(btns))
    
    elif step == "support":
        if not text.startswith("https://t.me/"):
            return send_message(MASTER_TOKEN, chat_id, "❌ https://t.me/... olmalı.")
        data["support"] = text
        # STATE'İ TEMİZLEMEDEN ÖNCE ÖZET GÖSTER
        # (Confirm_yes'te temizlenecek)
        st["step"] = "confirm"  # Bu adım artık bekliyor
        set_state(from_id, st)
        
        feats_text = ", ".join([f["name"] for k, f in ADMIN_FEATURES.items() if data.get("features", {}).get(k)]) or "Yok"
        txt = f"📋 <b>ÖZET</b>\n\n🤖 Bot: @{data['bot_username']}\n📝 İsim: {data['bot_name']}\n👑 Admin: {data['owner_id']}\n🩵 Destek: {data['support']}\n⚙️ Özellikler: {feats_text}\n\n✅ Onaylıyor musun?"
        kb = make_kb([
            [("✅ Onayla", "confirm_yes"), ("❌ İptal", "cancel")]
        ])
        return send_message(MASTER_TOKEN, chat_id, txt, reply_markup=kb)

# ============================================================
# 🎛 CLON BOT
# ============================================================
PENDING_ACTION = {}
_user_last_query = {}

def _check_cooldown(uid, window=3.0):
    now = time.time()
    diff = now - _user_last_query.get(uid, 0)
    if diff < window: return False, round(window - diff, 1)
    _user_last_query[uid] = now
    return True, 0

def _clean_dict(d):
    if not isinstance(d, dict): return d
    for k in list(d.keys()):
        if k.lower() in ("developer","devoloper","version","sürüm","surum","auth","altauth"): del d[k]
    return d

def clean_response(txt):
    for w in ["DEVOLOPER","DEVELOPER","developer","Devoloper","sürüm","Sürüm","SURUM","version","Version","auth","Auth","altauth","@jessy_php","jessy_php","JESSY_PHP"]:
        txt = txt.replace(w, "")
    try: data = json.loads(txt)
    except: return txt
    if isinstance(data, dict):
        _clean_dict(data)
        if "results" in data and isinstance(data["results"], list):
            data["results"] = [_clean_dict(x) if isinstance(x, dict) else x for x in data["results"]]
        return data
    return data

def clon_handle(token, update):
    # DUPLICATE KONTROLÜ
    update_id = update.get("update_id")
    if is_duplicate(update_id): return
    
    clon = get_clon(token)
    if not clon: return
    
    db = load_db()
    if db.get("maintenance") and update.get("message", {}).get("from", {}).get("id") != clon["owner_id"]:
        return
    
    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        from_id = msg["from"]["id"]
        text = (msg.get("text") or "").strip()
        fname = msg["from"].get("first_name", "")
        
        if from_id in clon.get("banned_dm", []): return
        if clon.get("status") == "passive" and from_id != clon["owner_id"]: return
        
        if from_id in PENDING_ACTION:
            act = PENDING_ACTION.pop(from_id)
            if act["token"] == token:
                handle_clon_action(token, chat_id, from_id, clon, act, text)
                return
        
        if text == "/start":
            if from_id not in clon.get("users", []):
                clon["users"].append(from_id); save_clon(token, clon)
            
            if clon.get("maintenance") and from_id != clon["owner_id"]:
                return send_message(token, chat_id, "⚠️ Bot bakımda!")
            
            btns = []
            active = [q for q, v in clon.get("queries", {}).items() if v.get("active", True)]
            row = []
            for i, q in enumerate(active):
                row.append((f"🔍 {q}", f"q_{q}"))
                if len(row) == 2: btns.append(row); row = []
            if row: btns.append(row)
            
            if clon.get("support"):
                btns.append([("🩵 Destek", clon["support"], True)])
            
            return send_message(token, chat_id, f"👋 <b>Hoş Geldin, {fname}!</b>\n\nMenüden sorgu seç.", reply_markup=make_kb(btns))
        
        if text == "/admin":
            if from_id != clon["owner_id"]: return
            return show_clon_panel(token, chat_id, clon)
        
        query_type = clon.get("active_query", {}).get(str(from_id))
        if query_type:
            ok, remain = _check_cooldown(from_id)
            if not ok: return send_message(token, chat_id, f"⚠️ {remain} sn bekle.")
            clon["active_query"].pop(str(from_id), None); save_clon(token, clon)
            
            status = send_message(token, chat_id, f"⏳ <b>{query_type}</b> hazırlanıyor...")
            try:
                q_data = clon.get("queries", {}).get(query_type)
                if not q_data or not q_data.get("active"):
                    return edit_message(token, chat_id, status["result"]["message_id"], "❌ Sorgu devre dışı.")
                
                url = q_data["url"]; parts = text.split(); params = {}
                if query_type == "Ad Soyad":
                    if len(parts) < 2: return edit_message(token, chat_id, status["result"]["message_id"], "❌ Ad ve Soyad girin.")
                    params["ad"], params["soyad"] = parts[0], parts[1]
                    params["il"] = parts[2] if len(parts) >= 3 else ""
                    params["ilce"] = " ".join(parts[3:]) if len(parts) >= 4 else ""
                elif query_type == "Ada Parsel":
                    if len(parts) < 2: return edit_message(token, chat_id, status["result"]["message_id"], "❌ İl ve İlçe girin.")
                    url = url.format(il=parts[0], ilce=" ".join(parts[1:]))
                else:
                    if "{tc}" in url: url = url.format(tc="".join(filter(str.isdigit, text)))
                    elif "{gsm}" in url:
                        clean = "".join(filter(str.isdigit, text))
                        url = url.format(gsm=clean[1:] if clean.startswith("0") else clean)
                
                r = requests.get(url, params=params, timeout=15)
                data = clean_response(r.text)
                if isinstance(data, dict) and data.get("hata"):
                    return edit_message(token, chat_id, status["result"]["message_id"], f"❌ Hata: {data.get('hata')}")
                
                fn = os.path.join(DATA_DIR, f"sorgu_{int(time.time())}.json")
                with open(fn, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
                
                try: delete_message(token, chat_id, status["result"]["message_id"])
                except: pass
                
                kb = make_kb([[("⬅️ Geri", "back_to_menu")]])
                send_document(token, chat_id, fn, f"✅ <b>{query_type} Sonucu</b>\n\n🕐 {datetime.now().strftime('%H:%M:%S')}", reply_markup=kb)
                os.remove(fn)
            except Exception as e:
                try: edit_message(token, chat_id, status["result"]["message_id"], f"❌ Hata: {str(e)[:100]}")
                except: pass
            return
    
    elif "callback_query" in update:
        cb = update["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        from_id = cb["from"]["id"]
        data = cb["data"]
        msg_id = cb["message"]["message_id"]
        answer_callback(token, cb["id"])
        
        if data == "back_to_menu":
            try: delete_message(token, chat_id, msg_id)
            except: pass
            return send_message(token, chat_id, "🏠 Ana Menü: /start")
        
        if data.startswith("q_"):
            q_name = data[2:]
            if "active_query" not in clon: clon["active_query"] = {}
            clon["active_query"][str(from_id)] = q_name
            save_clon(token, clon)
            hint = clon.get("queries", {}).get(q_name, {}).get("hint", "Bilgi girin:")
            kb = make_kb([[("❌ İptal", "back_to_menu")]])
            return edit_message(token, chat_id, msg_id, f"🔍 <b>{q_name}</b>\n\n{hint}", reply_markup=kb)
        
        if from_id == clon["owner_id"] and data.startswith("m_"):
            clon_panel_callback(token, chat_id, from_id, clon, data, cb)

def show_clon_panel(token, chat_id, clon):
    mnt = "🟢 Aktif" if not clon.get("maintenance") else "🔴 Bakımda"
    txt = f"🎛 <b>Bot Yönetim Paneli</b>\n\n🤖 {clon['bot_name']}\n🆔 @{clon['bot_username']}\n👥 Kullanıcı: {len(clon.get('users', []))}\n📊 Durum: {clon['status']} | Bakım: {mnt}"
    
    feats = clon.get("features", {})
    btns = []
    if feats.get("announce"): btns.append([("📣 Duyuru", "m_announce")])
    if feats.get("stats"): btns.append([("📊 Statik", "m_stats")])
    if feats.get("maintenance"): btns.append([("🛠 Bakım Modu", "m_toggle_maint")])
    if feats.get("ban"): btns.append([("🚫 Banla", "m_ban"), ("✅ Unban", "m_unban")])
    if feats.get("restart"): btns.append([("🔄 Yenile", "m_restart")])
    if feats.get("api_manage") and clon.get("template") == "query":
        btns.append([("🔗 Sorgular", "m_manage_queries")])
    btns.append([("▶️ Aktif", "m_active"), ("⏸ Durdur", "m_passive")])
    btns.append([("⬅️ Kapat", "back_to_menu")])
    
    return send_message(token, chat_id, txt, reply_markup=make_kb(btns))

def clon_panel_callback(token, chat_id, uid, clon, data, cb):
    if data == "m_active": clon["status"] = "active"; save_clon(token, clon); send_message(token, chat_id, "🟢 Aktif.")
    elif data == "m_passive": clon["status"] = "passive"; save_clon(token, clon); send_message(token, chat_id, "🔴 Durduruldu.")
    elif data == "m_toggle_maint":
        clon["maintenance"] = not clon.get("maintenance", False); save_clon(token, clon)
        send_message(token, chat_id, f"🛠 Bakım: {'Açık' if clon['maintenance'] else 'Kapalı'}")
    elif data == "m_manage_queries":
        btns = []
        for q_name, q_data in clon.get("queries", {}).items():
            icon = "🟢" if q_data.get("active") else "🔴"
            btns.append([(f"{icon} {q_name}", f"q_edit:{q_name}")])
        btns.append([("➕ Yeni API", "q_add")])
        btns.append([("⬅️ Geri", "back_to_menu")])
        send_message(token, chat_id, "🔗 Sorgular:", reply_markup=make_kb(btns))
    elif data == "q_add":
        PENDING_ACTION[uid] = {"token": token, "action": "add_query"}
        send_message(token, chat_id, "Yeni sorgu adı:")
    elif data.startswith("q_edit:"):
        q_name = data.split(":")[1]
        q = clon["queries"][q_name]
        btns = [
            [("🔴 Toggle", f"q_toggle:{q_name}")],
            [("✏️ Link Değiştir", f"q_url:{q_name}")],
            [("🗑 Sil", f"q_del:{q_name}")],
            [("⬅️ Geri", "m_manage_queries")]
        ]
        send_message(token, chat_id, f"🔍 <b>{q_name}</b>\nDurum: {q.get('active')}\nLink: <code>{q.get('url')}</code>", reply_markup=make_kb(btns))
    elif data.startswith("q_toggle:"):
        q = data.split(":")[1]
        clon["queries"][q]["active"] = not clon["queries"][q]["active"]; save_clon(token, clon)
        send_message(token, chat_id, "✅ Değiştirildi.")
    elif data.startswith("q_del:"):
        clon["queries"].pop(data.split(":")[1], None); save_clon(token, clon)
        send_message(token, chat_id, "✅ Silindi.")
    elif data.startswith("q_url:"):
        PENDING_ACTION[uid] = {"token": token, "action": "set_url", "q_name": data.split(":")[1]}
        send_message(token, chat_id, "Yeni API linki:")
    elif data == "m_announce": PENDING_ACTION[uid] = {"token": token, "action": "announce"}; send_message(token, chat_id, "Duyuru metni:")
    elif data == "m_ban": PENDING_ACTION[uid] = {"token": token, "action": "ban"}; send_message(token, chat_id, "Ban ID:")
    elif data == "m_unban": PENDING_ACTION[uid] = {"token": token, "action": "unban"}; send_message(token, chat_id, "Unban ID:")
    elif data == "m_stats": send_message(token, chat_id, f"📊 Kullanıcı: {len(clon.get('users', []))}\n🚫 Banlı: {len(clon.get('banned_dm', []))}")
    elif data == "m_restart":
        send_message(token, chat_id, "🔄 Yenileniyor...")
        try:
            requests.get(f"https://api.telegram.org/bot{token}/setWebhook?url={BASE_URL}/clon/{token}", timeout=10)
            send_message(token, chat_id, "✅ Yenilendi.")
        except: send_message(token, chat_id, "❌ Hata.")

def handle_clon_action(token, chat_id, uid, clon, act, txt):
    action = act["action"]
    if action == "add_query":
        PENDING_ACTION[uid] = {"token": token, "action": "add_url", "q_name": txt}
        send_message(token, chat_id, f"{txt} için API linki:")
    elif action == "add_url":
        clon["queries"][act["q_name"]] = {"url": txt, "active": True, "hint": "Bilgi girin"}
        save_clon(token, clon); send_message(token, chat_id, "✅ API eklendi.")
    elif action == "set_url":
        clon["queries"][act["q_name"]]["url"] = txt; save_clon(token, clon)
        send_message(token, chat_id, "✅ Güncellendi.")
    elif action == "announce":
        sent = 0
        for u in clon.get("users", []):
            try: send_message(token, u, f"📢 {txt}"); sent += 1
            except: pass
        send_message(token, chat_id, f"✅ {sent} kişiye gönderildi.")
    elif action == "ban":
        if txt.isdigit():
            if "banned_dm" not in clon: clon["banned_dm"] = []
            if int(txt) not in clon["banned_dm"]: clon["banned_dm"].append(int(txt))
            save_clon(token, clon); send_message(token, chat_id, "🚫 Banlandı.")
    elif action == "unban":
        if txt.isdigit() and int(txt) in clon.get("banned_dm", []):
            clon["banned_dm"].remove(int(txt)); save_clon(token, clon)
            send_message(token, chat_id, "✅ Unban.")

# ============================================================
# 🚀 FLASK WEBHOOK
# ============================================================
app = Flask(__name__)

@app.route("/", methods=["GET"])
def home(): return "Bot aktif."

@app.route("/master", methods=["POST"])
def master_webhook():
    try:
        update = request.get_json(force=True)
        master_handle(update)
        return "OK", 200
    except Exception as e:
        return str(e), 500

@app.route("/clon/<token>", methods=["POST"])
def clon_webhook(token):
    try:
        update = request.get_json(force=True)
        clon_handle(token, update)
        return "OK", 200
    except Exception as e:
        return str(e), 500

@app.route("/setup", methods=["GET"])
def setup():
    requests.get(f"https://api.telegram.org/bot{MASTER_TOKEN}/setWebhook?url={BASE_URL}/master", timeout=15)
    for t in load_db().get("clons", {}):
        try: requests.get(f"https://api.telegram.org/bot{t}/setWebhook?url={BASE_URL}/clon/{t}", timeout=10)
        except: pass
    return {"ok": True, "base_url": BASE_URL, "clons": len(load_db().get("clons", {}))}

@app.route("/cron", methods=["GET"])
def cron():
    try:
        requests.get(f"https://api.telegram.org/bot{MASTER_TOKEN}/setWebhook?url={BASE_URL}/master", timeout=10)
    except: pass
    return {"status": "ok"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
