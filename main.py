import subprocess
import sys
import os
import telebot
import json
import threading
import time
import random
import string
import re
import requests
import zipfile
import hashlib
import base64
import shutil
import psutil
import resource
from telebot import types
from datetime import datetime, timedelta
from html import escape
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes

required_modules = {
    'telebot': 'pyTelegramBotAPI',
    'requests': 'requests',
    'Crypto': 'pycryptodome',
    'psutil': 'psutil',
    'pymongo': 'pymongo'
}
missing_packages = []
for module, package in required_modules.items():
    try:
        __import__(module)
    except ImportError:
        missing_packages.append(package)

if missing_packages:
    print(f"Installing missing packages: {missing_packages}")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing_packages)
        print("Installation successful. Please restart the script.")
        sys.exit(0)
    except subprocess.CalledProcessError as e:
        print(f"Installation failed: {e}")
        sys.exit(1)

import pymongo

MONGODB_URI = os.environ.get("MONGODB_URI")
if not MONGODB_URI:
    print("Error: MONGODB_URI environment variable is not set.")
    sys.exit(1)

TOKEN = 'توكنك'
ADMIN_ID = 6812997550
HIDDEN_LONG = "ㅤ" * 50
bot = telebot.TeleBot(TOKEN, threaded=True, parse_mode="HTML")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUNNING_DIR = os.path.join(BASE_DIR, 'active_bots')
LOGS_DIR = os.path.join(BASE_DIR, 'bot_logs')
DB_DIR = os.path.join(BASE_DIR, 'database')
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')
STORE_DIR = os.path.join(BASE_DIR, 'store_files')
THUMBS_DIR = os.path.join(ASSETS_DIR, 'thumbs')
MARKET_DIR = os.path.join(BASE_DIR, 'market')
ENV_DIR = os.path.join(BASE_DIR, 'bot_environments')
ENCRYPTED_DIR = os.path.join(BASE_DIR, 'encrypted_files')
TEMP_DIR = os.path.join(BASE_DIR, 'temp')

for d in [RUNNING_DIR, LOGS_DIR, DB_DIR, ASSETS_DIR, STORE_DIR, THUMBS_DIR, MARKET_DIR, ENV_DIR, ENCRYPTED_DIR, TEMP_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

db = None
db_lock = threading.Lock()

cancel_states = {}
last_bot_messages = {}
active_processes = {}
process_hours = {}
user_notifications = {}
process_resources = {}

RESOURCE_LIMITS = {
    'max_cpu_percent': 80,
    'max_memory_mb': 256,
    'max_disk_usage_mb': 100,
    'max_processes': 20,
    'max_log_size_mb': 5
}

class DatabaseManager:
    @staticmethod
    def _get_collection(name):
        return db[name]

    @staticmethod
    def get_users():
        with db_lock:
            doc = DatabaseManager._get_collection('users').find_one({"_id": "users_data"})
        return doc.get("users", {}) if doc else {}

    @staticmethod
    def save_users(data):
        with db_lock:
            DatabaseManager._get_collection('users').update_one(
                {"_id": "users_data"},
                {"$set": {"users": data}},
                upsert=True
            )

    @staticmethod
    def get_files():
        with db_lock:
            doc = DatabaseManager._get_collection('files').find_one({"_id": "files_data"})
        return doc.get("files", {}) if doc else {}

    @staticmethod
    def save_files(data):
        with db_lock:
            DatabaseManager._get_collection('files').update_one(
                {"_id": "files_data"},
                {"$set": {"files": data}},
                upsert=True
            )

    @staticmethod
    def get_settings():
        with db_lock:
            doc = DatabaseManager._get_collection('settings').find_one({"_id": "settings_data"})
        return doc.get("settings", {}) if doc else {}

    @staticmethod
    def save_settings(data):
        with db_lock:
            DatabaseManager._get_collection('settings').update_one(
                {"_id": "settings_data"},
                {"$set": {"settings": data}},
                upsert=True
            )

    @staticmethod
    def get_store():
        with db_lock:
            doc = DatabaseManager._get_collection('store').find_one({"_id": "store_data"})
        return doc.get("store", {}) if doc else {}

    @staticmethod
    def save_store(data):
        with db_lock:
            DatabaseManager._get_collection('store').update_one(
                {"_id": "store_data"},
                {"$set": {"store": data}},
                upsert=True
            )

    @staticmethod
    def get_admins():
        with db_lock:
            doc = DatabaseManager._get_collection('admins').find_one({"_id": "admins_data"})
        if not doc:
            return [ADMIN_ID]
        return doc.get("admins", [ADMIN_ID])

    @staticmethod
    def save_admins(data):
        with db_lock:
            DatabaseManager._get_collection('admins').update_one(
                {"_id": "admins_data"},
                {"$set": {"admins": data}},
                upsert=True
            )

    @staticmethod
    def get_market():
        with db_lock:
            doc = DatabaseManager._get_collection('market').find_one({"_id": "market_data"})
        return doc.get("market", {}) if doc else {}

    @staticmethod
    def save_market(data):
        with db_lock:
            DatabaseManager._get_collection('market').update_one(
                {"_id": "market_data"},
                {"$set": {"market": data}},
                upsert=True
            )

    @staticmethod
    def get_security():
        with db_lock:
            doc = DatabaseManager._get_collection('security').find_one({"_id": "security_data"})
        return doc.get("security", {}) if doc else {}

    @staticmethod
    def save_security(data):
        with db_lock:
            DatabaseManager._get_collection('security').update_one(
                {"_id": "security_data"},
                {"$set": {"security": data}},
                upsert=True
            )

class EncryptionManager:
    @staticmethod
    def get_master_key():
        security = DatabaseManager.get_security()
        master_key = security.get('master_key')
        if not master_key:
            master_key = base64.b64encode(get_random_bytes(32)).decode('utf-8')
            security['master_key'] = master_key
            DatabaseManager.save_security(security)
        return base64.b64decode(master_key)

    @staticmethod
    def generate_file_key(fid, user_id):
        security = DatabaseManager.get_security()
        file_keys = security.get('file_keys', {})
        if fid not in file_keys:
            combined = f"{fid}:{user_id}:{ADMIN_ID}:{TOKEN}"
            salt = hashlib.sha256(combined.encode()).digest()[:16]
            master_key = EncryptionManager.get_master_key()
            kdf = hashlib.pbkdf2_hmac('sha256', master_key, salt, 100000, dklen=32)
            file_keys[fid] = {
                'key': base64.b64encode(kdf).decode('utf-8'),
                'salt': base64.b64encode(salt).decode('utf-8'),
                'user_id': user_id
            }
            security['file_keys'] = file_keys
            DatabaseManager.save_security(security)
        return file_keys[fid]

    @staticmethod
    def get_file_key(fid):
        security = DatabaseManager.get_security()
        return security.get('file_keys', {}).get(fid)

    @staticmethod
    def encrypt_content(content, fid, user_id):
        try:
            file_key_info = EncryptionManager.generate_file_key(fid, user_id)
            key = base64.b64decode(file_key_info['key'])
            salt = base64.b64decode(file_key_info['salt'])
            cipher = AES.new(key, AES.MODE_CBC)
            ct_bytes = cipher.encrypt(pad(content.encode('utf-8'), AES.block_size))
            encrypted_data = {
                'iv': base64.b64encode(cipher.iv).decode('utf-8'),
                'ciphertext': base64.b64encode(ct_bytes).decode('utf-8'),
                'salt': base64.b64encode(salt).decode('utf-8'),
                'fid': fid,
                'user_id': user_id,
                'timestamp': datetime.now().isoformat()
            }
            return json.dumps(encrypted_data)
        except Exception as e:
            print(f"Encryption error: {e}")
            return None

    @staticmethod
    def decrypt_content(encrypted_json, fid):
        try:
            data = json.loads(encrypted_json)
            file_key_info = EncryptionManager.get_file_key(fid)
            if not file_key_info:
                return None
            key = base64.b64decode(file_key_info['key'])
            iv = base64.b64decode(data['iv'])
            ct = base64.b64decode(data['ciphertext'])
            cipher = AES.new(key, AES.MODE_CBC, iv)
            pt = unpad(cipher.decrypt(ct), AES.block_size)
            return pt.decode('utf-8')
        except Exception as e:
            print(f"Decryption error: {e}")
            return None

    @staticmethod
    def save_encrypted_file(fid, content, user_id):
        encrypted_content = EncryptionManager.encrypt_content(content, fid, user_id)
        if encrypted_content:
            encrypted_path = os.path.join(ENCRYPTED_DIR, f"{fid}.enc")
            with open(encrypted_path, 'w', encoding='utf-8') as f:
                f.write(encrypted_content)
            return True
        return False

    @staticmethod
    def load_encrypted_file(fid):
        encrypted_path = os.path.join(ENCRYPTED_DIR, f"{fid}.enc")
        if os.path.exists(encrypted_path):
            with open(encrypted_path, 'r', encoding='utf-8') as f:
                encrypted_content = f.read()
            return EncryptionManager.decrypt_content(encrypted_content, fid)
        return None

class ProcessManager:
    @staticmethod
    def start_script(fid):
        files = DatabaseManager.get_files()
        if fid not in files:
            return False
        file_info = files[fid]
        user_id = file_info.get('user_id')
        if not Utilities.verify_file_access(fid, user_id):
            return False
        encrypted_content = EncryptionManager.load_encrypted_file(fid)
        if not encrypted_content:
            return False
        env_dir = os.path.join(ENV_DIR, fid)
        if not os.path.exists(env_dir):
            os.makedirs(env_dir)
        env_file_path = os.path.join(env_dir, f"{fid}.py")
        if fid in active_processes and active_processes[fid].poll() is None:
            return True
        if len(active_processes) >= RESOURCE_LIMITS['max_processes']:
            return False
        try:
            with open(env_file_path, 'w', encoding='utf-8') as f:
                f.write(encrypted_content)
        except:
            return False
        log_path = os.path.join(LOGS_DIR, f"{fid}.log")
        try:
            log_file = open(log_path, "a", encoding="utf-8")
            proc = subprocess.Popen(
                [sys.executable, "-u", env_file_path],
                stdout=log_file,
                stderr=log_file,
                stdin=subprocess.PIPE,
                cwd=env_dir,
                start_new_session=True,
                env={**os.environ, "PYTHONPATH": env_dir}
            )
            active_processes[fid] = proc
            process_resources[fid] = {
                'pid': proc.pid,
                'start_time': time.time(),
                'cpu_usage': 0,
                'memory_usage': 0
            }
            return True
        except:
            return False

    @staticmethod
    def stop_script(fid):
        if fid in active_processes:
            proc = active_processes[fid]
            try:
                os.killpg(os.getpgid(proc.pid), 9)
            except:
                try:
                    proc.terminate()
                except:
                    pass
            del active_processes[fid]
            if fid in process_hours:
                del process_hours[fid]
            if fid in process_resources:
                del process_resources[fid]
            return True
        return False

    @staticmethod
    def stop_all():
        for fid in list(active_processes.keys()):
            ProcessManager.stop_script(fid)
        return True

    @staticmethod
    def write_stdin(fid, cmd):
        if fid in active_processes and active_processes[fid].poll() is None:
            try:
                proc = active_processes[fid]
                if proc.stdin:
                    proc.stdin.write(cmd.encode('utf-8') + b'\n')
                    proc.stdin.flush()
                    return True
            except:
                pass
        return False

    @staticmethod
    def get_resource_usage(fid):
        if fid not in process_resources:
            return None
        try:
            proc = psutil.Process(process_resources[fid]['pid'])
            cpu = proc.cpu_percent(interval=0.1)
            mem = proc.memory_info().rss / (1024 * 1024)
            return {'cpu': cpu, 'memory': mem}
        except:
            return None

class Utilities:
    @staticmethod
    def gen_id(length=8):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

    @staticmethod
    def get_user_lang(user_id):
        users = DatabaseManager.get_users()
        u = users.get(str(user_id), {})
        return u.get('lang', 'en')

    @staticmethod
    def get_user_style(user_id):
        users = DatabaseManager.get_users()
        u = users.get(str(user_id), {})
        return u.get('button_style', 'default')

    @staticmethod
    def set_user_lang(user_id, lang):
        users = DatabaseManager.get_users()
        if str(user_id) in users:
            users[str(user_id)]['lang'] = lang
            DatabaseManager.save_users(users)

    @staticmethod
    def set_user_style(user_id, style):
        users = DatabaseManager.get_users()
        if str(user_id) in users:
            users[str(user_id)]['button_style'] = style
            DatabaseManager.save_users(users)

    @staticmethod
    def get_text(user_id, key, **kwargs):
        lang = Utilities.get_user_lang(user_id)
        text_dict = TRANSLATIONS.get(key, {})
        text = text_dict.get(lang, text_dict.get('en', key))
        if kwargs:
            text = text.format(**kwargs)
        return text

    @staticmethod
    def create_button(text, callback_data, user_id, style_override=None, url=None):
        style = style_override or Utilities.get_user_style(user_id) or 'default'
        if url:
            btn = types.InlineKeyboardButton(text=text, url=url)
        else:
            btn = types.InlineKeyboardButton(text=text, callback_data=callback_data)
        if style != 'default' and hasattr(btn, 'style'):
            btn.style = style
        return btn

    @staticmethod
    def format_border(user_id, title_key, content_key, **kwargs):
        title = Utilities.get_text(user_id, title_key, **kwargs)
        content = Utilities.get_text(user_id, content_key, **kwargs)
        settings = DatabaseManager.get_settings()
        name = settings.get('bot_name', 'Hosting Bot')
        return (f"┌─⊷『 {title} 』\n│\n├ {content}\n│\n└─⊷ <b>{name}</b>\n"
                f"<code>White Wolf t.me/j49_c</code>\n"
                f"<code>channel t.me/bshshshkk</code>\n{HIDDEN_LONG}")

    @staticmethod
    def delete_last_message(chat_id):
        if chat_id in last_bot_messages:
            try:
                bot.delete_message(chat_id, last_bot_messages[chat_id])
            except:
                pass

    @staticmethod
    def save_message(chat_id, msg_id):
        last_bot_messages[chat_id] = msg_id

    @staticmethod
    def send_message(chat_id, user_id, text, markup=None):
        Utilities.delete_last_message(chat_id)
        settings = DatabaseManager.get_settings()
        try:
            if settings.get('bot_image'):
                msg = bot.send_photo(chat_id, settings['bot_image'], caption=text, parse_mode="HTML", reply_markup=markup)
            else:
                msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
            Utilities.save_message(chat_id, msg.message_id)
            return msg
        except:
            msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
            Utilities.save_message(chat_id, msg.message_id)
            return msg

    @staticmethod
    def edit_message(call, user_id, text, markup):
        try:
            if call.message.content_type == 'photo':
                bot.edit_message_caption(text[:4096], call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
            else:
                bot.edit_message_text(text[:4096], call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
            Utilities.save_message(call.message.chat.id, call.message.message_id)
        except:
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
            settings = DatabaseManager.get_settings()
            try:
                if settings.get('bot_image'):
                    msg = bot.send_photo(call.message.chat.id, settings['bot_image'], caption=text[:4096], parse_mode="HTML", reply_markup=markup)
                else:
                    msg = bot.send_message(call.message.chat.id, text[:4096], parse_mode="HTML", reply_markup=markup)
                Utilities.save_message(call.message.chat.id, msg.message_id)
            except:
                msg = bot.send_message(call.message.chat.id, text[:4096], parse_mode="HTML", reply_markup=markup)
                Utilities.save_message(call.message.chat.id, msg.message_id)

    @staticmethod
    def delete_messages(chat_id, *msg_ids):
        for msg_id in msg_ids:
            if msg_id:
                try:
                    bot.delete_message(chat_id, msg_id)
                except:
                    pass

    @staticmethod
    def is_user_pro(uid):
        if uid == ADMIN_ID or Utilities.is_admin(uid):
            return True
        users = DatabaseManager.get_users()
        u = users.get(str(uid), {})
        expiry = u.get('expiry')
        if not expiry or expiry == 'null':
            return False
        if expiry == 'LIFETIME' or expiry == 0:
            return True
        try:
            exp_date = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
            if datetime.now() < exp_date:
                return True
            else:
                u['expiry'] = None
                users[str(uid)] = u
                DatabaseManager.save_users(users)
                return False
        except:
            return False

    @staticmethod
    def check_subscription(user_id):
        if user_id == ADMIN_ID or Utilities.is_admin(user_id):
            return True
        settings = DatabaseManager.get_settings()
        channels = settings.get('channels', [])
        if not channels:
            return True
        try:
            for ch in channels:
                member = bot.get_chat_member(ch["username"], user_id)
                if member.status in ['left', 'kicked']:
                    return False
            return True
        except:
            return True

    @staticmethod
    def is_admin(user_id):
        if user_id == ADMIN_ID:
            return True
        admins = DatabaseManager.get_admins()
        return user_id in admins

    @staticmethod
    def is_main_admin(user_id):
        return user_id == ADMIN_ID

    @staticmethod
    def add_admin(user_id):
        admins = DatabaseManager.get_admins()
        if user_id not in admins:
            admins.append(user_id)
            DatabaseManager.save_admins(admins)
            return True
        return False

    @staticmethod
    def remove_admin(user_id):
        if user_id == ADMIN_ID:
            return False
        admins = DatabaseManager.get_admins()
        if user_id in admins:
            admins.remove(user_id)
            DatabaseManager.save_admins(admins)
            return True
        return False

    @staticmethod
    def get_thumb():
        settings = DatabaseManager.get_settings()
        thumb = settings.get('file_thumb')
        if thumb and os.path.exists(thumb):
            return thumb
        return None

    @staticmethod
    def verify_file_access(fid, user_id):
        files = DatabaseManager.get_files()
        if fid not in files:
            return False
        file_info = files[fid]
        file_user_id = file_info.get('user_id')
        if user_id == ADMIN_ID or Utilities.is_admin(user_id):
            return True
        if file_user_id == user_id:
            return True
        if file_info.get('type') == 'store':
            store = DatabaseManager.get_store()
            if fid in store:
                return True
        return False

    @staticmethod
    def get_logs(fid, lines=40):
        log_path = os.path.join(LOGS_DIR, f"{fid}.log")
        try:
            if os.path.exists(log_path) and os.path.getsize(log_path) > 0:
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    all_lines = f.readlines()
                    last = all_lines[-lines:] if len(all_lines) > lines else all_lines
                    output = "".join(last)
                    safe = escape(output)
                    if len(safe) > 3000:
                        safe = safe[:3000] + "\n..."
                    return f"<pre><code>{safe}</code></pre>"
            return "No output available."
        except:
            return "Error reading logs."

    @staticmethod
    def update_token_in_memory(content, new_token):
        try:
            keywords = ["TOKEN", "bot_token", "api_key", "tok", "TKN", "BOT_TKN", "API_TOKEN"]
            pattern = r"(['\"])\d{8,12}:[a-zA-Z0-9_-]{35,}(['\"])"
            new_content = re.sub(pattern, f"\\1{new_token}\\2", content)
            for kw in keywords:
                kw_pattern = rf"{kw}\s*=\s*(['\"])[^'\"]+(['\"])"
                new_content = re.sub(kw_pattern, f"{kw} = \\1{new_token}\\2", new_content)
            return new_content
        except:
            return None

    @staticmethod
    def check_token(token):
        try:
            url = f"https://api.telegram.org/bot{token}/getMe"
            res = requests.get(url, timeout=15).json()
            if res.get("ok"):
                return True, res["result"]
            return False, res.get("description")
        except Exception as e:
            return False, str(e)

    @staticmethod
    def auto_fix_code(code):
        fixes = [
            (r'print\s+(\S+)', r'print(\1)'),
            (r'raw_input', 'input'),
            (r'xrange', 'range'),
            (r'\.iteritems\(\)', '.items()'),
            (r'\.itervalues\(\)', '.values()'),
            (r'\.iterkeys\(\)', '.keys()'),
        ]
        for pattern, replacement in fixes:
            code = re.sub(pattern, replacement, code)
        return code

    @staticmethod
    def create_zip(files_list, zip_name):
        zip_path = os.path.join(TEMP_DIR, zip_name)
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for file_path in files_list:
                if os.path.exists(file_path):
                    zipf.write(file_path, os.path.basename(file_path))
        return zip_path

    @staticmethod
    def set_cancel(uid, state=True):
        cancel_states[uid] = state

    @staticmethod
    def is_cancelled(uid):
        return cancel_states.get(uid, False)

    @staticmethod
    def clear_cancel(uid):
        if uid in cancel_states:
            del cancel_states[uid]

    @staticmethod
    def cleanup_temp_files():
        try:
            for f in os.listdir(TEMP_DIR):
                path = os.path.join(TEMP_DIR, f)
                if os.path.isfile(path):
                    os.remove(path)
        except:
            pass

    @staticmethod
    def cleanup_old_logs():
        try:
            now = time.time()
            for f in os.listdir(LOGS_DIR):
                path = os.path.join(LOGS_DIR, f)
                if os.path.isfile(path):
                    if os.path.getsize(path) > RESOURCE_LIMITS['max_log_size_mb'] * 1024 * 1024:
                        with open(path, 'w') as fp:
                            fp.truncate(0)
                    if now - os.path.getmtime(path) > 7 * 86400:
                        os.remove(path)
        except:
            pass

TRANSLATIONS = {
    'welcome': {
        'en': 'Welcome {name}!\n\nRank: {rank}\nPoints: {points}\nMember since: {date}',
        'ar': 'أهلاً {name}!\n\nالرتبة: {rank}\nالنقاط: {points}\nعضو منذ: {date}'
    },
    'main_menu_title': {'en': 'Main Menu', 'ar': 'القائمة الرئيسية'},
    'main_menu_rank': {'en': 'Rank: {rank}', 'ar': 'الرتبة: {rank}'},
    'main_menu_points': {'en': 'Points: {points}', 'ar': 'النقاط: {points}'},
    'upload': {'en': 'Upload New File', 'ar': 'رفع ملف جديد'},
    'my_files': {'en': 'My Files', 'ar': 'ملفاتي'},
    'store': {'en': 'Store', 'ar': 'المتجر'},
    'wallet': {'en': 'Wallet', 'ar': 'المحفظة'},
    'profile': {'en': 'Profile', 'ar': 'الملف الشخصي'},
    'install_library': {'en': 'Install Library', 'ar': 'تثبيت مكتبة'},
    'settings': {'en': 'Settings', 'ar': 'الإعدادات'},
    'contact_dev': {'en': 'Contact Developer', 'ar': 'تواصل مع المطور'},
    'admin_panel': {'en': 'Admin Panel', 'ar': 'لوحة الإدارة'},
    'pro_panel': {'en': 'Pro Panel', 'ar': 'لوحة Pro'},
    'download_all': {'en': 'Download All', 'ar': 'تحميل الكل'},
    'auto_fix': {'en': 'Auto Fix', 'ar': 'إصلاح تلقائي'},
    'test_run': {'en': 'Test Run', 'ar': 'تشغيل تجريبي'},
    'sell_store': {'en': 'Sell in Store', 'ar': 'بيع في المتجر'},
    'back': {'en': 'Back', 'ar': 'رجوع'},
    'cancel': {'en': 'Cancel', 'ar': 'إلغاء'},
    'bot_locked': {'en': 'Bot Locked', 'ar': 'البوت مغلق'},
    'bot_locked_desc': {'en': 'Service is temporarily paused.\nContact support via the button below.', 'ar': 'الخدمة موقفة مؤقتاً.\nتواصل مع الدعم عبر الزر أدناه.'},
    'subscription_required': {'en': 'Subscription Required', 'ar': 'اشتراك مطلوب'},
    'subscription_desc': {'en': 'Please join the following channels to continue:', 'ar': 'يرجى الاشتراك في القنوات التالية للمتابعة:'},
    'verify': {'en': 'Verify', 'ar': 'تحقق'},
    'join': {'en': 'Join {name}', 'ar': 'انضم {name}'},
    'language_selection': {'en': 'Select Language', 'ar': 'اختر اللغة'},
    'choose_lang': {'en': 'Please choose your preferred language:', 'ar': 'يرجى اختيار لغتك المفضلة:'},
    'english': {'en': 'English', 'ar': 'الإنجليزية'},
    'arabic': {'en': 'Arabic', 'ar': 'العربية'},
    'settings_title': {'en': 'Settings', 'ar': 'الإعدادات'},
    'change_lang': {'en': 'Change Language', 'ar': 'تغيير اللغة'},
    'change_style': {'en': 'Change Button Color', 'ar': 'تغيير لون الأزرار'},
    'style_default': {'en': 'Default', 'ar': 'افتراضي'},
    'style_primary': {'en': 'Blue (Primary)', 'ar': 'أزرق (رئيسي)'},
    'style_success': {'en': 'Green (Success)', 'ar': 'أخضر (نجاح)'},
    'style_danger': {'en': 'Red (Danger)', 'ar': 'أحمر (خطر)'},
    'style_updated': {'en': 'Button color updated.', 'ar': 'تم تحديث لون الأزرار.'},
    'lang_updated': {'en': 'Language updated.', 'ar': 'تم تحديث اللغة.'},
    'wallet_title': {'en': 'Wallet', 'ar': 'المحفظة'},
    'balance': {'en': 'Balance: {balance}', 'ar': 'الرصيد: {balance}'},
    'rank': {'en': 'Rank: {rank}', 'ar': 'الرتبة: {rank}'},
    'vip_expiry': {'en': 'VIP expiry: {expiry}', 'ar': 'صلاحية VIP: {expiry}'},
    'points_info': {'en': 'Each point = 1 hour of hosting.', 'ar': 'كل نقطة = ساعة استضافة.'},
    'daily_bonus': {'en': 'Daily Bonus', 'ar': 'المكافأة اليومية'},
    'referral_link': {'en': 'Referral Link', 'ar': 'رابط الإحالة'},
    'daily_claimed': {'en': 'Already claimed today!', 'ar': 'تم المطالبة اليوم!'},
    'daily_earned': {'en': 'You earned {points} points!', 'ar': 'لقد حصلت على {points} نقاط!'},
    'referral_text': {'en': 'Your referral link:\n<code>{link}</code>\n\nYou earn 10 points for each new user!', 'ar': 'رابط الإحالة الخاص بك:\n<code>{link}</code>\n\nتكسب 10 نقاط لكل مستخدم جديد!'},
    'help_title': {'en': 'Help', 'ar': 'المساعدة'},
    'help_text': {'en': 'Help Guide\n\nUpload a .py file and choose hosting type.\nFree hosting consumes points (1 point per hour).\nVIP hosting is unlimited.\n\nEarn points via daily bonus and referrals.\nManage your files from the "My Files" section.\nUse the terminal to interact with running bots.', 'ar': 'دليل المساعدة\n\nارفع ملف .py واختر نوع الاستضافة.\nالاستضافة المجانية تستهلك نقاط (نقطة لكل ساعة).\nاستضافة VIP غير محدودة.\n\nاحصل على نقاط عبر المكافأة اليومية والإحالات.\nأدر ملفاتك من قسم "ملفاتي".\nاستخدم الطرفية للتفاعل مع البوتات العاملة.'},
    'upload_choice': {'en': 'Choose hosting type:', 'ar': 'اختر نوع الاستضافة:'},
    'free_host': {'en': 'Free (points)', 'ar': 'مجاني (نقاط)'},
    'vip_host': {'en': 'VIP (unlimited)', 'ar': 'VIP (غير محدود)'},
    'send_file': {'en': 'Send your .py file:', 'ar': 'أرسل ملف .py الخاص بك:'},
    'invalid_file': {'en': 'Please send a .py file.', 'ar': 'يرجى إرسال ملف .py.'},
    'set_duration': {'en': 'Set Duration', 'ar': 'تحديد المدة'},
    'duration_prompt': {'en': 'File: <b>{name}</b>\n\nYour points: <code>{points}</code>\n\nEnter number of hours (max {max}):', 'ar': 'الملف: <b>{name}</b>\n\nنقاطك: <code>{points}</code>\n\nأدخل عدد الساعات (الحد الأقصى {max}):'},
    'invalid_number': {'en': 'Please enter a number.', 'ar': 'يرجى إدخال رقم.'},
    'min_hour': {'en': 'Minimum 1 hour.', 'ar': 'ساعة واحدة على الأقل.'},
    'insufficient_points': {'en': 'Required: {required}\nAvailable: {available}', 'ar': 'المطلوب: {required}\nالمتوفر: {available}'},
    'file_uploaded': {'en': 'File uploaded.\n\n{name}\n{type}\n{duration}\n\nWaiting for approval.', 'ar': 'تم رفع الملف.\n\n{name}\n{type}\n{duration}\n\nفي انتظار الموافقة.'},
    'file_accepted': {'en': 'File accepted automatically!\n\n{name}\n{duration}\nNow running.', 'ar': 'تم قبول الملف تلقائياً!\n\n{name}\n{duration}\nيعمل الآن.'},
    'file_approved': {'en': 'Your file has been approved!\n\n{name}\n{duration}\nNow running.', 'ar': 'تمت الموافقة على ملفك!\n\n{name}\n{duration}\nيعمل الآن.'},
    'file_rejected': {'en': 'Your file \'{name}\' has been rejected.', 'ar': 'تم رفض ملفك \'{name}\'.'},
    'my_files_title': {'en': 'My Files', 'ar': 'ملفاتي'},
    'files_count': {'en': 'Files: {count}', 'ar': 'الملفات: {count}'},
    'running_count': {'en': 'Running: {count}', 'ar': 'يعمل: {count}'},
    'stopped_count': {'en': 'Stopped: {count}', 'ar': 'متوقف: {count}'},
    'no_files': {'en': 'No files.', 'ar': 'لا توجد ملفات.'},
    'file_manager': {'en': 'File Manager', 'ar': 'إدارة الملف'},
    'file_status': {'en': 'Status: {status}', 'ar': 'الحالة: {status}'},
    'file_remaining': {'en': 'Remaining: {remaining}', 'ar': 'المتبقي: {remaining}'},
    'file_type': {'en': 'Type: {type}', 'ar': 'النوع: {type}'},
    'file_created': {'en': 'Created: {created}', 'ar': 'تاريخ الإنشاء: {created}'},
    'start': {'en': 'Start', 'ar': 'تشغيل'},
    'stop': {'en': 'Stop', 'ar': 'إيقاف'},
    'terminal': {'en': 'Terminal', 'ar': 'الطرفية'},
    'change_token': {'en': 'Change Token', 'ar': 'تغيير التوكن'},
    'token_info': {'en': 'Token Info', 'ar': 'معلومات التوكن'},
    'download': {'en': 'Download', 'ar': 'تحميل'},
    'delete': {'en': 'Delete', 'ar': 'حذف'},
    'confirm_delete': {'en': 'Are you sure you want to delete this file?', 'ar': 'هل أنت متأكد من حذف هذا الملف؟'},
    'yes': {'en': 'Yes', 'ar': 'نعم'},
    'no': {'en': 'No', 'ar': 'لا'},
    'deleted': {'en': 'Deleted: {name}', 'ar': 'تم الحذف: {name}'},
    'terminal_title': {'en': 'Terminal', 'ar': 'الطرفية'},
    'terminal_output': {'en': 'File: {name}\nStatus: {status}\n\nTerminal:\n{output}', 'ar': 'الملف: {name}\nالحالة: {status}\n\nالطرفية:\n{output}'},
    'refresh': {'en': 'Refresh', 'ar': 'تحديث'},
    'input': {'en': 'Input', 'ar': 'إدخال'},
    'input_sent': {'en': 'Sent: <code>{cmd}</code>', 'ar': 'تم الإرسال: <code>{cmd}</code>'},
    'process_not_running': {'en': 'Process not running.', 'ar': 'العملية لا تعمل.'},
    'token_updated': {'en': 'Token updated. Please restart the file.', 'ar': 'تم تحديث التوكن. يرجى إعادة تشغيل الملف.'},
    'token_failed': {'en': 'Failed to update token.', 'ar': 'فشل تحديث التوكن.'},
    'token_valid': {'en': 'Token is valid.', 'ar': 'التوكن صالح.'},
    'token_invalid': {'en': 'Token is invalid.', 'ar': 'التوكن غير صالح.'},
    'no_token': {'en': 'No token found.', 'ar': 'لم يتم العثور على توكن.'},
    'bot_name': {'en': 'Bot name: {name}', 'ar': 'اسم البوت: {name}'},
    'bot_image': {'en': 'Bot image: {state}', 'ar': 'صورة البوت: {state}'},
    'file_thumb': {'en': 'File thumbnail: {state}', 'ar': 'صورة مصغرة للملف: {state}'},
    'auto_approve': {'en': 'Auto-approve: {state}', 'ar': 'موافقة تلقائية: {state}'},
    'enabled': {'en': 'Enabled', 'ar': 'مفعل'},
    'disabled': {'en': 'Disabled', 'ar': 'معطل'},
    'change_name': {'en': 'Change Name', 'ar': 'تغيير الاسم'},
    'change_image': {'en': 'Change Image', 'ar': 'تغيير الصورة'},
    'remove_image': {'en': 'Remove Image', 'ar': 'إزالة الصورة'},
    'add_image': {'en': 'Add Image', 'ar': 'إضافة صورة'},
    'change_thumb': {'en': 'Change Thumbnail', 'ar': 'تغيير الصورة المصغرة'},
    'remove_thumb': {'en': 'Remove Thumbnail', 'ar': 'إزالة الصورة المصغرة'},
    'add_thumb': {'en': 'Add Thumbnail', 'ar': 'إضافة صورة مصغرة'},
    'name_set': {'en': 'Name set to: {name}', 'ar': 'تم تعيين الاسم: {name}'},
    'image_updated': {'en': 'Image updated.', 'ar': 'تم تحديث الصورة.'},
    'thumb_updated': {'en': 'Thumbnail updated.', 'ar': 'تم تحديث الصورة المصغرة.'},
    'admin_panel_title': {'en': 'Admin Panel', 'ar': 'لوحة الإدارة'},
    'admin_stats': {'en': 'Users: {users}\nFiles: {files}\nPending: {pending}\nActive: {active}\nAdmins: {admins}\n\nBot state: {state}\nAuto-approve: {auto}', 'ar': 'المستخدمين: {users}\nالملفات: {files}\nالمعلقة: {pending}\nالنشطة: {active}\nالأدمن: {admins}\n\nحالة البوت: {state}\nالموافقة التلقائية: {auto}'},
    'unlock': {'en': 'Unlock', 'ar': 'فتح'},
    'lock': {'en': 'Lock', 'ar': 'قفل'},
    'auto_approve_toggle': {'en': 'Auto-approve', 'ar': 'موافقة تلقائية'},
    'manual_approve': {'en': 'Manual approve', 'ar': 'موافقة يدوية'},
    'users_list': {'en': 'Users', 'ar': 'المستخدمين'},
    'admins_list': {'en': 'Admins', 'ar': 'الأدمن'},
    'store_management': {'en': 'Store Management', 'ar': 'إدارة المتجر'},
    'pending_files': {'en': 'Pending Files', 'ar': 'الملفات المعلقة'},
    'broadcast': {'en': 'Broadcast', 'ar': 'إذاعة'},
    'channels': {'en': 'Channels', 'ar': 'القنوات'},
    'all_files': {'en': 'All Files', 'ar': 'جميع الملفات'},
    'stop_all': {'en': 'Stop All', 'ar': 'إيقاف الكل'},
    'pending_count': {'en': 'Pending: {count}', 'ar': 'المعلقة: {count}'},
    'file_review': {'en': 'Review', 'ar': 'مراجعة'},
    'file_owner': {'en': 'Owner: {owner}', 'ar': 'المالك: {owner}'},
    'approve': {'en': 'Approve', 'ar': 'قبول'},
    'reject': {'en': 'Reject', 'ar': 'رفض'},
    'user_management': {'en': 'User Management', 'ar': 'إدارة المستخدم'},
    'user_id': {'en': 'ID: {id}', 'ar': 'المعرف: {id}'},
    'user_username': {'en': 'Username: @{username}', 'ar': 'اسم المستخدم: @{username}'},
    'user_joined': {'en': 'Joined: {date}', 'ar': 'انضم: {date}'},
    'user_points': {'en': 'Points: {points}', 'ar': 'النقاط: {points}'},
    'user_rank': {'en': 'Rank: {rank}', 'ar': 'الرتبة: {rank}'},
    'user_expiry': {'en': 'VIP expiry: {expiry}', 'ar': 'صلاحية VIP: {expiry}'},
    'user_files': {'en': 'Files: {files}', 'ar': 'الملفات: {files}'},
    'user_status': {'en': 'Status: {status}', 'ar': 'الحالة: {status}'},
    'active': {'en': 'Active', 'ar': 'نشط'},
    'banned': {'en': 'Banned', 'ar': 'محظور'},
    'ban': {'en': 'Ban', 'ar': 'حظر'},
    'unban': {'en': 'Unban', 'ar': 'فك الحظر'},
    'grant_vip': {'en': 'Grant VIP', 'ar': 'منح VIP'},
    'remove_vip': {'en': 'Remove VIP', 'ar': 'إزالة VIP'},
    'charge': {'en': 'Charge', 'ar': 'شحن'},
    'message_user': {'en': 'Message', 'ar': 'رسالة'},
    'charge_points': {'en': 'Enter points to add:', 'ar': 'أدخل النقاط للإضافة:'},
    'charge_success': {'en': 'Added {amount} points.', 'ar': 'تم إضافة {amount} نقاط.'},
    'message_sent': {'en': 'Message sent.', 'ar': 'تم إرسال الرسالة.'},
    'grant_vip_prompt': {'en': 'Enter days (0 for lifetime):', 'ar': 'أدخل عدد الأيام (0 مدى الحياة):'},
    'grant_vip_success': {'en': 'VIP granted for {duration}.', 'ar': 'تم منح VIP لمدة {duration}.'},
    'remove_vip_success': {'en': 'VIP removed.', 'ar': 'تم إزالة VIP.'},
    'add_admin': {'en': 'Add Admin', 'ar': 'إضافة أدمن'},
    'add_admin_prompt': {'en': 'Enter the user ID:', 'ar': 'أدخل معرف المستخدم:'},
    'admin_added': {'en': 'Admin added: {id}', 'ar': 'تم إضافة الأدمن: {id}'},
    'admin_exists': {'en': 'User is already an admin.', 'ar': 'المستخدم أدمن بالفعل.'},
    'admin_removed': {'en': 'Admin removed.', 'ar': 'تم إزالة الأدمن.'},
    'cannot_remove_owner': {'en': 'Cannot remove the main owner!', 'ar': 'لا يمكن إزالة المالك الرئيسي!'},
    'only_owner': {'en': 'Only the main owner can do this.', 'ar': 'فقط المالك الرئيسي يمكنه فعل هذا.'},
    'store_item': {'en': 'File: {name}\nPrice: {price}', 'ar': 'الملف: {name}\nالسعر: {price}'},
    'add_store_file': {'en': 'Add Store File', 'ar': 'إضافة ملف للمتجر'},
    'set_price': {'en': 'Set Price', 'ar': 'تحديد السعر'},
    'price_prompt': {'en': 'Enter price in points:', 'ar': 'أدخل السعر بالنقاط:'},
    'store_added': {'en': 'Added: {name}\nPrice: {price}', 'ar': 'تم الإضافة: {name}\nالسعر: {price}'},
    'price_updated': {'en': 'Price updated to {price}.', 'ar': 'تم تحديث السعر إلى {price}.'},
    'store_deleted': {'en': 'Deleted: {name}', 'ar': 'تم الحذف: {name}'},
    'broadcast_sending': {'en': 'Sending to {count} users...', 'ar': 'جاري الإرسال لـ {count} مستخدم...'},
    'broadcast_complete': {'en': 'Broadcast complete.\n\nSuccessful: {success}\nFailed: {failed}\nTotal: {total}', 'ar': 'اكتملت الإذاعة.\n\nنجح: {success}\nفشل: {failed}\nالإجمالي: {total}'},
    'channels_list': {'en': 'Channels: {count}', 'ar': 'القنوات: {count}'},
    'add_channel': {'en': 'Add Channel', 'ar': 'إضافة قناة'},
    'add_channel_prompt': {'en': 'Send the channel username (e.g., @channel):', 'ar': 'أرسل معرف القناة (مثال: @channel):'},
    'channel_added': {'en': 'Added: {name}', 'ar': 'تم الإضافة: {name}'},
    'channel_not_found': {'en': 'Channel not found.', 'ar': 'القناة غير موجودة.'},
    'channel_removed': {'en': 'Removed: {name}', 'ar': 'تم الإزالة: {name}'},
    'library_install': {'en': 'Installing library: {lib}', 'ar': 'جاري تثبيت المكتبة: {lib}'},
    'library_installed': {'en': 'Installed: {lib}', 'ar': 'تم التثبيت: {lib}'},
    'library_timeout': {'en': 'Timeout: {lib}', 'ar': 'انتهت المهلة: {lib}'},
    'library_failed': {'en': 'Failed: {lib}', 'ar': 'فشل: {lib}'},
    'edit_store': {'en': 'Edit Store Item', 'ar': 'تعديل عنصر المتجر'},
    'change_price': {'en': 'Change Price', 'ar': 'تغيير السعر'},
    'buy': {'en': 'Buy', 'ar': 'شراء'},
    'buy_confirm_text': {'en': 'File: {name}\nPrice: {price}\nYour balance: <code>{balance}</code>\n\n{status}', 'ar': 'الملف: {name}\nالسعر: {price}\nرصيدك: <code>{balance}</code>\n\n{status}'},
    'sufficient': {'en': 'Sufficient points!', 'ar': 'نقاط كافية!'},
    'insufficient': {'en': 'Insufficient points!', 'ar': 'نقاط غير كافية!'},
    'purchase_success': {'en': 'Purchase successful!', 'ar': 'تم الشراء بنجاح!'},
    'purchase_failed': {'en': 'Purchase failed.', 'ar': 'فشل الشراء.'},
    'store_empty': {'en': 'Store is empty.', 'ar': 'المتجر فارغ.'},
    'test_run_select': {'en': 'Select a file to test:', 'ar': 'اختر ملفاً للتشغيل التجريبي:'},
    'test_run_success': {'en': 'Test run successful!', 'ar': 'تم التشغيل التجريبي بنجاح!'},
    'test_run_error': {'en': 'Error: {error}', 'ar': 'خطأ: {error}'},
    'access_denied': {'en': 'Access denied!', 'ar': 'ممنوع الوصول!'},
    'file_not_found': {'en': 'File not found!', 'ar': 'الملف غير موجود!'},
    'download_failed': {'en': 'Download failed!', 'ar': 'فشل التحميل!'},
    'no_files_to_download': {'en': 'No files to download!', 'ar': 'لا توجد ملفات للتحميل!'},
    'vip_only': {'en': 'VIP only!', 'ar': 'VIP فقط!'},
    'insufficient_points_short': {'en': 'Insufficient points!', 'ar': 'نقاط غير كافية!'},
    'file_saved': {'en': 'File saved successfully.', 'ar': 'تم حفظ الملف بنجاح.'},
    'save_failed': {'en': 'Failed to save file.', 'ar': 'فشل حفظ الملف.'},
    'new_user_notify': {'en': 'New user registered!\n\nName: {name}\nID: <code>{id}</code>\nUsername: {username}\nDate: {date}', 'ar': 'مستخدم جديد!\n\nالاسم: {name}\nالمعرف: <code>{id}</code>\nاسم المستخدم: {username}\nالتاريخ: {date}'},
    'user_banned_notify': {'en': 'You have been banned.', 'ar': 'لقد تم حظرك.'},
    'user_unbanned_notify': {'en': 'Your ban has been lifted.', 'ar': 'تم رفع الحظر عنك.'},
    'vip_granted_notify': {'en': 'You have been upgraded to VIP for {duration}.', 'ar': 'تم ترقيتك إلى VIP لمدة {duration}.'},
    'vip_removed_notify': {'en': 'Your VIP status has been removed.', 'ar': 'تم إلغاء صلاحية VIP الخاصة بك.'},
    'points_added_notify': {'en': '<b>{amount}</b> points have been added to your balance.', 'ar': 'تم إضافة <b>{amount}</b> نقاط إلى رصيدك.'},
    'admin_promoted_notify': {'en': 'You have been made an admin!', 'ar': 'لقد تم تعيينك أدمن!'},
    'file_upload_notify': {'en': 'New file upload\n\nUser: {user}\nID: <code>{id}</code>\nFile: {file}\nType: {type}\nDuration: {duration}', 'ar': 'رفع ملف جديد\n\nالمستخدم: {user}\nالمعرف: <code>{id}</code>\nالملف: {file}\nالنوع: {type}\nالمدة: {duration}'},
    'time_expired_notify': {'en': 'Your bot \'{name}\' has reached its time limit.', 'ar': 'انتهت مدة البوت \'{name}\'.'},
    'stopped_subscription_notify': {'en': 'Your bot \'{name}\' was stopped due to missing subscription.', 'ar': 'تم إيقاف البوت \'{name}\' بسبب عدم الاشتراك.'},
    'resource_limit_notify': {'en': 'Your bot \'{name}\' was stopped due to exceeding resource limits.', 'ar': 'تم إيقاف البوت \'{name}\' بسبب تجاوز حدود الموارد.'},
    'system_usage': {'en': 'System Usage:\nCPU: {cpu}%\nMemory: {mem_mb} MB\nActive processes: {processes}', 'ar': 'استخدام النظام:\nCPU: {cpu}%\nالذاكرة: {mem_mb} ميجابايت\nالعمليات النشطة: {processes}'},
    'not_subscribed': {'en': 'You are not subscribed.', 'ar': 'أنت غير مشترك.'},
    'subscribe_first': {'en': 'Please subscribe first.', 'ar': 'يرجى الاشتراك أولاً.'},
    'previous': {'en': 'Previous', 'ar': 'السابق'},
    'next': {'en': 'Next', 'ar': 'التالي'},
    'locked': {'en': 'Locked', 'ar': 'مقفل'},
    'unlocked': {'en': 'Unlocked', 'ar': 'مفتوح'},
    'enter_library_name': {'en': 'Enter the library name to install:', 'ar': 'أدخل اسم المكتبة للتثبيت:'},
    'enter_message': {'en': 'Enter the message to send:', 'ar': 'أدخل الرسالة للإرسال:'},
    'send_token': {'en': 'Send the new token:', 'ar': 'أرسل التوكن الجديد:'},
    'enter_name': {'en': 'Enter the new bot name:', 'ar': 'أدخل اسم البوت الجديد:'},
    'send_image': {'en': 'Send an image:', 'ar': 'أرسل صورة:'},
    'error': {'en': 'Error', 'ar': 'خطأ'},
    'success': {'en': 'Success', 'ar': 'نجاح'},
    'invalid_user_id': {'en': 'Invalid user ID.', 'ar': 'معرف المستخدم غير صالح.'},
    'failed': {'en': 'Operation failed.', 'ar': 'فشلت العملية.'},
    'invalid_price': {'en': 'Invalid price.', 'ar': 'سعر غير صالح.'},
    'referral_bonus': {'en': 'Referral Bonus', 'ar': 'مكافأة الإحالة'},
    'approved': {'en': 'Approved', 'ar': 'تم القبول'},
    'rejected': {'en': 'Rejected', 'ar': 'تم الرفض'},
    'no_pending': {'en': 'No pending files.', 'ar': 'لا توجد ملفات معلقة.'},
    'running': {'en': 'Running', 'ar': 'يعمل'},
    'stopped': {'en': 'Stopped', 'ar': 'متوقف'},
    'pending_review': {'en': 'Pending Review', 'ar': 'قيد المراجعة'},
    'accepted': {'en': 'Accepted', 'ar': 'تم القبول'},
    'file': {'en': 'File: {name}', 'ar': 'الملف: {name}'},
    'duration': {'en': 'Duration: {duration}', 'ar': 'المدة: {duration}'},
    'unbanned': {'en': 'Unbanned', 'ar': 'تم رفع الحظر'},
    'done': {'en': 'Done', 'ar': 'تم'},
    'downloaded': {'en': 'Downloaded', 'ar': 'تم التحميل'},
    'started': {'en': 'Started', 'ar': 'تم التشغيل'},
    'start_failed': {'en': 'Failed to start', 'ar': 'فشل التشغيل'},
    'all_stopped': {'en': 'All processes stopped.', 'ar': 'تم إيقاف جميع العمليات.'},
    'image_removed': {'en': 'Image removed.', 'ar': 'تم إزالة الصورة.'},
    'thumb_removed': {'en': 'Thumbnail removed.', 'ar': 'تم إزالة الصورة المصغرة.'},
    'invalid_username': {'en': 'Invalid username.', 'ar': 'اسم المستخدم غير صالح.'},
    'time_expired': {'en': 'Time Expired', 'ar': 'انتهى الوقت'},
    'vip_removed': {'en': 'VIP removed.', 'ar': 'تم إزالة VIP.'},
}

def init_database():
    global db
    client = pymongo.MongoClient(MONGODB_URI)
    db = client.get_default_database()

    default_channels = [
        {"username": "@F7_7G", "name": "F7_7G"},
        {"username": "@H_U_VB", "name": "H_U_VB"},
        {"username": "@seed_1k", "name": "seed_1k"},
        {"username": "@TERBO_CODE", "name": "TERBO_CODE"},
        {"username": "@BQBOOB1", "name": "BQBOOB1"},
        {"username": "@bshshshkk", "name": "bshshshkk"},
        {"username": "@EQJ_1", "name": "EQJ_1"},
        {"username": "@HAMO_X_OT3", "name": "HAMO_X_OT3"}
    ]
    settings = DatabaseManager.get_settings()
    if 'channels' not in settings:
        settings['channels'] = default_channels
    defaults = {
        "bot_name": "Hosting Bot",
        "bot_image": None,
        "file_thumb": None,
        "bot_locked": False,
        "auto_approve": True
    }
    for key, value in defaults.items():
        if key not in settings:
            settings[key] = value
    DatabaseManager.save_settings(settings)

    admins = DatabaseManager.get_admins()
    if ADMIN_ID not in admins:
        admins.append(ADMIN_ID)
        DatabaseManager.save_admins(admins)

    security = DatabaseManager.get_security()
    if 'master_key' not in security:
        master_key = base64.b64encode(get_random_bytes(32)).decode('utf-8')
        security['master_key'] = master_key
        security['file_keys'] = {}
        DatabaseManager.save_security(security)

def build_main_keyboard(uid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'upload'), "nav_upload", uid))
    kb.row(
        Utilities.create_button(Utilities.get_text(uid, 'my_files'), "nav_files", uid),
        Utilities.create_button(Utilities.get_text(uid, 'store'), "nav_store", uid)
    )
    kb.row(
        Utilities.create_button(Utilities.get_text(uid, 'wallet'), "nav_wallet", uid),
        Utilities.create_button(Utilities.get_text(uid, 'profile'), "nav_stats", uid)
    )
    kb.row(
        Utilities.create_button(Utilities.get_text(uid, 'install_library'), "nav_lib", uid),
        Utilities.create_button(Utilities.get_text(uid, 'settings'), "nav_settings", uid)
    )
    if Utilities.is_user_pro(uid):
        kb.row(
            Utilities.create_button(Utilities.get_text(uid, 'pro_panel'), "nav_pro", uid)
        )
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'contact_dev'), None, uid, url=f"tg://user?id={ADMIN_ID}"))
    if Utilities.is_admin(uid):
        kb.add(Utilities.create_button(Utilities.get_text(uid, 'admin_panel'), "nav_admin", uid))
    return kb

def build_pro_keyboard(uid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'download_all'), "pro_download_all", uid))
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'auto_fix'), "pro_auto_fix", uid))
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'test_run'), "pro_test_run", uid))
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'sell_store'), "pro_sell", uid))
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), "nav_main", uid))
    return kb

def build_cancel_keyboard(uid, data="cancel"):
    kb = types.InlineKeyboardMarkup()
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'cancel'), data, uid))
    return kb

def build_back_keyboard(uid, data="nav_main"):
    kb = types.InlineKeyboardMarkup()
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), data, uid))
    return kb

def build_language_keyboard(uid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(Utilities.create_button("English", "set_lang_en", uid))
    kb.add(Utilities.create_button("العربية", "set_lang_ar", uid))
    return kb

def build_style_keyboard(uid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'style_default'), "set_style_default", uid, style_override='default'))
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'style_primary'), "set_style_primary", uid, style_override='primary'))
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'style_success'), "set_style_success", uid, style_override='success'))
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'style_danger'), "set_style_danger", uid, style_override='danger'))
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), "nav_settings", uid))
    return kb

def build_settings_keyboard(uid):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'change_lang'), "nav_change_lang", uid))
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'change_style'), "nav_change_style", uid))
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), "nav_main", uid))
    return kb

@bot.message_handler(commands=['start'])
def start_command(msg):
    try:
        uid = msg.from_user.id
        settings = DatabaseManager.get_settings()
        if settings.get('bot_locked', False) and not Utilities.is_admin(uid):
            try:
                bot.delete_message(msg.chat.id, msg.message_id)
            except:
                pass
            Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'bot_locked', 'bot_locked_desc'),
                                   types.InlineKeyboardMarkup().add(Utilities.create_button(Utilities.get_text(uid, 'contact_dev'), None, uid, url=f"tg://user?id={ADMIN_ID}")))
            return
        users = DatabaseManager.get_users()
        Utilities.clear_cancel(uid)
        if str(uid) not in users:
            if len(msg.text.split()) > 1:
                ref = msg.text.split()[1]
                if ref.isdigit() and int(ref) != uid:
                    udb = DatabaseManager.get_users()
                    if str(ref) in udb:
                        udb[str(ref)]['points'] = udb[str(ref)].get('points', 0) + 10
                        DatabaseManager.save_users(udb)
                        try:
                            bot.send_message(int(ref), Utilities.format_border(uid, 'referral_bonus', 'You earned 10 points for referring a new user!'))
                        except:
                            pass
            users[str(uid)] = {
                'username': msg.from_user.username,
                'first_name': msg.from_user.first_name,
                'last_name': msg.from_user.last_name,
                'points': 10,
                'join_date': str(datetime.now().date()),
                'is_banned': 0,
                'expiry': None,
                'last_daily': None,
                'notifications': True,
                'lang': 'en',
                'button_style': 'default'
            }
            DatabaseManager.save_users(users)
            user_notifications[uid] = True
            try:
                name = escape(f"{msg.from_user.first_name} {msg.from_user.last_name or ''}")
                uname = f"@{msg.from_user.username}" if msg.from_user.username else "None"
                cap = Utilities.get_text(uid, 'new_user_notify', name=name, id=uid, username=uname, date=datetime.now().strftime('%Y-%m-%d %H:%M'))
                for adm in DatabaseManager.get_admins():
                    try:
                        photos = bot.get_user_profile_photos(uid)
                        if photos.total_count > 0:
                            bot.send_photo(adm, photos.photos[0][-1].file_id, caption=cap, parse_mode="HTML")
                        else:
                            bot.send_message(adm, cap, parse_mode="HTML")
                    except:
                        pass
            except:
                pass
        users = DatabaseManager.get_users()
        if users.get(str(uid), {}).get('is_banned', 0) == 1:
            bot.send_message(msg.chat.id, Utilities.format_border(uid, 'banned', 'You have been banned.'))
            return
        if not Utilities.check_subscription(uid):
            subscription_required(msg.chat.id, uid)
            return
        try:
            bot.delete_message(msg.chat.id, msg.message_id)
        except:
            pass
        u = users.get(str(uid), {})
        if 'lang' not in u:
            lang_text = Utilities.get_text(uid, 'choose_lang')
            Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'language_selection', 'choose_lang'),
                                   build_language_keyboard(uid))
            return
        vip = Utilities.is_user_pro(uid)
        rank = 'VIP' if vip else 'Free'
        rank_ar = 'VIP' if vip else 'مجاني'
        text = Utilities.get_text(uid, 'welcome', name=escape(msg.from_user.first_name), rank=rank, points=u.get('points', 0), date=u.get('join_date', 'today'))
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'main_menu_title', text), build_main_keyboard(uid))
    except Exception as e:
        print(f"Start error: {e}")

def subscription_required(chat_id, uid):
    settings = DatabaseManager.get_settings()
    channels = settings.get('channels', [])
    if not channels:
        return
    kb = types.InlineKeyboardMarkup(row_width=1)
    for ch in channels:
        kb.add(Utilities.create_button(Utilities.get_text(uid, 'join', name=ch['name']), f"https://t.me/{ch['username'].replace('@', '')}", uid))
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'verify'), "check_sub", uid))
    Utilities.send_message(chat_id, uid, Utilities.format_border(uid, 'subscription_required', 'subscription_desc'), kb)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        uid = call.from_user.id
        cid = call.message.chat.id
        data = call.data
        users = DatabaseManager.get_users()
        settings = DatabaseManager.get_settings()
        if settings.get('bot_locked', False) and not Utilities.is_admin(uid):
            bot.answer_callback_query(call.id, "Bot is locked!", show_alert=True)
            Utilities.send_message(cid, uid, Utilities.format_border(uid, 'bot_locked', 'bot_locked_desc'),
                                   types.InlineKeyboardMarkup().add(Utilities.create_button(Utilities.get_text(uid, 'contact_dev'), f"tg://user?id={ADMIN_ID}", uid)))
            return
        if str(uid) in users and users[str(uid)].get('is_banned', 0) == 1:
            bot.answer_callback_query(call.id, "You are banned!", show_alert=True)
            return
        if data == "cancel":
            Utilities.set_cancel(uid, True)
            bot.answer_callback_query(call.id, Utilities.get_text(uid, 'cancel'))
            u = users.get(str(uid), {})
            vip = Utilities.is_user_pro(uid)
            rank = 'VIP' if vip else 'Free'
            text = Utilities.get_text(uid, 'main_menu_rank', rank=rank) + '\n' + Utilities.get_text(uid, 'main_menu_points', points=u.get('points', 0))
            Utilities.edit_message(call, uid, Utilities.format_border(uid, 'main_menu_title', text), build_main_keyboard(uid))
            return
        if data == "cancel_admin":
            Utilities.set_cancel(uid, True)
            bot.answer_callback_query(call.id, Utilities.get_text(uid, 'cancel'))
            admin_panel(call, uid)
            return
        if data == "check_sub":
            if Utilities.check_subscription(uid):
                bot.answer_callback_query(call.id, Utilities.get_text(uid, 'verify'))
                u = users.get(str(uid), {})
                if 'lang' not in u:
                    Utilities.edit_message(call, uid, Utilities.format_border(uid, 'language_selection', 'choose_lang'),
                                          build_language_keyboard(uid))
                    return
                vip = Utilities.is_user_pro(uid)
                rank = 'VIP' if vip else 'Free'
                text = Utilities.get_text(uid, 'main_menu_rank', rank=rank) + '\n' + Utilities.get_text(uid, 'main_menu_points', points=u.get('points', 0))
                Utilities.edit_message(call, uid, Utilities.format_border(uid, 'main_menu_title', text), build_main_keyboard(uid))
            else:
                bot.answer_callback_query(call.id, Utilities.get_text(uid, 'not_subscribed'), show_alert=True)
            return
        if not Utilities.check_subscription(uid) and not Utilities.is_admin(uid):
            bot.answer_callback_query(call.id, Utilities.get_text(uid, 'subscribe_first'), show_alert=True)
            return
        Utilities.clear_cancel(uid)

        if data == "set_lang_en":
            Utilities.set_user_lang(uid, 'en')
            bot.answer_callback_query(call.id, Utilities.get_text(uid, 'lang_updated'))
            u = users.get(str(uid), {})
            vip = Utilities.is_user_pro(uid)
            rank = 'VIP' if vip else 'Free'
            text = Utilities.get_text(uid, 'welcome', name=escape(call.from_user.first_name), rank=rank, points=u.get('points', 0), date=u.get('join_date', 'today'))
            Utilities.edit_message(call, uid, Utilities.format_border(uid, 'main_menu_title', text), build_main_keyboard(uid))
            return
        if data == "set_lang_ar":
            Utilities.set_user_lang(uid, 'ar')
            bot.answer_callback_query(call.id, Utilities.get_text(uid, 'lang_updated'))
            u = users.get(str(uid), {})
            vip = Utilities.is_user_pro(uid)
            rank = 'VIP' if vip else 'مجاني'
            text = Utilities.get_text(uid, 'welcome', name=escape(call.from_user.first_name), rank=rank, points=u.get('points', 0), date=u.get('join_date', 'today'))
            Utilities.edit_message(call, uid, Utilities.format_border(uid, 'main_menu_title', text), build_main_keyboard(uid))
            return
        if data.startswith("set_style_"):
            style = data.split("_")[2]
            Utilities.set_user_style(uid, style)
            bot.answer_callback_query(call.id, Utilities.get_text(uid, 'style_updated'))
            settings_panel(call, uid)
            return

        if data == "nav_main":
            u = users.get(str(uid), {})
            vip = Utilities.is_user_pro(uid)
            rank = 'VIP' if vip else 'Free'
            text = Utilities.get_text(uid, 'main_menu_rank', rank=rank) + '\n' + Utilities.get_text(uid, 'main_menu_points', points=u.get('points', 0))
            Utilities.edit_message(call, uid, Utilities.format_border(uid, 'main_menu_title', text), build_main_keyboard(uid))
        elif data == "nav_settings":
            settings_panel(call, uid)
        elif data == "nav_change_lang":
            Utilities.edit_message(call, uid, Utilities.format_border(uid, 'language_selection', 'choose_lang'), build_language_keyboard(uid))
        elif data == "nav_change_style":
            Utilities.edit_message(call, uid, Utilities.format_border(uid, 'change_style', 'Choose a button color:'), build_style_keyboard(uid))
        elif data == "nav_pro":
            if not Utilities.is_user_pro(uid):
                bot.answer_callback_query(call.id, Utilities.get_text(uid, 'vip_only'), show_alert=True)
                return
            Utilities.edit_message(call, uid, Utilities.format_border(uid, 'pro_panel', 'Pro Panel - exclusive features for VIP subscribers.'), build_pro_keyboard(uid))
        elif data == "pro_download_all":
            if not Utilities.is_user_pro(uid):
                bot.answer_callback_query(call.id, Utilities.get_text(uid, 'vip_only'), show_alert=True)
                return
            files = DatabaseManager.get_files()
            u_files = {fid: f for fid, f in files.items() if f.get('user_id') == uid and f.get('status') == 'active'}
            if not u_files:
                bot.answer_callback_query(call.id, Utilities.get_text(uid, 'no_files'), show_alert=True)
                return
            decrypted_files = []
            for fid in u_files.keys():
                if Utilities.verify_file_access(fid, uid):
                    content = EncryptionManager.load_encrypted_file(fid)
                    if content:
                        temp_path = os.path.join(TEMP_DIR, f"temp_{fid}_{Utilities.gen_id(4)}.py")
                        with open(temp_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        decrypted_files.append(temp_path)
            if decrypted_files:
                zip_name = f"files_{uid}_{Utilities.gen_id(4)}.zip"
                zip_path = Utilities.create_zip(decrypted_files, zip_name)
                try:
                    with open(zip_path, 'rb') as f:
                        bot.send_document(cid, f, caption="Your files archive")
                    for temp_file in decrypted_files:
                        try:
                            os.remove(temp_file)
                        except:
                            pass
                    os.remove(zip_path)
                except:
                    bot.answer_callback_query(call.id, Utilities.get_text(uid, 'download_failed'), show_alert=True)
            else:
                bot.answer_callback_query(call.id, Utilities.get_text(uid, 'no_files_to_download'), show_alert=True)
        elif data == "pro_auto_fix":
            if not Utilities.is_user_pro(uid):
                bot.answer_callback_query(call.id, Utilities.get_text(uid, 'vip_only'), show_alert=True)
                return
            m = bot.send_message(cid, Utilities.format_border(uid, 'auto_fix', 'Send a .py file to analyze and fix:'), reply_markup=build_cancel_keyboard(uid))
            Utilities.save_message(cid, m.message_id)
            bot.register_next_step_handler(m, auto_fix_step, m.message_id, uid)
        elif data == "pro_test_run":
            if not Utilities.is_user_pro(uid):
                bot.answer_callback_query(call.id, Utilities.get_text(uid, 'vip_only'), show_alert=True)
                return
            files = DatabaseManager.get_files()
            u_files = {fid: f for fid, f in files.items() if f.get('user_id') == uid and f.get('status') == 'active'}
            if not u_files:
                bot.answer_callback_query(call.id, Utilities.get_text(uid, 'no_files'), show_alert=True)
                return
            kb = types.InlineKeyboardMarkup(row_width=1)
            for fid, f in u_files.items():
                kb.add(Utilities.create_button(f"{f.get('file_name', '?')[:25]}", f"testrun_{fid}", uid))
            kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), "nav_pro", uid))
            Utilities.edit_message(call, uid, Utilities.format_border(uid, 'test_run', Utilities.get_text(uid, 'test_run_select')), kb)
        elif data.startswith("testrun_"):
            fid = data.split("_")[1]
            if not Utilities.verify_file_access(fid, uid):
                bot.answer_callback_query(call.id, Utilities.get_text(uid, 'access_denied'), show_alert=True)
                return
            content = EncryptionManager.load_encrypted_file(fid)
            if not content:
                bot.answer_callback_query(call.id, Utilities.get_text(uid, 'file_not_found'), show_alert=True)
                return
            try:
                exec(compile(content, f"test_{fid}", 'exec'), {})
                bot.answer_callback_query(call.id, Utilities.get_text(uid, 'test_run_success'))
            except Exception as e:
                bot.answer_callback_query(call.id, Utilities.get_text(uid, 'test_run_error', error=str(e)[:100]), show_alert=True)
        elif data == "pro_sell":
            if not Utilities.is_user_pro(uid):
                bot.answer_callback_query(call.id, Utilities.get_text(uid, 'vip_only'), show_alert=True)
                return
            m = bot.send_message(cid, Utilities.format_border(uid, 'sell_store', Utilities.get_text(uid, 'send_file')), reply_markup=build_cancel_keyboard(uid))
            Utilities.save_message(cid, m.message_id)
            bot.register_next_step_handler(m, sell_file_step, m.message_id, uid)
        elif data == "nav_wallet":
            u = users.get(str(uid), {})
            vip = Utilities.is_user_pro(uid)
            exp = "None"
            if vip:
                e = u.get('expiry')
                if e == 'LIFETIME' or e == 0:
                    exp = "Lifetime"
                elif e:
                    exp = e
            today = str(datetime.now().date())
            can_claim = u.get('last_daily') != today
            text = (Utilities.get_text(uid, 'balance', balance=u.get('points', 0)) + '\n' +
                    Utilities.get_text(uid, 'rank', rank='VIP' if vip else 'Free') + '\n' +
                    Utilities.get_text(uid, 'vip_expiry', expiry=exp) + '\n\n' +
                    Utilities.get_text(uid, 'points_info'))
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                Utilities.create_button(Utilities.get_text(uid, 'daily_bonus') + (' ✅' if can_claim else ' ❌'), "daily", uid),
                Utilities.create_button(Utilities.get_text(uid, 'referral_link'), "ref", uid)
            )
            kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), "nav_main", uid))
            Utilities.edit_message(call, uid, Utilities.format_border(uid, 'wallet_title', text), kb)
        elif data == "daily":
            u = users.get(str(uid))
            today = str(datetime.now().date())
            if u.get('last_daily') == today:
                return bot.answer_callback_query(call.id, Utilities.get_text(uid, 'daily_claimed'), show_alert=True)
            gift = random.randint(5, 15)
            u['points'] = u.get('points', 0) + gift
            u['last_daily'] = today
            users[str(uid)] = u
            DatabaseManager.save_users(users)
            bot.answer_callback_query(call.id, Utilities.get_text(uid, 'daily_earned', points=gift), show_alert=True)
            vip = Utilities.is_user_pro(uid)
            text = (Utilities.get_text(uid, 'balance', balance=u.get('points', 0)) + '\n' +
                    Utilities.get_text(uid, 'rank', rank='VIP' if vip else 'Free') + '\n' +
                    Utilities.get_text(uid, 'daily_earned', points=gift))
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                Utilities.create_button(Utilities.get_text(uid, 'daily_bonus') + ' ❌', "daily", uid),
                Utilities.create_button(Utilities.get_text(uid, 'referral_link'), "ref", uid)
            )
            kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), "nav_main", uid))
            Utilities.edit_message(call, uid, Utilities.format_border(uid, 'wallet_title', text), kb)
        elif data == "ref":
            info = bot.get_me()
            link = f"https://t.me/{info.username}?start={uid}"
            text = Utilities.get_text(uid, 'referral_text', link=link)
            kb = types.InlineKeyboardMarkup()
            kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), "nav_wallet", uid))
            Utilities.edit_message(call, uid, Utilities.format_border(uid, 'referral_link', text), kb)
        elif data == "nav_help":
            text = Utilities.get_text(uid, 'help_text')
            kb = types.InlineKeyboardMarkup()
            kb.add(Utilities.create_button(Utilities.get_text(uid, 'contact_dev'), None, uid, url=f"tg://user?id={ADMIN_ID}"))
            kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), "nav_main", uid))
            Utilities.edit_message(call, uid, Utilities.format_border(uid, 'help_title', text), kb)
        elif data == "nav_upload":
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                Utilities.create_button(Utilities.get_text(uid, 'free_host'), "up_free", uid),
                Utilities.create_button(Utilities.get_text(uid, 'vip_host'), "up_pro", uid)
            )
            kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), "nav_main", uid))
            Utilities.edit_message(call, uid, Utilities.format_border(uid, 'upload', Utilities.get_text(uid, 'upload_choice')), kb)
        elif data.startswith("up_"):
            h_type = data.split("_")[1]
            if h_type == "pro" and not Utilities.is_user_pro(uid):
                bot.answer_callback_query(call.id, Utilities.get_text(uid, 'vip_only'), show_alert=True)
                return
            if h_type == "free":
                u = users.get(str(uid), {})
                if u.get('points', 0) < 1:
                    bot.answer_callback_query(call.id, Utilities.get_text(uid, 'insufficient_points_short'), show_alert=True)
                    return
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, Utilities.format_border(uid, 'upload', Utilities.get_text(uid, 'send_file')), reply_markup=build_cancel_keyboard(uid))
            Utilities.save_message(cid, m.message_id)
            bot.register_next_step_handler(m, upload_step, h_type, m.message_id, uid)
        elif data == "nav_files":
            files = DatabaseManager.get_files()
            u_files = {fid: f for fid, f in files.items() if f.get('user_id') == uid and f.get('status') == 'active'}
            if not u_files:
                bot.answer_callback_query(call.id, Utilities.get_text(uid, 'no_files'), show_alert=True)
                return
            kb = types.InlineKeyboardMarkup(row_width=1)
            for fid, f in u_files.items():
                running = fid in active_processes and active_processes[fid].poll() is None
                icon = "🟢" if running else "🔴"
                ft = "VIP" if f.get('type') == 'pro' else "Free"
                kb.add(Utilities.create_button(f"{icon} {ft} {f.get('file_name', '?')[:25]}", f"manage_{fid}", uid))
            if Utilities.is_user_pro(uid):
                kb.add(Utilities.create_button(Utilities.get_text(uid, 'download_all'), "pro_download_all", uid))
            kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), "nav_main", uid))
            running_count = sum(1 for fid in u_files if fid in active_processes and active_processes[fid].poll() is None)
            text = (Utilities.get_text(uid, 'files_count', count=len(u_files)) + '\n' +
                    Utilities.get_text(uid, 'running_count', count=running_count) + '\n' +
                    Utilities.get_text(uid, 'stopped_count', count=len(u_files) - running_count))
            Utilities.edit_message(call, uid, Utilities.format_border(uid, 'my_files_title', text), kb)
        elif data.startswith("manage_"):
            file_panel(call, data.split("_")[1], uid)
        elif data.startswith("toggle_"):
            toggle_file(call, data.split("_")[1], uid)
        elif data.startswith("delc_"):
            fid = data.split("_")[1]
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                Utilities.create_button(Utilities.get_text(uid, 'yes'), f"del_{fid}", uid),
                Utilities.create_button(Utilities.get_text(uid, 'no'), f"manage_{fid}", uid)
            )
            Utilities.edit_message(call, uid, Utilities.format_border(uid, 'delete', Utilities.get_text(uid, 'confirm_delete')), kb)
        elif data.startswith("del_"):
            delete_file(call, data.split("_")[1], uid)
        elif data.startswith("dl_"):
            download_file(call, data.split("_")[1], uid)
        elif data.startswith("term_"):
            terminal(call, data.split("_")[1], uid)
        elif data.startswith("rterm_"):
            terminal(call, data.split("_")[1], uid)
        elif data.startswith("inp_"):
            fid = data.split("_")[1]
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, Utilities.format_border(uid, 'input', Utilities.get_text(uid, 'input') + ':'), reply_markup=build_cancel_keyboard(uid))
            Utilities.save_message(cid, m.message_id)
            bot.register_next_step_handler(m, input_step, fid, m.message_id, uid)
        elif data.startswith("chtoken_"):
            fid = data.split("_")[1]
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, Utilities.format_border(uid, 'change_token', Utilities.get_text(uid, 'send_token')), reply_markup=build_cancel_keyboard(uid))
            Utilities.save_message(cid, m.message_id)
            bot.register_next_step_handler(m, token_step, fid, m.message_id, uid)
        elif data.startswith("tokinfo_"):
            token_info(call, data.split("_")[1], uid)
        elif data == "nav_store":
            store_view(call, uid)
        elif data.startswith("buy_"):
            buy_confirm(call, data.split("_")[1], uid)
        elif data.startswith("ebuy_"):
            buy_execute(call, data.split("_")[1], uid)
        elif data == "nav_lib":
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, Utilities.format_border(uid, 'install_library', Utilities.get_text(uid, 'enter_library_name')), reply_markup=build_cancel_keyboard(uid))
            Utilities.save_message(cid, m.message_id)
            bot.register_next_step_handler(m, library_step, m.message_id, uid)
        elif data == "nav_stats":
            files = DatabaseManager.get_files()
            u = users.get(str(uid), {})
            u_files = [f for f in files.values() if f.get('user_id') == uid and f.get('status') == 'active']
            running = sum(1 for fid, f in files.items() if f.get('user_id') == uid and fid in active_processes and active_processes[fid].poll() is None)
            vip = Utilities.is_user_pro(uid)
            exp = "None"
            if vip:
                e = u.get('expiry')
                if e == 'LIFETIME' or e == 0:
                    exp = "Lifetime"
                elif e:
                    try:
                        ed = datetime.strptime(e, "%Y-%m-%d %H:%M:%S")
                        rem = ed - datetime.now()
                        exp = f"{rem.days} days"
                    except:
                        exp = e
            text = (Utilities.get_text(uid, 'user_id', id=uid) + '\n' +
                    Utilities.get_text(uid, 'user_username', username=u.get('username', 'None')) + '\n' +
                    Utilities.get_text(uid, 'user_joined', date=u.get('join_date', '?')) + '\n\n' +
                    Utilities.get_text(uid, 'rank', rank='VIP' if vip else 'Free') + '\n' +
                    Utilities.get_text(uid, 'vip_expiry', expiry=exp) + '\n' +
                    Utilities.get_text(uid, 'balance', balance=u.get('points', 0)) + '\n\n' +
                    Utilities.get_text(uid, 'files_count', count=len(u_files)) + '\n' +
                    Utilities.get_text(uid, 'running_count', count=running))
            kb = types.InlineKeyboardMarkup()
            kb.add(Utilities.create_button(Utilities.get_text(uid, 'wallet'), "nav_wallet", uid))
            kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), "nav_main", uid))
            Utilities.edit_message(call, uid, Utilities.format_border(uid, 'profile', text), kb)
        elif data == "nav_admin" and Utilities.is_admin(uid):
            admin_panel(call, uid)
        elif data == "lock_bot" and Utilities.is_admin(uid):
            new_state = not settings.get('bot_locked', False)
            settings['bot_locked'] = new_state
            DatabaseManager.save_settings(settings)
            st = Utilities.get_text(uid, 'locked') if new_state else Utilities.get_text(uid, 'unlocked')
            bot.answer_callback_query(call.id, f"Bot {st}")
            admin_panel(call, uid)
        elif data == "adm_users" and Utilities.is_admin(uid):
            users_panel(call, uid)
        elif data.startswith("userpage_"):
            page = int(data.split("_")[1])
            users_panel(call, uid, page)
        elif data.startswith("uctrl_") and Utilities.is_admin(uid):
            user_panel(call, data.split("_")[1], uid)
        elif data.startswith("ban_") and Utilities.is_admin(uid):
            ban_toggle(call, data.split("_")[1], uid)
        elif data.startswith("pro_") and Utilities.is_admin(uid):
            tuid = data.split("_")[1]
            if Utilities.is_user_pro(int(tuid)):
                pro_remove(call, tuid, uid)
            else:
                try:
                    bot.delete_message(cid, call.message.message_id)
                except:
                    pass
                m = bot.send_message(cid, Utilities.format_border(uid, 'grant_vip', Utilities.get_text(uid, 'grant_vip_prompt')), reply_markup=build_cancel_keyboard(uid, "cancel_admin"))
                Utilities.save_message(cid, m.message_id)
                bot.register_next_step_handler(m, pro_grant_step, tuid, m.message_id, uid)
        elif data.startswith("charge_") and Utilities.is_admin(uid):
            tuid = data.split("_")[1]
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, Utilities.format_border(uid, 'charge', Utilities.get_text(uid, 'charge_points')), reply_markup=build_cancel_keyboard(uid, "cancel_admin"))
            Utilities.save_message(cid, m.message_id)
            bot.register_next_step_handler(m, charge_step, tuid, m.message_id, uid)
        elif data.startswith("msguser_") and Utilities.is_admin(uid):
            tuid = data.split("_")[1]
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, Utilities.format_border(uid, 'message_user', Utilities.get_text(uid, 'enter_message')), reply_markup=build_cancel_keyboard(uid, "cancel_admin"))
            Utilities.save_message(cid, m.message_id)
            bot.register_next_step_handler(m, message_user_step, tuid, m.message_id, uid)
        elif data == "adm_admins" and Utilities.is_admin(uid):
            admins_panel(call, uid)
        elif data == "add_admin" and Utilities.is_main_admin(uid):
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, Utilities.format_border(uid, 'add_admin', Utilities.get_text(uid, 'add_admin_prompt')), reply_markup=build_cancel_keyboard(uid, "cancel_admin"))
            Utilities.save_message(cid, m.message_id)
            bot.register_next_step_handler(m, add_admin_step, m.message_id, uid)
        elif data == "add_admin" and not Utilities.is_main_admin(uid):
            bot.answer_callback_query(call.id, Utilities.get_text(uid, 'only_owner'), show_alert=True)
        elif data.startswith("rmadmin_") and Utilities.is_admin(uid):
            aid = int(data.split("_")[1])
            if aid == ADMIN_ID:
                bot.answer_callback_query(call.id, Utilities.get_text(uid, 'cannot_remove_owner'), show_alert=True)
            elif not Utilities.is_main_admin(uid) and aid != uid:
                bot.answer_callback_query(call.id, Utilities.get_text(uid, 'only_owner'), show_alert=True)
            elif Utilities.remove_admin(aid):
                bot.answer_callback_query(call.id, Utilities.get_text(uid, 'admin_removed'))
                admins_panel(call, uid)
            else:
                bot.answer_callback_query(call.id, Utilities.get_text(uid, 'failed'), show_alert=True)
        elif data == "adm_store" and Utilities.is_admin(uid):
            store_panel(call, uid)
        elif data == "add_store" and Utilities.is_admin(uid):
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, Utilities.format_border(uid, 'add_store_file', Utilities.get_text(uid, 'send_file')), reply_markup=build_cancel_keyboard(uid, "cancel_admin"))
            Utilities.save_message(cid, m.message_id)
            bot.register_next_step_handler(m, store_add_step, m.message_id, uid)
        elif data.startswith("estore_"):
            store_edit(call, data.split("_")[1], uid)
        elif data.startswith("sprice_"):
            sid = data.split("_")[1]
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, Utilities.format_border(uid, 'set_price', Utilities.get_text(uid, 'price_prompt')), reply_markup=build_cancel_keyboard(uid, "cancel_admin"))
            Utilities.save_message(cid, m.message_id)
            bot.register_next_step_handler(m, store_price_step, sid, m.message_id, uid)
        elif data.startswith("delstore_"):
            store_delete(call, data.split("_")[1], uid)
        elif data == "adm_pending" and Utilities.is_admin(uid):
            pending_list(call, uid)
        elif data.startswith("vpend_") and Utilities.is_admin(uid):
            pending_view(call, data.split("_")[1], uid)
        elif data.startswith("approve_") and Utilities.is_admin(uid):
            approve_file(call, data.split("_")[1], uid)
        elif data.startswith("reject_") and Utilities.is_admin(uid):
            reject_file(call, data.split("_")[1], uid)
        elif data == "adm_broadcast" and Utilities.is_admin(uid):
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, Utilities.format_border(uid, 'broadcast', Utilities.get_text(uid, 'enter_message')), reply_markup=build_cancel_keyboard(uid, "cancel_admin"))
            Utilities.save_message(cid, m.message_id)
            bot.register_next_step_handler(m, broadcast_step, m.message_id, uid)
        elif data == "adm_settings" and Utilities.is_admin(uid):
            settings_panel(call, uid)
        elif data == "adm_channels" and Utilities.is_admin(uid):
            channels_panel(call, uid)
        elif data == "add_channel" and Utilities.is_admin(uid):
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, Utilities.format_border(uid, 'add_channel', Utilities.get_text(uid, 'add_channel_prompt')), reply_markup=build_cancel_keyboard(uid, "cancel_admin"))
            Utilities.save_message(cid, m.message_id)
            bot.register_next_step_handler(m, add_channel_step, m.message_id, uid)
        elif data.startswith("delch_") and Utilities.is_admin(uid):
            del_channel(call, int(data.split("_")[1]), uid)
        elif data == "set_img" and Utilities.is_admin(uid):
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, Utilities.format_border(uid, 'add_image', Utilities.get_text(uid, 'send_image')), reply_markup=build_cancel_keyboard(uid, "cancel_admin"))
            Utilities.save_message(cid, m.message_id)
            bot.register_next_step_handler(m, set_image_step, m.message_id, uid)
        elif data == "rm_img" and Utilities.is_admin(uid):
            settings['bot_image'] = None
            DatabaseManager.save_settings(settings)
            bot.answer_callback_query(call.id, Utilities.get_text(uid, 'image_removed'))
            settings_panel(call, uid)
        elif data == "set_thumb" and Utilities.is_admin(uid):
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, Utilities.format_border(uid, 'add_thumb', Utilities.get_text(uid, 'send_image')), reply_markup=build_cancel_keyboard(uid, "cancel_admin"))
            Utilities.save_message(cid, m.message_id)
            bot.register_next_step_handler(m, set_thumb_step, m.message_id, uid)
        elif data == "rm_thumb" and Utilities.is_admin(uid):
            if settings.get('file_thumb') and os.path.exists(settings.get('file_thumb', '')):
                try:
                    os.remove(settings['file_thumb'])
                except:
                    pass
            settings['file_thumb'] = None
            DatabaseManager.save_settings(settings)
            bot.answer_callback_query(call.id, Utilities.get_text(uid, 'thumb_removed'))
            settings_panel(call, uid)
        elif data == "set_name" and Utilities.is_admin(uid):
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, Utilities.format_border(uid, 'change_name', Utilities.get_text(uid, 'enter_name')), reply_markup=build_cancel_keyboard(uid, "cancel_admin"))
            Utilities.save_message(cid, m.message_id)
            bot.register_next_step_handler(m, set_name_step, m.message_id, uid)
        elif data == "stop_all" and Utilities.is_admin(uid):
            ProcessManager.stop_all()
            bot.answer_callback_query(call.id, Utilities.get_text(uid, 'all_stopped'))
            admin_panel(call, uid)
        elif data == "toggle_auto" and Utilities.is_admin(uid):
            new_state = not settings.get('auto_approve', True)
            settings['auto_approve'] = new_state
            DatabaseManager.save_settings(settings)
            st = Utilities.get_text(uid, 'enabled') if new_state else Utilities.get_text(uid, 'disabled')
            bot.answer_callback_query(call.id, f"Auto-approve {st}")
            settings_panel(call, uid)
        elif data == "adm_files" and Utilities.is_admin(uid):
            all_files_panel(call, uid)
        elif data.startswith("afpage_"):
            page = int(data.split("_")[1])
            all_files_panel(call, uid, page)
        elif data.startswith("afile_"):
            fid = data.split("_")[1]
            file_panel_admin(call, fid, uid)
        elif data == "download_all_files" and Utilities.is_admin(uid):
            all_files = DatabaseManager.get_files()
            decrypted_files = []
            for fid in all_files.keys():
                if Utilities.verify_file_access(fid, ADMIN_ID):
                    content = EncryptionManager.load_encrypted_file(fid)
                    if content:
                        temp_path = os.path.join(TEMP_DIR, f"temp_{fid}_{Utilities.gen_id(4)}.py")
                        with open(temp_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        decrypted_files.append(temp_path)
            if decrypted_files:
                zip_name = f"all_files_{Utilities.gen_id(4)}.zip"
                zip_path = Utilities.create_zip(decrypted_files, zip_name)
                try:
                    with open(zip_path, 'rb') as f:
                        bot.send_document(cid, f, caption="All bot files")
                    for temp_file in decrypted_files:
                        try:
                            os.remove(temp_file)
                        except:
                            pass
                    os.remove(zip_path)
                except:
                    bot.answer_callback_query(call.id, Utilities.get_text(uid, 'download_failed'), show_alert=True)
            else:
                bot.answer_callback_query(call.id, Utilities.get_text(uid, 'no_files_to_download'), show_alert=True)
    except Exception as e:
        print(f"Callback error: {e}")

def settings_panel(call, uid):
    settings = DatabaseManager.get_settings()
    has_img = "✅" if settings.get('bot_image') else "❌"
    has_thumb = "✅" if settings.get('file_thumb') and os.path.exists(settings.get('file_thumb', '')) else "❌"
    auto_approve = "✅" if settings.get('auto_approve', True) else "❌"
    text = (Utilities.get_text(uid, 'bot_name', name=settings.get('bot_name', 'Not set')) + '\n' +
            Utilities.get_text(uid, 'bot_image', state=has_img) + '\n' +
            Utilities.get_text(uid, 'file_thumb', state=has_thumb) + '\n' +
            Utilities.get_text(uid, 'auto_approve', state=auto_approve))
    Utilities.edit_message(call, uid, Utilities.format_border(uid, 'settings_title', text), build_settings_keyboard(uid))

def auto_fix_step(msg, prompt_id, uid):
    if Utilities.is_cancelled(uid):
        Utilities.clear_cancel(uid)
        return
    Utilities.delete_messages(msg.chat.id, prompt_id, msg.message_id)
    if not msg.document or not msg.document.file_name.endswith('.py'):
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'error', Utilities.get_text(uid, 'invalid_file')), build_back_keyboard(uid, "nav_pro"))
        return
    try:
        finfo = bot.get_file(msg.document.file_id)
        file_content = bot.download_file(finfo.file_path).decode('utf-8')
        fixed_content = Utilities.auto_fix_code(file_content)
        fixed_name = f"fixed_{msg.document.file_name}"
        temp_path = os.path.join(TEMP_DIR, fixed_name)
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        with open(temp_path, 'rb') as f:
            bot.send_document(msg.chat.id, f, caption="Fixed file")
        os.remove(temp_path)
    except Exception as e:
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'error', f"Fix failed: {str(e)[:200]}"), build_back_keyboard(uid, "nav_pro"))

def sell_file_step(msg, prompt_id, uid):
    if Utilities.is_cancelled(uid):
        Utilities.clear_cancel(uid)
        return
    Utilities.delete_messages(msg.chat.id, prompt_id, msg.message_id)
    if not msg.document or not msg.document.file_name.endswith('.py'):
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'error', Utilities.get_text(uid, 'invalid_file')), build_back_keyboard(uid, "nav_pro"))
        return
    m = bot.send_message(msg.chat.id, Utilities.format_border(uid, 'set_price', Utilities.get_text(uid, 'price_prompt')), reply_markup=build_cancel_keyboard(uid))
    Utilities.save_message(msg.chat.id, m.message_id)
    bot.register_next_step_handler(m, sell_price_step, msg.document, m.message_id, uid)

def sell_price_step(msg, doc, prompt_id, uid):
    if Utilities.is_cancelled(uid):
        Utilities.clear_cancel(uid)
        return
    Utilities.delete_messages(msg.chat.id, prompt_id, msg.message_id)
    if not msg.text or not msg.text.strip().isdigit():
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'error', Utilities.get_text(uid, 'invalid_price')), build_back_keyboard(uid, "nav_pro"))
        return
    price = int(msg.text.strip())
    market = DatabaseManager.get_market()
    sid = Utilities.gen_id()
    market[sid] = {
        'name': doc.file_name,
        'price': price,
        'seller_id': uid,
        'seller_name': f"{msg.from_user.first_name} {msg.from_user.last_name or ''}",
        'rating': 0,
        'votes': 0,
        'downloads': 0,
        'category': 'General',
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    DatabaseManager.save_market(market)
    finfo = bot.get_file(doc.file_id)
    with open(os.path.join(MARKET_DIR, f"{sid}.py"), 'wb') as f:
        f.write(bot.download_file(finfo.file_path))
    Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'success', f"File listed for sale!\n{doc.file_name}\nPrice: {price} points"), build_back_keyboard(uid, "nav_pro"))

def store_view(call, uid):
    store = DatabaseManager.get_store()
    if not store:
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'store_empty'), show_alert=True)
        return
    kb = types.InlineKeyboardMarkup(row_width=2)
    for sid, item in store.items():
        kb.add(Utilities.create_button(f"{item['name'][:15]} • {item['price']}pt", f"buy_{sid}", uid))
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), "nav_main", uid))
    users = DatabaseManager.get_users()
    text = Utilities.get_text(uid, 'store') + '\n\n' + Utilities.get_text(uid, 'balance', balance=users.get(str(uid), {}).get('points', 0))
    Utilities.edit_message(call, uid, Utilities.format_border(uid, 'store', text), kb)

def buy_confirm(call, sid, uid):
    store = DatabaseManager.get_store()
    item = store.get(sid)
    if not item:
        return
    users = DatabaseManager.get_users()
    pts = users.get(str(uid), {}).get('points', 0)
    status = Utilities.get_text(uid, 'sufficient') if pts >= item['price'] else Utilities.get_text(uid, 'insufficient')
    text = Utilities.get_text(uid, 'buy_confirm_text', name=item['name'], price=item['price'], balance=pts, status=status)
    kb = types.InlineKeyboardMarkup(row_width=2)
    if pts >= item['price']:
        kb.add(
            Utilities.create_button(Utilities.get_text(uid, 'buy'), f"ebuy_{sid}", uid),
            Utilities.create_button(Utilities.get_text(uid, 'cancel'), "nav_store", uid)
        )
    else:
        kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), "nav_store", uid))
    Utilities.edit_message(call, uid, Utilities.format_border(uid, 'buy', text), kb)

def buy_execute(call, sid, uid):
    users = DatabaseManager.get_users()
    store = DatabaseManager.get_store()
    item = store.get(sid)
    if not item:
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'file_not_found'), show_alert=True)
        return
    if users.get(str(uid), {}).get('points', 0) < item['price']:
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'insufficient_points_short'), show_alert=True)
        return
    users[str(uid)]['points'] -= item['price']
    DatabaseManager.save_users(users)
    path = os.path.join(STORE_DIR, f"{sid}.py")
    try:
        thumb = Utilities.get_thumb()
        with open(path, 'rb') as f:
            if thumb:
                with open(thumb, 'rb') as t:
                    bot.send_document(uid, f, thumb=t, caption=f"Purchased: {item['name']}", parse_mode="HTML")
            else:
                bot.send_document(uid, f, caption=f"Purchased: {item['name']}", parse_mode="HTML")
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'purchase_success'))
        store_view(call, uid)
    except:
        users[str(uid)]['points'] += item['price']
        DatabaseManager.save_users(users)
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'purchase_failed'), show_alert=True)

def admin_panel(call, uid):
    users = DatabaseManager.get_users()
    files = DatabaseManager.get_files()
    pending = [f for f in files.values() if f.get('status') == 'pending']
    active = sum(1 for fid in active_processes if active_processes[fid].poll() is None)
    settings = DatabaseManager.get_settings()
    locked = settings.get('bot_locked', False)
    auto_approve = settings.get('auto_approve', True)
    state = Utilities.get_text(uid, 'locked') if locked else Utilities.get_text(uid, 'unlocked')
    auto = Utilities.get_text(uid, 'enabled') if auto_approve else Utilities.get_text(uid, 'disabled')
    text = Utilities.get_text(uid, 'admin_stats', users=len(users), files=len(files), pending=len(pending), active=active,
                           admins=len(DatabaseManager.get_admins()), state=state, auto=auto)
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'unlock') if locked else Utilities.get_text(uid, 'lock'), "lock_bot", uid))
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'auto_approve_toggle') if auto_approve else Utilities.get_text(uid, 'manual_approve'), "toggle_auto", uid))
    kb.row(
        Utilities.create_button(Utilities.get_text(uid, 'users_list'), "adm_users", uid),
        Utilities.create_button(Utilities.get_text(uid, 'admins_list'), "adm_admins", uid)
    )
    kb.row(
        Utilities.create_button(Utilities.get_text(uid, 'store_management'), "adm_store", uid),
        Utilities.create_button(Utilities.get_text(uid, 'pending_files') + f" ({len(pending)})", "adm_pending", uid)
    )
    kb.row(
        Utilities.create_button(Utilities.get_text(uid, 'broadcast'), "adm_broadcast", uid),
        Utilities.create_button(Utilities.get_text(uid, 'channels'), "adm_channels", uid)
    )
    kb.row(
        Utilities.create_button(Utilities.get_text(uid, 'all_files'), "adm_files", uid),
        Utilities.create_button(Utilities.get_text(uid, 'stop_all'), "stop_all", uid)
    )
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'settings'), "adm_settings", uid))
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), "nav_main", uid))
    Utilities.edit_message(call, uid, Utilities.format_border(uid, 'admin_panel_title', text), kb)

def users_panel(call, uid, page=0):
    users = DatabaseManager.get_users()
    user_ids = list(users.keys())
    items_per_page = 10
    total_pages = (len(user_ids) + items_per_page - 1) // items_per_page
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_users = user_ids[start_idx:end_idx]
    kb = types.InlineKeyboardMarkup(row_width=2)
    for uid_iter in page_users:
        u = users[uid_iter]
        name = u.get('first_name', 'Unknown')
        kb.add(Utilities.create_button(f"{name[:10]}", f"uctrl_{uid_iter}", uid))
    nav_buttons = []
    if page > 0:
        nav_buttons.append(Utilities.create_button(Utilities.get_text(uid, 'previous'), f"userpage_{page-1}", uid))
    if page < total_pages - 1:
        nav_buttons.append(Utilities.create_button(Utilities.get_text(uid, 'next'), f"userpage_{page+1}", uid))
    if nav_buttons:
        kb.row(*nav_buttons)
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), "nav_admin", uid))
    text = f"Page {page+1} of {total_pages}\nTotal users: {len(users)}"
    Utilities.edit_message(call, uid, Utilities.format_border(uid, 'users_list', text), kb)

def all_files_panel(call, uid, page=0):
    files = DatabaseManager.get_files()
    file_ids = list(files.keys())
    items_per_page = 10
    total_pages = (len(file_ids) + items_per_page - 1) // items_per_page
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_files = file_ids[start_idx:end_idx]
    kb = types.InlineKeyboardMarkup(row_width=2)
    for fid in page_files:
        f = files[fid]
        kb.add(Utilities.create_button(f"{f.get('file_name', '?')[:15]}", f"afile_{fid}", uid))
    nav_buttons = []
    if page > 0:
        nav_buttons.append(Utilities.create_button(Utilities.get_text(uid, 'previous'), f"afpage_{page-1}", uid))
    if page < total_pages - 1:
        nav_buttons.append(Utilities.create_button(Utilities.get_text(uid, 'next'), f"afpage_{page+1}", uid))
    if nav_buttons:
        kb.row(*nav_buttons)
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'download_all'), "download_all_files", uid))
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), "nav_admin", uid))
    text = f"Page {page+1} of {total_pages}\nTotal files: {len(files)}"
    Utilities.edit_message(call, uid, Utilities.format_border(uid, 'all_files', text), kb)

def file_panel_admin(call, fid, uid):
    files = DatabaseManager.get_files()
    if fid not in files:
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'file_not_found'))
        return
    f = files[fid]
    content = EncryptionManager.load_encrypted_file(fid)
    preview = "Access denied"
    if content:
        safe = escape(content[:1000])
        if len(safe) > 3000:
            safe = safe[:3000] + "\n..."
        preview = f"<pre><code class='language-python'>{safe}</code></pre>"
    running = fid in active_processes and active_processes[fid].poll() is None
    text = (Utilities.get_text(uid, 'file', name=f.get('file_name')) + '\n' +
            Utilities.get_text(uid, 'user_id', id=f.get('user_id')) + '\n' +
            Utilities.get_text(uid, 'file_type', type='VIP' if f.get('type') == 'pro' else 'Free') + '\n' +
            Utilities.get_text(uid, 'file_status', status=Utilities.get_text(uid, 'running') if running else Utilities.get_text(uid, 'stopped')) + '\n' +
            Utilities.get_text(uid, 'file_created', created=f.get('created_at')) + '\n\nPreview:\n' + preview)
    kb = types.InlineKeyboardMarkup()
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), "afpage_0", uid))
    Utilities.edit_message(call, uid, Utilities.format_border(uid, 'file', text), kb)

def admins_panel(call, uid):
    admins = DatabaseManager.get_admins()
    text = Utilities.get_text(uid, 'admins_list') + f" ({len(admins)}):\n\n"
    kb = types.InlineKeyboardMarkup(row_width=1)
    if Utilities.is_main_admin(uid):
        kb.add(Utilities.create_button(Utilities.get_text(uid, 'add_admin'), "add_admin", uid))
    for aid in admins:
        try:
            user = bot.get_chat(aid)
            name = user.first_name
            owner = "👑" if aid == ADMIN_ID else "👮"
            text += f"{owner} {escape(name)} - <code>{aid}</code>\n"
            if aid != ADMIN_ID and Utilities.is_main_admin(uid):
                kb.add(Utilities.create_button(f"Remove {name[:10]}", f"rmadmin_{aid}", uid))
        except:
            text += f"👮 <code>{aid}</code>\n"
            if aid != ADMIN_ID and Utilities.is_main_admin(uid):
                kb.add(Utilities.create_button(f"Remove {aid}", f"rmadmin_{aid}", uid))
    if not Utilities.is_main_admin(uid):
        text += "\n\n" + Utilities.get_text(uid, 'only_owner')
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), "nav_admin", uid))
    Utilities.edit_message(call, uid, Utilities.format_border(uid, 'admins_list', text), kb)

def add_admin_step(msg, prompt_id, uid):
    if Utilities.is_cancelled(uid):
        Utilities.clear_cancel(uid)
        return
    Utilities.delete_messages(msg.chat.id, prompt_id, msg.message_id)
    if not Utilities.is_main_admin(uid):
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'error', Utilities.get_text(uid, 'only_owner')), build_back_keyboard(uid, "adm_admins"))
        return
    if not msg.text or not msg.text.strip().isdigit():
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'error', Utilities.get_text(uid, 'invalid_user_id')), build_back_keyboard(uid, "adm_admins"))
        return
    new_id = int(msg.text.strip())
    if Utilities.add_admin(new_id):
        try:
            bot.send_message(new_id, Utilities.format_border(new_id, 'admin_promoted_notify', 'You have been made an admin!'))
        except:
            pass
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'success', Utilities.get_text(uid, 'admin_added', id=new_id)), build_back_keyboard(uid, "adm_admins"))
    else:
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'error', Utilities.get_text(uid, 'admin_exists')), build_back_keyboard(uid, "adm_admins"))

def user_panel(call, tuid, uid):
    users = DatabaseManager.get_users()
    u = users.get(str(tuid))
    if not u:
        return
    banned = u.get('is_banned', 0) == 1
    vip = Utilities.is_user_pro(int(tuid))
    exp = "None"
    if vip:
        e = u.get('expiry')
        if e == 'LIFETIME' or e == 0:
            exp = "Lifetime"
        elif e:
            exp = e
    files = DatabaseManager.get_files()
    u_files = [f for f in files.values() if f.get('user_id') == int(tuid)]
    text = (Utilities.get_text(uid, 'user_id', id=tuid) + '\n' +
            Utilities.get_text(uid, 'user_username', username=u.get('username', 'None')) + '\n' +
            Utilities.get_text(uid, 'user_joined', date=u.get('join_date', '?')) + '\n\n' +
            Utilities.get_text(uid, 'balance', balance=u.get('points', 0)) + '\n' +
            Utilities.get_text(uid, 'rank', rank='VIP' if vip else 'Free') + '\n' +
            Utilities.get_text(uid, 'vip_expiry', expiry=exp) + '\n\n' +
            Utilities.get_text(uid, 'files_count', count=len(u_files)) + '\n' +
            Utilities.get_text(uid, 'user_status', status=Utilities.get_text(uid, 'banned') if banned else Utilities.get_text(uid, 'active')))
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        Utilities.create_button(Utilities.get_text(uid, 'unban') if banned else Utilities.get_text(uid, 'ban'), f"ban_{tuid}", uid),
        Utilities.create_button(Utilities.get_text(uid, 'remove_vip') if vip else Utilities.get_text(uid, 'grant_vip'), f"pro_{tuid}", uid)
    )
    kb.add(
        Utilities.create_button(Utilities.get_text(uid, 'charge'), f"charge_{tuid}", uid),
        Utilities.create_button(Utilities.get_text(uid, 'message_user'), f"msguser_{tuid}", uid)
    )
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), "adm_users", uid))
    Utilities.edit_message(call, uid, Utilities.format_border(uid, 'user_management', text), kb)

def charge_step(msg, tuid, prompt_id, uid):
    if Utilities.is_cancelled(uid):
        Utilities.clear_cancel(uid)
        return
    Utilities.delete_messages(msg.chat.id, prompt_id, msg.message_id)
    if not msg.text or not msg.text.strip().lstrip('-').isdigit():
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'error', Utilities.get_text(uid, 'invalid_number')), build_back_keyboard(uid, f"uctrl_{tuid}"))
        return
    amount = int(msg.text.strip())
    users = DatabaseManager.get_users()
    if str(tuid) in users:
        users[str(tuid)]['points'] = users[str(tuid)].get('points', 0) + amount
        DatabaseManager.save_users(users)
        try:
            bot.send_message(int(tuid), Utilities.format_border(int(tuid), 'points_added_notify', f"<b>{amount}</b> points have been added to your balance."))
        except:
            pass
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'success', Utilities.get_text(uid, 'charge_success', amount=amount)), build_back_keyboard(uid, f"uctrl_{tuid}"))

def message_user_step(msg, tuid, prompt_id, uid):
    if Utilities.is_cancelled(uid):
        Utilities.clear_cancel(uid)
        return
    Utilities.delete_messages(msg.chat.id, prompt_id, msg.message_id)
    try:
        bot.copy_message(int(tuid), msg.chat.id, msg.message_id)
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'success', Utilities.get_text(uid, 'message_sent')), build_back_keyboard(uid, f"uctrl_{tuid}"))
    except:
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'error', Utilities.get_text(uid, 'failed')), build_back_keyboard(uid, f"uctrl_{tuid}"))

def pro_grant_step(msg, tuid, prompt_id, uid):
    if Utilities.is_cancelled(uid):
        Utilities.clear_cancel(uid)
        return
    Utilities.delete_messages(msg.chat.id, prompt_id, msg.message_id)
    if not msg.text or not msg.text.strip().isdigit():
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'error', Utilities.get_text(uid, 'invalid_number')), build_back_keyboard(uid, f"uctrl_{tuid}"))
        return
    days = int(msg.text.strip())
    users = DatabaseManager.get_users()
    if str(tuid) in users:
        if days == 0:
            users[str(tuid)]['expiry'] = 'LIFETIME'
            exp_text = "Lifetime"
        else:
            exp_date = datetime.now() + timedelta(days=days)
            users[str(tuid)]['expiry'] = exp_date.strftime("%Y-%m-%d %H:%M:%S")
            exp_text = f"{days} days"
        DatabaseManager.save_users(users)
        try:
            bot.send_message(int(tuid), Utilities.format_border(int(tuid), 'vip_granted_notify', f"You have been upgraded to VIP for {exp_text}."))
        except:
            pass
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'success', Utilities.get_text(uid, 'grant_vip_success', duration=exp_text)), build_back_keyboard(uid, f"uctrl_{tuid}"))

def ban_toggle(call, tuid, uid):
    users = DatabaseManager.get_users()
    if str(tuid) in users:
        curr = users[str(tuid)].get('is_banned', 0)
        users[str(tuid)]['is_banned'] = 0 if curr == 1 else 1
        DatabaseManager.save_users(users)
        try:
            if users[str(tuid)]['is_banned'] == 1:
                bot.send_message(int(tuid), Utilities.format_border(int(tuid), 'banned', Utilities.get_text(int(tuid), 'user_banned_notify')))
            else:
                bot.send_message(int(tuid), Utilities.format_border(int(tuid), 'unbanned', Utilities.get_text(int(tuid), 'user_unbanned_notify')))
        except:
            pass
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'done'))
        user_panel(call, tuid, uid)

def pro_remove(call, tuid, uid):
    users = DatabaseManager.get_users()
    if str(tuid) in users:
        users[str(tuid)]['expiry'] = None
        DatabaseManager.save_users(users)
        try:
            bot.send_message(int(tuid), Utilities.format_border(int(tuid), 'vip_removed_notify', Utilities.get_text(int(tuid), 'vip_removed_notify')))
        except:
            pass
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'vip_removed'))
        user_panel(call, tuid, uid)

def store_panel(call, uid):
    store = DatabaseManager.get_store()
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'add_store_file'), "add_store", uid))
    for sid, item in store.items():
        kb.add(Utilities.create_button(f"{item['name'][:20]} • {item['price']}pt", f"estore_{sid}", uid))
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), "nav_admin", uid))
    text = Utilities.get_text(uid, 'store_management') + f": {len(store)}"
    Utilities.edit_message(call, uid, Utilities.format_border(uid, 'store_management', text), kb)

def store_add_step(msg, prompt_id, uid):
    if Utilities.is_cancelled(uid):
        Utilities.clear_cancel(uid)
        return
    Utilities.delete_messages(msg.chat.id, prompt_id, msg.message_id)
    if not msg.document:
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'error', Utilities.get_text(uid, 'invalid_file')), build_back_keyboard(uid, "adm_store"))
        return
    m = bot.send_message(msg.chat.id, Utilities.format_border(uid, 'set_price', Utilities.get_text(uid, 'price_prompt')), reply_markup=build_cancel_keyboard(uid, "cancel_admin"))
    Utilities.save_message(msg.chat.id, m.message_id)
    bot.register_next_step_handler(m, store_price_add_step, msg.document, m.message_id, uid)

def store_price_add_step(msg, doc, prompt_id, uid):
    if Utilities.is_cancelled(uid):
        Utilities.clear_cancel(uid)
        return
    Utilities.delete_messages(msg.chat.id, prompt_id, msg.message_id)
    if not msg.text or not msg.text.strip().isdigit():
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'error', Utilities.get_text(uid, 'invalid_price')), build_back_keyboard(uid, "adm_store"))
        return
    sid = Utilities.gen_id()
    store = DatabaseManager.get_store()
    store[sid] = {'name': doc.file_name, 'price': int(msg.text.strip())}
    DatabaseManager.save_store(store)
    finfo = bot.get_file(doc.file_id)
    with open(os.path.join(STORE_DIR, f"{sid}.py"), 'wb') as f:
        f.write(bot.download_file(finfo.file_path))
    Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'success', Utilities.get_text(uid, 'store_added', name=doc.file_name, price=msg.text)), build_back_keyboard(uid, "adm_store"))

def store_edit(call, sid, uid):
    store = DatabaseManager.get_store()
    item = store.get(sid)
    if not item:
        return
    text = Utilities.get_text(uid, 'store_item', name=item['name'], price=item['price'])
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        Utilities.create_button(Utilities.get_text(uid, 'change_price'), f"sprice_{sid}", uid),
        Utilities.create_button(Utilities.get_text(uid, 'delete'), f"delstore_{sid}", uid)
    )
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), "adm_store", uid))
    Utilities.edit_message(call, uid, Utilities.format_border(uid, 'edit_store', text), kb)

def store_price_step(msg, sid, prompt_id, uid):
    if Utilities.is_cancelled(uid):
        Utilities.clear_cancel(uid)
        return
    Utilities.delete_messages(msg.chat.id, prompt_id, msg.message_id)
    if not msg.text or not msg.text.strip().isdigit():
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'error', Utilities.get_text(uid, 'invalid_price')), build_back_keyboard(uid, "adm_store"))
        return
    store = DatabaseManager.get_store()
    if sid in store:
        store[sid]['price'] = int(msg.text.strip())
        DatabaseManager.save_store(store)
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'success', Utilities.get_text(uid, 'price_updated', price=msg.text)), build_back_keyboard(uid, "adm_store"))

def store_delete(call, sid, uid):
    store = DatabaseManager.get_store()
    if sid in store:
        name = store[sid]['name']
        try:
            os.remove(os.path.join(STORE_DIR, f"{sid}.py"))
        except:
            pass
        del store[sid]
        DatabaseManager.save_store(store)
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'store_deleted', name=name))
        store_panel(call, uid)

def upload_step(msg, h_type, prompt_id, uid):
    if Utilities.is_cancelled(uid):
        Utilities.clear_cancel(uid)
        return
    Utilities.delete_messages(msg.chat.id, prompt_id, msg.message_id)
    if not msg.document or not msg.document.file_name.endswith('.py'):
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'error', Utilities.get_text(uid, 'invalid_file')), build_back_keyboard(uid, "nav_upload"))
        return
    if h_type == "free":
        users = DatabaseManager.get_users()
        pts = users.get(str(uid), {}).get('points', 0)
        m = bot.send_message(
            msg.chat.id,
            Utilities.format_border(uid, 'set_duration', Utilities.get_text(uid, 'duration_prompt', name=escape(msg.document.file_name), points=pts, max=pts)),
            reply_markup=build_cancel_keyboard(uid)
        )
        Utilities.save_message(msg.chat.id, m.message_id)
        bot.register_next_step_handler(m, hours_step, msg.document, m.message_id, uid)
    else:
        complete_upload(msg.document, uid, h_type, 0, uid)

def hours_step(msg, doc, prompt_id, uid):
    if Utilities.is_cancelled(uid):
        Utilities.clear_cancel(uid)
        return
    Utilities.delete_messages(msg.chat.id, prompt_id, msg.message_id)
    if not msg.text or not msg.text.strip().isdigit():
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'error', Utilities.get_text(uid, 'invalid_number')), build_back_keyboard(uid, "nav_upload"))
        return
    hours = int(msg.text.strip())
    users = DatabaseManager.get_users()
    pts = users.get(str(uid), {}).get('points', 0)
    if hours < 1:
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'error', Utilities.get_text(uid, 'min_hour')), build_back_keyboard(uid, "nav_upload"))
        return
    if hours > pts:
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'insufficient_points_short', Utilities.get_text(uid, 'insufficient_points', required=hours, available=pts)), build_back_keyboard(uid, "nav_wallet"))
        return
    complete_upload(doc, uid, "free", hours, uid)

def complete_upload(doc, user_id, h_type, hours, uid):
    fid = Utilities.gen_id()
    finfo = bot.get_file(doc.file_id)
    file_content = bot.download_file(finfo.file_path).decode('utf-8')
    if not EncryptionManager.save_encrypted_file(fid, file_content, user_id):
        Utilities.send_message(user_id, uid, Utilities.format_border(uid, 'error', Utilities.get_text(uid, 'save_failed')), build_back_keyboard(uid))
        return
    files = DatabaseManager.get_files()
    files[fid] = {
        'user_id': user_id,
        'file_name': doc.file_name,
        'type': h_type,
        'status': 'pending',
        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'hours': hours
    }
    DatabaseManager.save_files(files)
    settings = DatabaseManager.get_settings()
    if settings.get('auto_approve', True):
        files[fid]['status'] = 'active'
        if h_type == 'free' and hours > 0:
            users = DatabaseManager.get_users()
            if str(user_id) in users:
                users[str(user_id)]['points'] -= hours
                DatabaseManager.save_users(users)
                process_hours[fid] = hours
        DatabaseManager.save_files(files)
        ProcessManager.start_script(fid)
        duration = str(hours) + ' hour(s)' if h_type == 'free' else 'Unlimited'
        text = Utilities.get_text(uid, 'file_accepted', name=doc.file_name, duration=duration)
        Utilities.send_message(user_id, uid, Utilities.format_border(uid, 'accepted', text), build_back_keyboard(uid))
    else:
        duration = str(hours) + ' hour(s)' if h_type == 'free' else ''
        text = Utilities.get_text(uid, 'file_uploaded', name=doc.file_name, type='VIP' if h_type == 'pro' else 'Free', duration=duration)
        Utilities.send_message(user_id, uid, Utilities.format_border(uid, 'pending_review', text), build_back_keyboard(uid))
    try:
        user = bot.get_chat(user_id)
        admin_text = Utilities.get_text(uid, 'file_upload_notify', user=escape(user.first_name), id=user_id,
                                       file=doc.file_name, type='VIP' if h_type == 'pro' else 'Free',
                                       duration=str(hours) + ' hour(s)' if h_type == 'free' else '')
        for adm in DatabaseManager.get_admins():
            try:
                bot.send_message(adm, admin_text, parse_mode="HTML")
            except:
                pass
    except:
        pass

def pending_list(call, uid):
    files = DatabaseManager.get_files()
    pending = {fid: f for fid, f in files.items() if f.get('status') == 'pending'}
    if not pending:
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'no_pending'), show_alert=True)
        return
    kb = types.InlineKeyboardMarkup(row_width=1)
    for fid, f in pending.items():
        ft = "VIP" if f.get('type') == 'pro' else "Free"
        kb.add(Utilities.create_button(f"{ft} {f.get('file_name', '?')[:25]}", f"vpend_{fid}", uid))
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), "nav_admin", uid))
    text = Utilities.get_text(uid, 'pending_files') + f": {len(pending)}"
    Utilities.edit_message(call, uid, Utilities.format_border(uid, 'pending_files', text), kb)

def pending_view(call, fid, uid):
    files = DatabaseManager.get_files()
    f = files.get(fid)
    if not f:
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'file_not_found'))
        return
    content = EncryptionManager.load_encrypted_file(fid)
    preview = "Unable to read file"
    if content:
        safe = escape(content[:1000])
        if len(safe) > 3000:
            safe = safe[:3000] + "\n..."
        preview = f"<pre><code class='language-python'>{safe}</code></pre>"
    try:
        uinfo = bot.get_chat(f['user_id'])
        utext = f"{escape(uinfo.first_name)} (@{uinfo.username if uinfo.username else 'None'})"
    except:
        utext = f"ID: {f['user_id']}"
    text = (Utilities.get_text(uid, 'file', name=f.get('file_name')) + '\n' +
            Utilities.get_text(uid, 'file_owner', owner=utext) + '\n' +
            Utilities.get_text(uid, 'user_id', id=f.get('user_id')) + '\n' +
            Utilities.get_text(uid, 'file_type', type='VIP' if f.get('type') == 'pro' else 'Free') + '\n' +
            (Utilities.get_text(uid, 'duration', duration=str(f.get('hours', 0)) + ' hour(s)') if f.get('type') == 'free' else '') + '\n' +
            Utilities.get_text(uid, 'file_created', created=f.get('created_at')) + '\n\nPreview:\n' + preview)
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        Utilities.create_button(Utilities.get_text(uid, 'approve'), f"approve_{fid}", uid),
        Utilities.create_button(Utilities.get_text(uid, 'reject'), f"reject_{fid}", uid)
    )
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), "adm_pending", uid))
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    m = bot.send_message(call.message.chat.id, Utilities.format_border(uid, 'file_review', text[:4000]), parse_mode="HTML", reply_markup=kb)
    Utilities.save_message(call.message.chat.id, m.message_id)

def approve_file(call, fid, uid):
    files = DatabaseManager.get_files()
    if fid not in files:
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'file_not_found'))
        return
    files[fid]['status'] = 'active'
    h_type = files[fid].get('type')
    hours = files[fid].get('hours', 0)
    user_id = files[fid]['user_id']
    if h_type == 'free' and hours > 0:
        users = DatabaseManager.get_users()
        if str(user_id) in users:
            users[str(user_id)]['points'] -= hours
            DatabaseManager.save_users(users)
            process_hours[fid] = hours
    DatabaseManager.save_files(files)
    ProcessManager.start_script(fid)
    try:
        duration = str(hours) + ' hour(s)' if h_type == 'free' else 'Unlimited'
        text = Utilities.get_text(user_id, 'file_approved', name=files[fid]['file_name'], duration=duration)
        bot.send_message(user_id, Utilities.format_border(user_id, 'approved', text))
    except:
        pass
    bot.answer_callback_query(call.id, Utilities.get_text(uid, 'approved'))
    pending_list(call, uid)

def reject_file(call, fid, uid):
    files = DatabaseManager.get_files()
    if fid not in files:
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'file_not_found'))
        return
    user_id = files[fid]['user_id']
    fname = files[fid]['file_name']
    try:
        encrypted_path = os.path.join(ENCRYPTED_DIR, f"{fid}.enc")
        if os.path.exists(encrypted_path):
            os.remove(encrypted_path)
    except:
        pass
    security = DatabaseManager.get_security()
    file_keys = security.get('file_keys', {})
    if fid in file_keys:
        del file_keys[fid]
        security['file_keys'] = file_keys
        DatabaseManager.save_security(security)
    del files[fid]
    DatabaseManager.save_files(files)
    try:
        bot.send_message(user_id, Utilities.format_border(user_id, 'rejected', Utilities.get_text(user_id, 'file_rejected', name=fname)))
    except:
        pass
    bot.answer_callback_query(call.id, Utilities.get_text(uid, 'rejected'))
    pending_list(call, uid)

def file_panel(call, fid, uid):
    if not Utilities.verify_file_access(fid, uid):
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'access_denied'), show_alert=True)
        return
    files = DatabaseManager.get_files()
    if fid not in files:
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'file_not_found'))
        return
    f = files[fid]
    content = EncryptionManager.load_encrypted_file(fid)
    preview = "Unable to read file"
    if content:
        safe = escape(content[:1000])
        if len(safe) > 3000:
            safe = safe[:3000] + "\n..."
        preview = f"<pre><code class='language-python'>{safe}</code></pre>"
    running = fid in active_processes and active_processes[fid].poll() is None
    hrs = "Unlimited"
    if f.get('type') == 'free' and fid in process_hours:
        hrs = f"{process_hours[fid]} hour(s)"
    text = (Utilities.get_text(uid, 'file', name=f.get('file_name')) + '\n' +
            Utilities.get_text(uid, 'file_type', type='VIP' if f.get('type') == 'pro' else 'Free') + '\n' +
            Utilities.get_text(uid, 'file_status', status=Utilities.get_text(uid, 'running') if running else Utilities.get_text(uid, 'stopped')) + '\n' +
            Utilities.get_text(uid, 'file_remaining', remaining=hrs) + '\n' +
            Utilities.get_text(uid, 'file_created', created=f.get('created_at')) + '\n\nPreview:\n' + preview)
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        Utilities.create_button(Utilities.get_text(uid, 'stop') if running else Utilities.get_text(uid, 'start'), f"toggle_{fid}", uid),
        Utilities.create_button(Utilities.get_text(uid, 'terminal'), f"term_{fid}", uid)
    )
    kb.add(
        Utilities.create_button(Utilities.get_text(uid, 'change_token'), f"chtoken_{fid}", uid),
        Utilities.create_button(Utilities.get_text(uid, 'token_info'), f"tokinfo_{fid}", uid)
    )
    kb.add(
        Utilities.create_button(Utilities.get_text(uid, 'download'), f"dl_{fid}", uid),
        Utilities.create_button(Utilities.get_text(uid, 'delete'), f"delc_{fid}", uid)
    )
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), "nav_files", uid))
    Utilities.edit_message(call, uid, Utilities.format_border(uid, 'file_manager', text), kb)

def toggle_file(call, fid, uid):
    if not Utilities.verify_file_access(fid, uid):
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'access_denied'), show_alert=True)
        return
    files = DatabaseManager.get_files()
    if fid not in files:
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'file_not_found'))
        return
    running = fid in active_processes and active_processes[fid].poll() is None
    if running:
        ProcessManager.stop_script(fid)
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'stopped'))
    else:
        if ProcessManager.start_script(fid):
            bot.answer_callback_query(call.id, Utilities.get_text(uid, 'started'))
        else:
            bot.answer_callback_query(call.id, Utilities.get_text(uid, 'start_failed'), show_alert=True)
    file_panel(call, fid, uid)

def delete_file(call, fid, uid):
    if not Utilities.verify_file_access(fid, uid):
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'access_denied'), show_alert=True)
        return
    ProcessManager.stop_script(fid)
    files = DatabaseManager.get_files()
    if fid in files:
        fname = files[fid].get('file_name', '?')
        try:
            encrypted_path = os.path.join(ENCRYPTED_DIR, f"{fid}.enc")
            if os.path.exists(encrypted_path):
                os.remove(encrypted_path)
        except:
            pass
        try:
            os.remove(os.path.join(LOGS_DIR, f"{fid}.log"))
        except:
            pass
        try:
            env_dir = os.path.join(ENV_DIR, fid)
            shutil.rmtree(env_dir, ignore_errors=True)
        except:
            pass
        security = DatabaseManager.get_security()
        file_keys = security.get('file_keys', {})
        if fid in file_keys:
            del file_keys[fid]
            security['file_keys'] = file_keys
            DatabaseManager.save_security(security)
        del files[fid]
        DatabaseManager.save_files(files)
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'deleted', name=fname))
    u_files = {fid: f for fid, f in files.items() if f.get('user_id') == uid and f.get('status') == 'active'}
    if not u_files:
        kb = types.InlineKeyboardMarkup()
        kb.add(
            Utilities.create_button(Utilities.get_text(uid, 'upload'), "nav_upload", uid),
            Utilities.create_button(Utilities.get_text(uid, 'back'), "nav_main", uid)
        )
        Utilities.edit_message(call, uid, Utilities.format_border(uid, 'my_files_title', Utilities.get_text(uid, 'no_files')), kb)
    else:
        kb = types.InlineKeyboardMarkup(row_width=1)
        for fid, f in u_files.items():
            running = fid in active_processes and active_processes[fid].poll() is None
            icon = "🟢" if running else "🔴"
            ft = "VIP" if f.get('type') == 'pro' else "Free"
            kb.add(Utilities.create_button(f"{icon} {ft} {f.get('file_name', '?')[:25]}", f"manage_{fid}", uid))
        kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), "nav_main", uid))
        Utilities.edit_message(call, uid, Utilities.format_border(uid, 'my_files_title', Utilities.get_text(uid, 'files_count', count=len(u_files))), kb)

def download_file(call, fid, uid):
    if not Utilities.verify_file_access(fid, uid):
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'access_denied'), show_alert=True)
        return
    files = DatabaseManager.get_files()
    if fid not in files:
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'file_not_found'))
        return
    content = EncryptionManager.load_encrypted_file(fid)
    if not content:
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'download_failed'), show_alert=True)
        return
    try:
        temp_path = os.path.join(TEMP_DIR, f"temp_{fid}_{Utilities.gen_id(4)}.py")
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(content)
        thumb = Utilities.get_thumb()
        with open(temp_path, 'rb') as f:
            if thumb:
                with open(thumb, 'rb') as t:
                    bot.send_document(call.message.chat.id, f, thumb=t, caption=f"{files[fid]['file_name']}", parse_mode="HTML")
            else:
                bot.send_document(call.message.chat.id, f, caption=f"{files[fid]['file_name']}", parse_mode="HTML")
        os.remove(temp_path)
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'downloaded'))
    except:
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'download_failed'), show_alert=True)

def terminal(call, fid, uid):
    if not Utilities.verify_file_access(fid, uid):
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'access_denied'), show_alert=True)
        return
    files = DatabaseManager.get_files()
    if fid not in files:
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'file_not_found'))
        return
    running = fid in active_processes and active_processes[fid].poll() is None
    output = Utilities.get_logs(fid, 40)
    text = Utilities.get_text(uid, 'terminal_output', name=files[fid]['file_name'],
                             status=Utilities.get_text(uid, 'running') if running else Utilities.get_text(uid, 'stopped'),
                             output=output)
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        Utilities.create_button(Utilities.get_text(uid, 'refresh'), f"rterm_{fid}", uid),
        Utilities.create_button(Utilities.get_text(uid, 'input'), f"inp_{fid}", uid)
    )
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), f"manage_{fid}", uid))
    Utilities.edit_message(call, uid, Utilities.format_border(uid, 'terminal_title', text), kb)

def input_step(msg, fid, prompt_id, uid):
    if Utilities.is_cancelled(uid):
        Utilities.clear_cancel(uid)
        return
    Utilities.delete_messages(msg.chat.id, prompt_id, msg.message_id)
    if not msg.text:
        return
    if ProcessManager.write_stdin(fid, msg.text):
        text = Utilities.get_text(uid, 'input_sent', cmd=escape(msg.text))
    else:
        text = Utilities.get_text(uid, 'process_not_running')
    Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'input', text), build_back_keyboard(uid, f"term_{fid}"))

def token_step(msg, fid, prompt_id, uid):
    if Utilities.is_cancelled(uid):
        Utilities.clear_cancel(uid)
        return
    Utilities.delete_messages(msg.chat.id, prompt_id, msg.message_id)
    if not msg.text:
        return
    token = msg.text.strip()
    content = EncryptionManager.load_encrypted_file(fid)
    if not content:
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'error', Utilities.get_text(uid, 'file_not_found')), build_back_keyboard(uid, f"manage_{fid}"))
        return
    updated_content = Utilities.update_token_in_memory(content, token)
    if updated_content:
        files = DatabaseManager.get_files()
        if fid in files:
            user_id = files[fid].get('user_id')
            if EncryptionManager.save_encrypted_file(fid, updated_content, user_id):
                Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'success', Utilities.get_text(uid, 'token_updated')), build_back_keyboard(uid, f"manage_{fid}"))
            else:
                Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'error', Utilities.get_text(uid, 'save_failed')), build_back_keyboard(uid, f"manage_{fid}"))
        else:
            Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'error', Utilities.get_text(uid, 'file_not_found')), build_back_keyboard(uid, f"manage_{fid}"))
    else:
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'error', Utilities.get_text(uid, 'token_failed')), build_back_keyboard(uid, f"manage_{fid}"))

def token_info(call, fid, uid):
    if not Utilities.verify_file_access(fid, uid):
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'access_denied'), show_alert=True)
        return
    content = EncryptionManager.load_encrypted_file(fid)
    if not content:
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'file_not_found'), show_alert=True)
        return
    try:
        tokens = re.findall(r"(\d{8,12}:[a-zA-Z0-9_-]{35,})", content)
        if not tokens:
            bot.answer_callback_query(call.id, Utilities.get_text(uid, 'no_token'), show_alert=True)
            return
        token = tokens[0]
        valid, info = Utilities.check_token(token)
        if valid:
            text = Utilities.get_text(uid, 'token_valid') + '\n\n' + \
                   f"Bot name: {escape(info.get('first_name'))}\nUsername: @{info.get('username')}\nID: <code>{info.get('id')}</code>"
        else:
            text = Utilities.get_text(uid, 'token_invalid') + '\n\n' + escape(str(info))
        kb = types.InlineKeyboardMarkup()
        kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), f"manage_{fid}", uid))
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        m = bot.send_message(call.message.chat.id, Utilities.format_border(uid, 'token_info', text), parse_mode="HTML", reply_markup=kb)
        Utilities.save_message(call.message.chat.id, m.message_id)
    except:
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'error'), show_alert=True)

def library_step(msg, prompt_id, uid):
    if Utilities.is_cancelled(uid):
        Utilities.clear_cancel(uid)
        return
    Utilities.delete_messages(msg.chat.id, prompt_id, msg.message_id)
    if not msg.text:
        return
    lib = msg.text.strip()
    m = bot.send_message(msg.chat.id, Utilities.format_border(uid, 'library_install', Utilities.get_text(uid, 'library_install', lib=escape(lib))))
    Utilities.save_message(msg.chat.id, m.message_id)
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", lib], timeout=120)
        text = Utilities.get_text(uid, 'library_installed', lib=escape(lib))
    except subprocess.TimeoutExpired:
        text = Utilities.get_text(uid, 'library_timeout', lib=escape(lib))
    except:
        text = Utilities.get_text(uid, 'library_failed', lib=escape(lib))
    bot.edit_message_text(Utilities.format_border(uid, 'library_install', text), msg.chat.id, m.message_id, parse_mode="HTML", reply_markup=build_back_keyboard(uid))

def broadcast_step(msg, prompt_id, uid):
    if Utilities.is_cancelled(uid):
        Utilities.clear_cancel(uid)
        return
    Utilities.delete_messages(msg.chat.id, prompt_id, msg.message_id)
    users = DatabaseManager.get_users()
    uids = list(users.keys())
    success, failed = 0, 0
    wait = bot.send_message(msg.chat.id, Utilities.format_border(uid, 'broadcast', Utilities.get_text(uid, 'broadcast_sending', count=len(uids))))
    Utilities.save_message(msg.chat.id, wait.message_id)
    for user_id in uids:
        try:
            if msg.content_type == 'text':
                bot.send_message(int(user_id), msg.text, parse_mode="HTML")
            elif msg.content_type == 'photo':
                bot.send_photo(int(user_id), msg.photo[-1].file_id, caption=msg.caption, parse_mode="HTML")
            elif msg.content_type == 'document':
                bot.send_document(int(user_id), msg.document.file_id, caption=msg.caption, parse_mode="HTML")
            success += 1
            time.sleep(0.05)
        except:
            failed += 1
    text = Utilities.get_text(uid, 'broadcast_complete', success=success, failed=failed, total=len(uids))
    bot.edit_message_text(Utilities.format_border(uid, 'broadcast', text), msg.chat.id, wait.message_id, parse_mode="HTML", reply_markup=build_back_keyboard(uid, "nav_admin"))

def channels_panel(call, uid):
    settings = DatabaseManager.get_settings()
    channels = settings.get('channels', [])
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'add_channel'), "add_channel", uid))
    for i, ch in enumerate(channels):
        kb.add(Utilities.create_button(f"Remove {ch['name']}", f"delch_{i}", uid))
    kb.add(Utilities.create_button(Utilities.get_text(uid, 'back'), "nav_admin", uid))
    text = Utilities.get_text(uid, 'channels_list', count=len(channels))
    if channels:
        text += "\n\n" + "\n".join([f"{ch['name']} ({ch['username']})" for ch in channels])
    Utilities.edit_message(call, uid, Utilities.format_border(uid, 'channels', text), kb)

def add_channel_step(msg, prompt_id, uid):
    if Utilities.is_cancelled(uid):
        Utilities.clear_cancel(uid)
        return
    Utilities.delete_messages(msg.chat.id, prompt_id, msg.message_id)
    if not msg.text:
        return
    username = msg.text.strip()
    if not username.startswith('@'):
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'error', Utilities.get_text(uid, 'invalid_username')), build_back_keyboard(uid, "adm_channels"))
        return
    try:
        chat = bot.get_chat(username)
        settings = DatabaseManager.get_settings()
        settings['channels'] = settings.get('channels', []) + [{"username": username, "name": chat.title}]
        DatabaseManager.save_settings(settings)
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'success', Utilities.get_text(uid, 'channel_added', name=chat.title)), build_back_keyboard(uid, "adm_channels"))
    except:
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'error', Utilities.get_text(uid, 'channel_not_found')), build_back_keyboard(uid, "adm_channels"))

def del_channel(call, index, uid):
    settings = DatabaseManager.get_settings()
    try:
        channels = settings.get('channels', [])
        if 0 <= index < len(channels):
            name = channels[index]['name']
            del channels[index]
            settings['channels'] = channels
            DatabaseManager.save_settings(settings)
            bot.answer_callback_query(call.id, Utilities.get_text(uid, 'channel_removed', name=name))
        channels_panel(call, uid)
    except:
        bot.answer_callback_query(call.id, Utilities.get_text(uid, 'error'))

def set_name_step(msg, prompt_id, uid):
    if Utilities.is_cancelled(uid):
        Utilities.clear_cancel(uid)
        return
    Utilities.delete_messages(msg.chat.id, prompt_id, msg.message_id)
    if not msg.text:
        return
    settings = DatabaseManager.get_settings()
    settings['bot_name'] = msg.text.strip()
    DatabaseManager.save_settings(settings)
    Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'success', Utilities.get_text(uid, 'name_set', name=msg.text.strip())), build_back_keyboard(uid, "adm_settings"))

def set_image_step(msg, prompt_id, uid):
    if Utilities.is_cancelled(uid):
        Utilities.clear_cancel(uid)
        return
    Utilities.delete_messages(msg.chat.id, prompt_id, msg.message_id)
    if not msg.photo:
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'error', Utilities.get_text(uid, 'send_image')), build_back_keyboard(uid, "adm_settings"))
        return
    try:
        fid = msg.photo[-1].file_id
        settings = DatabaseManager.get_settings()
        settings['bot_image'] = fid
        DatabaseManager.save_settings(settings)
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'success', Utilities.get_text(uid, 'image_updated')), build_back_keyboard(uid, "adm_settings"))
    except:
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'error', Utilities.get_text(uid, 'failed')), build_back_keyboard(uid, "adm_settings"))

def set_thumb_step(msg, prompt_id, uid):
    if Utilities.is_cancelled(uid):
        Utilities.clear_cancel(uid)
        return
    Utilities.delete_messages(msg.chat.id, prompt_id, msg.message_id)
    if not msg.photo:
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'error', Utilities.get_text(uid, 'send_image')), build_back_keyboard(uid, "adm_settings"))
        return
    try:
        finfo = bot.get_file(msg.photo[-1].file_id)
        path = os.path.join(THUMBS_DIR, "thumb.jpg")
        with open(path, "wb") as f:
            f.write(bot.download_file(finfo.file_path))
        settings = DatabaseManager.get_settings()
        settings['file_thumb'] = path
        DatabaseManager.save_settings(settings)
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'success', Utilities.get_text(uid, 'thumb_updated')), build_back_keyboard(uid, "adm_settings"))
    except:
        Utilities.send_message(msg.chat.id, uid, Utilities.format_border(uid, 'error', Utilities.get_text(uid, 'failed')), build_back_keyboard(uid, "adm_settings"))

def resource_monitoring():
    while True:
        try:
            for fid in list(active_processes.keys()):
                usage = ProcessManager.get_resource_usage(fid)
                if usage:
                    if usage['cpu'] > RESOURCE_LIMITS['max_cpu_percent'] or usage['memory'] > RESOURCE_LIMITS['max_memory_mb']:
                        files = DatabaseManager.get_files()
                        if fid in files:
                            user_id = files[fid]['user_id']
                            ProcessManager.stop_script(fid)
                            try:
                                bot.send_message(user_id, Utilities.format_border(user_id, 'resource_limit_notify', f"Your bot '{files[fid]['file_name']}' was stopped due to exceeding resource limits."))
                            except:
                                pass
                            for adm in DatabaseManager.get_admins():
                                try:
                                    bot.send_message(adm, f"⚠️ Bot {files[fid]['file_name']} (User: {user_id}) stopped due to high resource usage.\nCPU: {usage['cpu']}%\nMemory: {usage['memory']:.2f} MB")
                                except:
                                    pass
            Utilities.cleanup_temp_files()
            Utilities.cleanup_old_logs()
        except:
            pass
        time.sleep(60)

def system_usage_report():
    while True:
        try:
            cpu = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            mem_mb = mem.used / (1024 * 1024)
            process_count = len(active_processes)
            for adm in DatabaseManager.get_admins():
                try:
                    text = Utilities.get_text(adm, 'system_usage', cpu=cpu, mem_mb=round(mem_mb, 1), processes=process_count)
                    bot.send_message(adm, Utilities.format_border(adm, 'system_usage', text), parse_mode="HTML")
                except:
                    pass
        except:
            pass
        time.sleep(3600)

threading.Thread(target=resource_monitoring, daemon=True).start()
threading.Thread(target=system_usage_report, daemon=True).start()

def monitoring_loop():
    while True:
        try:
            files = DatabaseManager.get_files()
            for fid in list(active_processes.keys()):
                proc = active_processes.get(fid)
                if not proc or proc.poll() is not None:
                    if fid in active_processes:
                        del active_processes[fid]
                    continue
                if fid not in files:
                    continue
                uid = str(files[fid]['user_id'])
                if not Utilities.check_subscription(int(uid)):
                    ProcessManager.stop_script(fid)
                    try:
                        bot.send_message(int(uid), Utilities.format_border(int(uid), 'stopped', Utilities.get_text(int(uid), 'stopped_subscription_notify', name=files[fid]['file_name'])))
                    except:
                        pass
                    continue
                if not Utilities.is_user_pro(int(uid)) and fid in process_hours:
                    process_hours[fid] -= 1
                    if process_hours[fid] <= 0:
                        ProcessManager.stop_script(fid)
                        try:
                            bot.send_message(int(uid), Utilities.format_border(int(uid), 'time_expired', Utilities.get_text(int(uid), 'time_expired_notify', name=files[fid]['file_name'])))
                        except:
                            pass
        except Exception as e:
            print(f"Monitoring error: {e}")
        time.sleep(3600)

def keep_alive():
    links = ["https://www.google.com", "https://www.bing.com", "https://www.wikipedia.org"]
    while True:
        try:
            requests.get(random.choice(links), timeout=15)
            time.sleep(random.randint(120, 240))
        except:
            time.sleep(60)

threading.Thread(target=keep_alive, daemon=True).start()
threading.Thread(target=monitoring_loop, daemon=True).start()

init_database()

print("=" * 40)
print("Hosting Bot | White Wolf t.me/j49_c")
print("channel t.me/bshshshkk")
print("=" * 40)

while True:
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"Polling error: {e}")
        time.sleep(5)
