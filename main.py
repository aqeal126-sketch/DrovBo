import logging
import asyncio
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, PreCheckoutQuery
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# --- الثوابت الأساسية لمتجر DroV ---
TOKEN = "8901226826:AAEjt55gEpJ4LyaBKr0ts4rYv3QIBjl_H2E"
ADMIN_ID = 8333784255
CHANNEL_URL = "https://t.me/drov70"
LOG_CHANNEL_ID = -1002242131908  # آيدي قناتك ل Log المبيعات

logging.basicConfig(level=logging.ERROR)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- فتح اتصال قاعدة البيانات الآمن متعدد المسارات ---
db_conn = sqlite3.connect("drov_store.db", check_same_thread=False)
db_cursor = db_conn.cursor()

def init_db():
    db_cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0.0,
            referred_by INTEGER DEFAULT NULL,
            is_banned INTEGER DEFAULT 0,
            is_agent INTEGER DEFAULT 0,
            referral_count INTEGER DEFAULT 0,
            lang TEXT DEFAULT 'ar'
        )
    """)
    db_cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price REAL,
            content_type TEXT,
            stock_data TEXT
        )
    """)
    db_cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_name TEXT,
            content_type TEXT,
            item_content TEXT,
            price REAL,
            date TEXT
        )
    """)
    db_cursor.execute("""
        CREATE TABLE IF NOT EXISTS used_hashes (
            tx_hash TEXT PRIMARY KEY,
            user_id INTEGER,
            amount REAL,
            date TEXT
        )
    """)
    db_cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    db_cursor.execute("CREATE TABLE IF NOT EXISTS stats (key TEXT PRIMARY KEY, value REAL DEFAULT 0)")
    
    db_cursor.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('total_sales', 0)")
    db_cursor.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('net_profit', 0)")
    db_cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('ton', 'UQAGuG_0cf0Me23nkD-W4rEY80g2_dt3P3zMvfjaf4VduXsr')")
    db_cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('erc20', '0x0B8061889c457Db2A769a846F0414da3e363fe16')")
    db_cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('trc20', 'TB22EEgggNPZp3Qsjo3xhdB8aaDAKFQjjK')")
    db_cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('btc', 'bc1qveuqtlsh069pja87rr5x2rge4q6wvhvm98zj2j')")
    db_cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('maintenance', '0')")
    db_cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('m_start', '2026-01-01 00:00:00')")
    db_cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('m_end', '2026-01-01 00:00:00')")
    db_conn.commit()

init_db()

# --- محرك فحص الصيانة بالوقت والتاريخ ---
def check_maintenance_status():
    db_cursor.execute("SELECT value FROM config WHERE key = 'maintenance'")
    m_active = db_cursor.fetchone()[0]
    if m_active == "1":
        db_cursor.execute("SELECT value FROM config WHERE key = 'm_start'")
        start_str = db_cursor.fetchone()[0]
        db_cursor.execute("SELECT value FROM config WHERE key = 'm_end'")
        end_str = db_cursor.fetchone()[0]
        try:
            now = datetime.now()
            start_time = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
            end_time = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
            if start_time <= now <= end_time:
                remaining = end_time - now
                hours, remainder = divmod(int(remaining.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)
                return True, f"🛠 **البوت قيد الصيانة المجدولة حالياً**\n\n📅 **بدأت بتاريخ:** `{start_str}`\n🏁 **تنتهي بتاريخ:** `{end_str}`\n\n⏳ **الوقت المتبقي لفتح المتجر تلقائياً:** `{hours}` ساعة و `{minutes}` دقيقة."
            else:
                db_cursor.execute("UPDATE config SET value = '0' WHERE key = 'maintenance'")
                db_conn.commit()
                return False, ""
        except Exception:
            return True, "🛠 وضع الصيانة مفعل حالياً سنعود خلال دقائق!"
    return False, ""

# --- قاموس الترجمة الفوري لجميع لغات البوت الترحيبية الثابتة ---
LOCALES = {
    'ar': {
        'welcome': "🙋‍♂️ أهلاً بك في متجر Drov TG الرقمي 📱✨\n\n🛍️ نوفر لك أفضل الخدمات والأدوات الرقمية بجودة عالية وأسعار مناسبة.\n\n🆔 آيدي حسابك: `{uid}`\n💵 رصيدك الحالي: *{bal}$*\n\n📋 يمكنك استخدام الأزرار بالأسفل للتنقل بين الأقسام",
        'deposit_msg': "💰 قسم شحن الرصيد \n\nيرجى اختيار وسيلة الشحن المناسبة لك من الأزرار أدناه: 💳🚀",
        'crypto_msg': "🪙 الشحن الفوري عبر العملات الرقمية 🚀\n\nيرجى اختيار شبكة التحويل المفضلة لديك لبدء الإيداع المباشر 💳✨",
        'btn_buy': "🛍️ الشراء", 'btn_python': "🐍 شراء أداة بايثون", 'btn_lang': "🌐 اللغة / Language",
        'btn_support': "🧑‍💻 الدعم الفني", 'btn_agents': "👥 الوكلاء", 'btn_deposit': "💳 شحن رصيد",
        'btn_channel': "✅ قناة التفعيلات", 'btn_orders': "⚙️ مشترياتي", 'btn_referral': "🔗 الإحالة",
        'agent_txt': "💼 **الوكيل المعتمد والحصري لمتجر DroV:**\n\n👤 الاسم: *DEAV*\n🔗 حساب التواصل المباشر: @iii306\n\nاضغط على المعرف أعلاه للتواصل الفوري حول التفعيل أو الاستفسار المباشر.",
        'back_crypto': "🔴 العودة للشبكات", 'back_main': "🔴 العودة للقائمة الرئيسية"
    },
    'en': {
        'welcome': "🙋‍♂️ Welcome to Drov TG Digital Store 📱✨\n\n🛍️ We provide you with the best digital services and tools with high quality and reasonable prices.\n\n🆔 Your ID: `{uid}`\n💵 Your Balance: *{bal}$*\n\n📋 You can use the buttons below to navigate between sections",
        'deposit_msg': "💰 Top-up Balance Section\n\nPlease choose your preferred payment method below: 💳🚀",
        'crypto_msg': "🪙 Instant Crypto Top-up 🚀\n\nPlease select your preferred network to start direct deposit 💳✨",
        'btn_buy': "🛍️ Purchase", 'btn_python': "🐍 Buy Python Tool", 'btn_lang': "🌐 Language / اللغة",
        'btn_support': "🧑‍💻 Support", 'btn_agents': "👥 Agents", 'btn_deposit': "💳 Top-up Balance",
        'btn_channel': "✅ Updates Channel", 'btn_orders': "⚙️ My Orders", 'btn_referral': "🔗 Referral System",
        'agent_txt': "💼 **Official & Exclusive Agent for DroV Store:**\n\n👤 Name: *DEAV*\n🔗 Direct Contact: @iii306\n\nClick on the username above to contact the agent immediately.",
        'back_crypto': "🔴 Back to Networks", 'back_main': "🔴 Back to Main Menu"
    },
    'ru': {
        'welcome': "🙋‍♂️ Добро пожаловать в цифровой магазин Drov TG 📱✨\n\n🛍️ Мы предоставляем вам лучшие цифровые услуги и инструменты высокого качества по разумным ценам.\n\n🆔 Ваш ID: `{uid}`\n💵 Ваш баланс: *{bal}$*\n\n📋 Вы можете использовать кнопки ниже для навигации между разделами",
        'deposit_msg': "💰 Раздел пополнения баланса\n\nПожалуйста, выберите удобный способ оплаты ниже: 💳🚀",
        'crypto_msg': "🪙 Мгновенное пополнение криптовалютой 🚀\n\nПожалуйста, выберите сеть для прямого депозита 💳✨",
        'btn_buy': "🛍️ Купить", 'btn_python': "🐍 Купить Python скрипт", 'btn_lang': "🌐 Язык / Language",
        'btn_support': "🧑‍💻 Поддержка", 'btn_agents': "👥 Агенты", 'btn_deposit': "💳 Пополнить баланс",
        'btn_channel': "✅ Канал активации", 'btn_orders': "⚙️ Мои покупки", 'btn_referral': "🔗 Рефералы",
        'agent_txt': "💼 **Официальный представитель DroV Store:**\n\n👤 Имя: *DEAV*\n🔗 Связь: @iii306\n\nНажмите на никнейм для быстрой связи.",
        'back_crypto': "🔴 Назад к сетям", 'back_main': "🔴 Назад в главное меню"
    },
    'fa': {
        'welcome': "🙋‍♂️ به فروشگاه دیجیتال Drov TG خوش آمدید 📱✨\n\n🛍️ ما بهترین خدمات و ابزارهای دیجیتال را با کیفیت بالا و قیمت مناسب به شما ارائه می دهیم.\n\n🆔 شناسه شما: `{uid}`\n💵 موجودی شما: *{bal}$*\n\n📋 برای جابجایی بین بخش ها می توانید از دکمه های زیر استفاده کنید:",
        'deposit_msg': "💰 بخش شارژ حساب\n\nلطفاً روش پرداخت مورد نظر خود را از دکمه‌های زیر انتخاب کنید: 💳🚀",
        'crypto_msg': "🪙 شارژ فوری با ارز دیجیتال 🚀\n\nلطفاً برای شروع واریز مستقیم شبکه مورد نظر خود را انتخاب کنید 💳✨",
        'btn_buy': "🛍️ خرید", 'btn_python': "🐍 خرید ابزار پایتون", 'btn_lang': "🌐 زبان / Language",
        'btn_support': "🧑‍💻 پشتیبانی", 'btn_agents': "👥 نمایندگان", 'btn_deposit': "💳 شارژ حساب",
        'btn_channel': "✅ کانال فعال‌سازی", 'btn_orders': "⚙️ سفارشات من", 'btn_referral': "🔗 زیرمجموعه گیری",
        'back_crypto': "🔴 بازگشت به شبکه‌ها", 'back_main': "🔴 بازگشت به منوی اصلی"
    }
}

class AdminStates(StatesGroup):
    waiting_for_product_name = State()
    waiting_for_content_type = State()
    waiting_for_product_stock = State()
    waiting_for_product_price = State()
    waiting_for_del_id = State()
    waiting_for_charge_username = State()
    waiting_for_charge_amount = State()
    waiting_for_broadcast_msg = State()
    waiting_for_change_price_id = State()
    waiting_for_new_price = State()
    waiting_for_ban_id = State()
    waiting_for_agent_id = State()
    waiting_for_m_start = State()
    waiting_for_m_end = State()

class UserStates(StatesGroup):
    waiting_for_stars = State()
    waiting_for_screenshot = State()

def get_wallet(wallet_type):
    db_cursor.execute("SELECT value FROM config WHERE key = ?", (wallet_type,))
    row = db_cursor.fetchone()
    return row[0] if row else ""

def get_user_lang(user_id):
    db_cursor.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,))
    row = db_cursor.fetchone()
    return row[0] if row and row[0] in LOCALES else 'ar'

def get_main_keyboard(user_id):
    lang = get_user_lang(user_id)
    text_provider = LOCALES[lang]
    builder = InlineKeyboardBuilder()
    
    # السطر الأول: زر الشراء (عريض ولون أخضر)
    builder.row(InlineKeyboardButton(text=text_provider['btn_buy'], callback_data="sections", style="success"))
    
    # السطر الثاني: شراء أداة بايثون (أخضر) واللغة (أخضر)
    builder.row(
        InlineKeyboardButton(text=text_provider['btn_python'], callback_data="buy_python_tools", style="success"),
        InlineKeyboardButton(text=text_provider['btn_lang'], callback_data="change_language", style="success")
    )
    
    # السطر الثالث: الدعم الفني (أزرق) والوكلاء (أزرق)
    builder.row(
        InlineKeyboardButton(text=text_provider['btn_support'], url="https://t.me/xq_7d", style="primary"),
        InlineKeyboardButton(text=text_provider['btn_agents'], callback_data="view_official_agents", style="primary")
    )
    
    # السطر الرابع: شحن رصيد (عريض ولون أحمر)
    builder.row(InlineKeyboardButton(text=text_provider['btn_deposit'], callback_data="deposit", style="danger"))
    
    # السطر الخامس: قناة التفعيلات (أخضر) ومشترياتي (أحمر)
    builder.row(
        InlineKeyboardButton(text=text_provider['btn_channel'], url=CHANNEL_URL, style="success"),
        InlineKeyboardButton(text=text_provider['btn_orders'], callback_data="my_orders", style="danger")
    )
    
    # السطر السادس: الإحالة (عريض ولون أزرق)
    builder.row(InlineKeyboardButton(text=text_provider['btn_referral'], callback_data="referral", style="primary"))
    
    if user_id == ADMIN_ID:
        builder.row(InlineKeyboardButton(text="👑 لوحة تحكم المالك", callback_data="admin_panel", style="primary"))
        
    return builder.as_markup()

def get_deposit_keyboard(user_id):
    lang = get_user_lang(user_id)
    back_text = LOCALES[lang]['back_main']
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐️ شحن عبر نجوم تيليجرام", callback_data="stars_deposit", style="success")],
        [InlineKeyboardButton(text="🪙 شحن عبر العملات الرقمية", callback_data="crypto_menu", style="primary")],
        [InlineKeyboardButton(text=back_text, callback_data="back_to_main", style="danger")]
    ])

def get_crypto_keyboard(user_id):
    lang = get_user_lang(user_id)
    back_deposit = LOCALES[lang]['back_crypto']
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🪩 شبكة USDT TON", callback_data="crypto_invoice_ton", style="success")],
        [InlineKeyboardButton(text="🌐 شبكة إيثيريوم ERC20", callback_data="crypto_invoice_erc20", style="primary")],
        [InlineKeyboardButton(text="🔻 شبكة ترون TRC20", callback_data="crypto_invoice_trc20", style="danger")],
        [InlineKeyboardButton(text="🪙 شبكة BTC (بيتكوين)", callback_data="crypto_invoice_btc", style="success")],
        [InlineKeyboardButton(text=back_deposit, callback_data="deposit", style="danger")]
    ])

KEYBOARD_PANEL = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="➕ إضافة خدمة", callback_data="admin_add_service", style="success"),
     InlineKeyboardButton(text="❌ حذف خدمة", callback_data="admin_manage_services", style="danger")],
    [InlineKeyboardButton(text="💰 تعديل سعر سلعة", callback_data="admin_change_price", style="success"),
     InlineKeyboardButton(text="💵 شحن لمستعمل مستخدم", callback_data="admin_add_balance", style="primary")],
    [InlineKeyboardButton(text="📊 إحصائيات حية", callback_data="admin_stats", style="success"),
     InlineKeyboardButton(text="🛠️ وضع صيانة مؤقت بالوقت", callback_data="admin_toggle_maintenance", style="danger")],
    [InlineKeyboardButton(text="📢 إرسال إذاعة جماعية", callback_data="admin_broadcast", style="primary"),
     InlineKeyboardButton(text="🔒 حظر مستخدم", callback_data="admin_ban_user", style="primary")],
    [InlineKeyboardButton(text="💼 تعيين/إلغاء وكيل للعميل", callback_data="admin_toggle_agent", style="danger")],
    [InlineKeyboardButton(text="🔴 العودة للقائمة الرئيسية", callback_data="back_to_main", style="danger")]
])
BACK_TO_ADMIN = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔴 عودة للوحة التحكم", callback_data="admin_panel", style="danger")]])

def get_user_profile(user_id, username=None):
    db_cursor.execute("SELECT balance, is_banned, is_agent FROM users WHERE user_id = ?", (user_id,))
    row = db_cursor.fetchone()
    if row is None:
        uname = username if username else "بدون يوزر"
        db_cursor.execute("INSERT INTO users (user_id, username, balance, is_banned, is_agent) VALUES (?, ?, ?, 0, 0)", (user_id, uname, 0.0))
        db_conn.commit()
        return 0.0, 0, 0
    return row[0], row[1], row[2]

async def is_user_banned(user_id: int) -> bool:
    db_cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    row = db_cursor.fetchone()
    return row is not None and row[0] == 1

async def process_safety_checks(event, user_id: int) -> bool:
    if user_id == ADMIN_ID: return True
    if await is_user_banned(user_id):
        if isinstance(event, CallbackQuery): await event.answer("🚫 حسابك محظور نهائياً!", show_alert=True)
        else: await event.answer("🚫 عذراً، لقد تم حظر حسابك نهائياً!")
        return False
        
    is_under_maintenance, maintenance_text = check_maintenance_status()
    if is_under_maintenance:
        if isinstance(event, CallbackQuery): await event.answer("🛠️ المتجر مغلق للصيانة المجدولة حالياً!", show_alert=True)
        else: await event.answer(maintenance_text, parse_mode="Markdown")
        return False
    return True

@dp.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    await state.clear()
    uid = msg.from_user.id
    if not await process_safety_checks(msg, uid): return
    uname = msg.from_user.username

    args = msg.text.split()
    db_cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (uid,))
    exists = db_cursor.fetchone()
    
    if not exists and len(args) > 1 and args[1].isdigit():
        referrer = int(args[1])
        if referrer != uid:
            db_cursor.execute("INSERT INTO users (user_id, username, balance, referred_by, referral_count) VALUES (?, ?, 0.0, ?, 1)", (uid, uname, referrer))
            db_cursor.execute("UPDATE users SET balance = balance + 0.05, referral_count = referral_count + 1 WHERE user_id = ?", (referrer,))
            try: await bot.send_message(chat_id=referrer, text=f"🤝 **دخل شخص برابط إحالتك!**\n\nتمت إضافة `+0.05$` لرصيدك تلقائياً.")
            except Exception: pass
            db_conn.commit()
            
    bal, _, _ = get_user_profile(uid, uname)
    lang = get_user_lang(uid)
    welcome_text = LOCALES[lang]['welcome'].format(uid=uid, bal=bal)
    await msg.answer(text=welcome_text, parse_mode="Markdown", reply_markup=get_main_keyboard(uid))

@dp.callback_query(F.data == "change_language")
async def cmd_change_lang(call: CallbackQuery):
    if not await process_safety_checks(call, call.from_user.id): return
    await call.answer()
    kb_languages = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇸🇦 العربية", callback_data="lang_ar", style="primary"),
         InlineKeyboardButton(text="🇺🇸 English", callback_data="lang_en", style="primary")],
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru", style="primary"),
         InlineKeyboardButton(text="🇮🇷 فارسی", callback_data="lang_fa", style="primary")],
        [InlineKeyboardButton(text=LOCALES[get_user_lang(call.from_user.id)]['back_main'], callback_data="back_to_main", style="danger")]
    ])
    await call.message.edit_text("⚙️ **يرجى اختيار لغة البوت المفضلة لديك / Please choose your language:**", reply_markup=kb_languages)

@dp.callback_query(F.data.startswith("lang_"))
async def process_lang_selection(call: CallbackQuery):
    selected_lang = call.data.split("_")[1]
    uid = call.from_user.id
    db_cursor.execute("UPDATE users SET lang = ? WHERE user_id = ?", (selected_lang, uid))
    db_conn.commit()
    await call.answer("✅ Language Updated!", show_alert=False)
    
    bal, _, _ = get_user_profile(uid, call.from_user.username)
    welcome_text = LOCALES[selected_lang]['welcome'].format(uid=uid, bal=bal)
    await call.message.edit_text(text=welcome_text, parse_mode="Markdown", reply_markup=get_main_keyboard(uid))

@dp.callback_query(F.data == "admin_toggle_maintenance")
async def admin_toggle_maintenance_cmd(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.answer()
    db_cursor.execute("SELECT value FROM config WHERE key = 'maintenance'")
    current_status = db_cursor.fetchone()[0]
    
    if current_status == "1":
        db_cursor.execute("UPDATE config SET value = '0' WHERE key = 'maintenance'")
        db_conn.commit()
        await call.message.edit_text("✅ **تم إلغاء وضع الصيانة بنجاح، البوت متاح للعملاء الآن!**", reply_markup=BACK_TO_ADMIN)
    else:
        await call.message.edit_text("✍️ **يرجى إدخال تاريخ ووقت بَدْء الصيانة بالتنسيق التالي بدقة:**\n\n`YYYY-MM-DD HH:MM:SS`\n\n*مثال:* `2026-06-05 20:00:00`")
        await state.set_state(AdminStates.waiting_for_m_start)

@dp.message(AdminStates.waiting_for_m_start)
async def admin_save_m_start(msg: Message, state: FSMContext):
    start_time = msg.text.strip()
    try:
        datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        await state.update_data(m_start=start_time)
        await msg.answer("✍️ **جميل! الآن أرسل تاريخ ووقت انتهاء الصيانة وفتح البوت تلقائياً:**\n\n`YYYY-MM-DD HH:MM:SS`")
        await state.set_state(AdminStates.waiting_for_m_end)
    except ValueError:
        await msg.answer("❌ **التنسيق خاطئ!**")

@dp.message(AdminStates.waiting_for_m_end)
async def admin_save_m_end_and_activate(msg: Message, state: FSMContext):
    end_time = msg.text.strip()
    try:
        datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        data = await state.get_data()
        start_time = data['m_start']
        
        db_cursor.execute("UPDATE config SET value = '1' WHERE key = 'maintenance'")
        db_cursor.execute("UPDATE config SET value = ? WHERE key = 'm_start'", (start_time,))
        db_cursor.execute("UPDATE config SET value = ? WHERE key = 'm_end'", (end_time,))
        db_conn.commit()
        
        await msg.answer(f"🛠 **تم تفعيل الصيانة المجدولة بنجاح!**", reply_markup=BACK_TO_ADMIN)
        await state.clear()
    except ValueError:
        await msg.answer("❌ **التنسيق خاطئ!**")

@dp.callback_query(F.data == "view_official_agents")
async def process_view_agents_cmd(call: CallbackQuery):
    uid = call.from_user.id
    if not await process_safety_checks(call, uid): return
    await call.answer()
    lang = get_user_lang(uid)
    back_text = LOCALES[lang]['back_main']
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧑‍💻 تواصل مع الوكيل DEAV", url="https://t.me/iii306")],
        [InlineKeyboardButton(text=back_text, callback_data="back_to_main", style="danger")]
    ])
    await call.message.edit_text(text=LOCALES[lang]['agent_txt'], parse_mode="Markdown", reply_markup=kb)

@dp.callback_query(F.data == "buy_python_tools")
async def buy_python_tools_cmd(call: CallbackQuery):
    uid = call.from_user.id
    if not await process_safety_checks(call, uid): return
    await call.answer()
    lang = get_user_lang(uid)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 تصفح السكربتات والأدوات الجاهزة", callback_data="sections", style="success")],
        [InlineKeyboardButton(text=LOCALES[lang]['back_main'], callback_data="back_to_main", style="danger")]
    ])
    await call.message.edit_text("🐍 **قسم أدوات وملفات لغة بايثون التلقائية:**\n\nهنا يمكنك شراء وتحميل ملفات السكربتات مباشرة وبشكل فوري.", reply_markup=kb)

@dp.callback_query(F.data == "deposit")
async def process_deposit(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    if not await process_safety_checks(call, uid): return
    await call.answer()
    await state.clear()
    lang = get_user_lang(uid)
    await call.message.edit_text(text=LOCALES[lang]['deposit_msg'], reply_markup=get_deposit_keyboard(uid))

@dp.callback_query(F.data == "crypto_menu")
async def process_crypto_menu(call: CallbackQuery):
    uid = call.from_user.id
    if not await process_safety_checks(call, uid): return
    await call.answer()
    lang = get_user_lang(uid)
    await call.message.edit_text(text=LOCALES[lang]['crypto_msg'], reply_markup=get_crypto_keyboard(uid))

# --- معالج العودة الشامل والآمن للقائمة الرئيسية (تم تصحيحه وتطويره) ---
@dp.callback_query(F.data == "back_to_main")
async def process_back_main(call: CallbackQuery, state: FSMContext):
    if not await process_safety_checks(call, call.from_user.id): return
    await call.answer()
    await state.clear()  # تصفير أي مراحل FSM معلقة لضمان استقرار التنقل
    uid = call.from_user.id
    bal, _ , _ = get_user_profile(uid, call.from_user.username)
    lang = get_user_lang(uid)
    welcome_text = LOCALES[lang]['welcome'].format(uid=uid, bal=bal)
    await call.message.edit_text(text=welcome_text, parse_mode="Markdown", reply_markup=get_main_keyboard(uid))

@dp.callback_query(F.data == "crypto_invoice__back")
async def back_to_crypto_networks(call: CallbackQuery):
    uid = call.from_user.id
    if not await process_safety_checks(call, uid): return
    await call.answer()
    lang = get_user_lang(uid)
    await call.message.edit_text(text=LOCALES[lang]['crypto_msg'], reply_markup=get_crypto_keyboard(uid))

@dp.callback_query(F.data.startswith("crypto_invoice_"))
async def crypto_generate_invoice(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    if not await process_safety_checks(call, uid): return
    await call.answer()
    w_type = call.data.split("_")[2]
    wallet_address = get_wallet(w_type)
    net_names = {"ton": "USDT (شبكة TON)", "erc20": "USDT (شبكة Ethereum ERC20)", "trc20": "USDT (شبكة Tron TRC20)", "btc": "Bitcoin (BTC)"}
    lang = get_user_lang(uid)
    back_btn_text = LOCALES[lang]['back_crypto']
    
    text = (
        f"📥 **بوابة تحويل الإيداع عبر {net_names[w_type]}**\n\n"
        f"🔗 **عنوان محفظة الاستلام الرسمية (اضغط للنسخ):**\n`{wallet_address}`\n\n"
        "📸 **بعد إتمام الدفع الناجح، قم بإرسال لقطة شاشة الإثبات هنا بالبوت ليتم مراجعته يدوياً وضخ رصيدك فوراً!**"
    )
    
    kb_with_back = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=back_btn_text, callback_data="crypto_invoice__back", style="danger")]])
    await call.message.edit_text(text=text, parse_mode="Markdown", reply_markup=kb_with_back)
    await state.update_data(wallet_type=w_type)
    await state.set_state(UserStates.waiting_for_screenshot)

@dp.message(UserStates.waiting_for_screenshot, F.photo)
async def receive_crypto_screenshot(msg: Message, state: FSMContext):
    uid = msg.from_user.id
    photo_id = msg.photo[-1].file_id
    data = await state.get_data()
    w_type = data.get('wallet_type', 'Crypto')
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    admin_text = f"🔔 **إشعار طلب شحن جديد**\n\n👤 يوزر العميل: @{msg.from_user.username}\n🆔 آيدي العميل: `{uid}`\n🪙 الشبكة: `{w_type.upper()}`\n📅 التاريخ: {now_str}"
    await bot.send_photo(chat_id=ADMIN_ID, photo=photo_id, caption=admin_text)
    await msg.answer("⚡ **تم إرسال سكرين شوت الإثبات إلى الإدارة بنجاح!**", reply_markup=get_main_keyboard(uid))
    await state.clear()

@dp.callback_query(F.data == "stars_deposit")
async def stars_deposit_cmd(call: CallbackQuery, state: FSMContext):
    if not await process_safety_checks(call, call.from_user.id): return
    await call.answer()
    await call.message.answer("⭐️ **قسم الشحن عبر نجوم تيليجرام**\n\nالرجاء إرسال عدد النجوم:")
    await state.set_state(UserStates.waiting_for_stars)

@dp.message(UserStates.waiting_for_stars)
async def process_stars_amount(msg: Message, state: FSMContext):
    if not msg.text.isdigit(): return
    stars_count = int(msg.text)
    calculated_credit = (stars_count / 50) * 0.5
    await state.clear()
    await bot.send_invoice(
        chat_id=msg.chat.id, title="⭐️ شحن رصيد DroV", description=f"شحن {stars_count} نجمة تمنحك رصيد بقيمة {calculated_credit}$.",
        payload=f"deposit_stars_{stars_count}", provider_token="", currency="XTR", prices=[LabeledPrice(label="Stars", amount=stars_count)]
    )

@dp.pre_checkout_query()
async def process_pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(msg: Message):
    try:
        payload = msg.successful_payment.invoice_payload
        if payload.startswith("deposit_stars_"):
            stars_shipped = int(payload.split("_")[2])
            added_balance = (stars_shipped / 50) * 0.5
            db_cursor.execute("SELECT balance FROM users WHERE user_id = ?", (msg.from_user.id,))
            row = db_cursor.fetchone()
            db_cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (row[0] + added_balance, msg.from_user.id))
            db_conn.commit()
            await msg.answer(f"✅ **تمت عملية الشحن بنجاح! +{added_balance}$**")
    except Exception: pass

@dp.callback_query(F.data == "sections")
async def process_sections(call: CallbackQuery):
    uid = call.from_user.id
    if not await process_safety_checks(call, uid): return
    await call.answer()
    db_cursor.execute("SELECT id, name, price FROM products")
    rows = db_cursor.fetchall()
    lang = get_user_lang(uid)
    
    builder = InlineKeyboardBuilder()
    text = "🛍️ **السلع والأدوات المتوفرة حالياً للشراء التلقائي الفوري:**\n\n"
    if not rows: text += "🚫 لا توجد سلع مضافة حالياً."
    else:
        for r in rows:
            db_cursor.execute("SELECT is_agent FROM users WHERE user_id = ?", (uid,))
            is_agent = db_cursor.fetchone()[0]
            price = r[2] * 0.85 if is_agent == 1 else r[2]
            text += f"🔹 `{r[1]} | {round(price, 2)}$`\n"
            builder.button(text=f"🛒 شراء: {r[1]} | {round(price, 2)}$", callback_data=f"instant_buy_{r[0]}", style="success")
    builder.button(text=LOCALES[lang]['back_main'], callback_data="back_to_main", style="danger")
    builder.adjust(1)
    await call.message.edit_text(text=text, parse_mode="Markdown", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("instant_buy_"))
async def instant_buy_item(call: CallbackQuery):
    uid = call.from_user.id
    if not await process_safety_checks(call, uid): return
    pid = int(call.data.split("_")[2])
    
    db_cursor.execute("SELECT name, price, stock_data, content_type FROM products WHERE id = ?", (pid,))
    prod = db_cursor.fetchone()
    if not prod: return
    pname, pprice, pstock, ptype = prod
    
    db_cursor.execute("SELECT is_agent FROM users WHERE user_id = ?", (uid,))
    is_agent = db_cursor.fetchone()[0]
    final_price = pprice * 0.85 if is_agent == 1 else pprice
    
    bal, _ = get_user_profile(uid)[:2]
    if bal < final_price:
        await call.answer("❌ رصيدك غير كافٍ!", show_alert=True)
        return
    stocks = pstock.split("||") if pstock else []
    stocks = [s for s in stocks if s.strip() != ""]
    if not stocks:
        await call.answer("❌ نفذ المخزون!", show_alert=True)
        return
        
    await call.answer()
    content = stocks.pop(0)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    db_cursor.execute("INSERT INTO orders (user_id, product_name, content_type, item_content, price, date) VALUES (?, ?, ?, ?, ?, ?)", (uid, pname, ptype, content, final_price, now_str))
    db_cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (final_price, uid))
    new_stock_str = "||".join(stocks)
    db_cursor.execute("UPDATE products SET stock_data = ? WHERE id = ?", (new_stock_str, pid))
    db_conn.commit()
    
    await call.message.answer(f"🎉 **تم الشراء بنجاح!**\n🛍️ السلعة: *{pname}*")
    
    bot_user = await bot.get_me()
    masked_uid = str(uid)[:4] + "xxxx"
    log_text = f"🛍 **عملية شراء جديدة من البوت🚀**\n\n📱 **السلعة:** {pname}\n💵 **السعر:** {round(final_price, 2)}$\n👤 **العميل:** `{masked_uid}`\n✅ **الحالة:** تم التسليم تلقائياً\n📅 **التاريخ:** {now_str}"
    try: await bot.send_message(chat_id=LOG_CHANNEL_ID, text=log_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=" 🎯 𝗗𝒓ο𝒗 𝗧𝗚", url=f"https://t.me/{bot_user.username}", style="primary")]]))
    except Exception: pass
        
    if ptype == "file":
        try: await bot.send_document(chat_id=uid, document=content, caption="✅ ملف السلعة جاهز:")
        except Exception: await bot.send_message(chat_id=uid, text=f"✅ الرابط:\n`{content}`")
    elif ptype == "url":
        await bot.send_message(chat_id=uid, text="👇 اضغط على الزر أدناه:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[[InlineKeyboardButton(text="🔗 فتح الرابط", url=content, style="success")]]]))
    else:
        await bot.send_message(chat_id=uid, text=f"📦 **المخزون المستلم:**\n`{content}`")

@dp.callback_query(F.data == "referral")
async def process_referral(call: CallbackQuery):
    uid = call.from_user.id
    if not await process_safety_checks(call, uid): return
    await call.answer()
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={uid}"
    lang = get_user_lang(uid)
    ref_text = f"🤝 **نظام الإحالة لمتجر DroV**\n\n🔗 **رابط الإحالة الخاص بك للنسخ:**\n`{ref_link}`"
    await call.message.edit_text(text=ref_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=LOCALES[lang]['back_main'], callback_data="back_to_main", style="danger")]]))

@dp.callback_query(F.data == "my_orders")
async def process_my_orders(call: CallbackQuery):
    uid = call.from_user.id
    if not await process_safety_checks(call, uid): return
    await call.answer()
    db_cursor.execute("SELECT product_name, item_content, price, date FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 5", (uid,))
    rows = db_cursor.fetchall()
    text = "📦 **آخر 5 مشتريات سابقة مسجلة في حسابك:**\n\n"
    if not rows: text += "🚫 لا توجد مشتريات."
    else:
        for r in rows: text += f"🛍️ *{r[0]}* - السعر: `{r[2]}$`\n`{r[1]}`\n──────────────────\n"
    lang = get_user_lang(uid)
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=LOCALES[lang]['back_main'], callback_data="back_to_main", style="danger")]]))

@dp.callback_query(F.data == "admin_panel")
async def admin_panel_cmd(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    await call.answer()
    await call.message.edit_text("👑 **لوحة تحكم المالك:**", reply_markup=KEYBOARD_PANEL)

@dp.callback_query(F.data == "admin_toggle_agent")
async def admin_toggle_agent_cmd(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.answer()
    await call.message.edit_text("💼 **أرسل آيدي (User ID) العضو لتغيير رتبة الوكيل له:**")
    await state.set_state(AdminStates.waiting_for_agent_id)

@dp.message(AdminStates.waiting_for_agent_id)
async def admin_process_agent_toggle(msg: Message, state: FSMContext):
    if not msg.text.isdigit(): return
    target_uid = int(msg.text)
    db_cursor.execute("SELECT is_agent FROM users WHERE user_id = ?", (target_uid,))
    row = db_cursor.fetchone()
    if row:
        new_status = 0 if row[0] == 1 else 1
        db_cursor.execute("UPDATE users SET is_agent = ? WHERE user_id = ?", (new_status, target_uid))
        db_conn.commit()
        res = "💼 تم منحه رتبة وكيل (خصم الجملة 15% مفعل)" if new_status == 1 else "✅ تم إلغاء رتبة الوكيل"
        await msg.answer(f"⚙️ العضو `{target_uid}` ➡️ **{res}**", reply_markup=BACK_TO_ADMIN)
    else: await msg.answer("❌ غير مسجل!")
    await state.clear()

@dp.callback_query(F.data == "admin_add_balance")
async def charge_bal(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.edit_text("💸 أرسل يوزر المستخدم لشحن حسابه يدوياً:")
    await state.set_state(AdminStates.waiting_for_charge_username)

@dp.message(AdminStates.waiting_for_charge_username)
async def charge_u_set(msg: Message, state: FSMContext):
    await state.update_data(username=msg.text.strip())
    await msg.answer("💵 أرسل قيمة الرصيد بالدولار:")
    await state.set_state(AdminStates.waiting_for_charge_amount)

@dp.message(AdminStates.waiting_for_charge_amount)
async def charge_u_fin(msg: Message, state: FSMContext):
    try: amount = float(msg.text)
    except ValueError: return
    data = await state.get_data()
    db_cursor.execute("SELECT user_id, balance FROM users WHERE username = ?", (data['username'],))
    row = db_cursor.fetchone()
    if not row:
        await msg.answer("❌ لم يتم العثور عليه!", reply_markup=BACK_TO_ADMIN)
        await state.clear()
        return
    db_cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (row[1] + amount, row[0]))
    db_conn.commit()
    await msg.answer(f"✅ تم الشحن بنجاح بقيمة {amount}$.", reply_markup=BACK_TO_ADMIN)
    await state.clear()

@dp.callback_query(F.data == "admin_change_price")
async def admin_change_price_cmd(call: CallbackQuery, state: FSMContext):
    await call.answer()
    db_cursor.execute("SELECT id, name, price FROM products")
    rows = db_cursor.fetchall()
    text = "💰 **قائمة الأسعار لتعديلها فورا:**\n\n"
    for r in rows: text += f"🆔 معرف: `{r[0]}` | *{r[1]}* -> `{r[2]}$`\n"
    text += "\n✍️ أرسل رقم معرف السلعة:"
    await call.message.edit_text(text)
    await state.set_state(AdminStates.waiting_for_change_price_id)

@dp.message(AdminStates.waiting_for_change_price_id)
async def admin_get_price_id(msg: Message, state: FSMContext):
    if not msg.text.isdigit(): return
    await state.update_data(prod_id=int(msg.text))
    await msg.answer("💰 أرسل السعر الجديد بالدولار:")
    await state.set_state(AdminStates.waiting_for_new_price)

@dp.message(AdminStates.waiting_for_new_price)
async def admin_save_new_price(msg: Message, state: FSMContext):
    try: price = float(msg.text)
    except ValueError: return
    data = await state.get_data()
    db_cursor.execute("UPDATE products SET price = ? WHERE id = ?", (price, data['prod_id']))
    db_conn.commit()
    await msg.answer(f"✅ تم التعديل إلى `{price}$`!", reply_markup=BACK_TO_ADMIN)
    await state.clear()

@dp.callback_query(F.data == "admin_ban_user")
async def admin_ban_user_cmd(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.edit_text("🔒 أرسل آيدي المستخدم لحظره أو فك حظره:")
    await state.set_state(AdminStates.waiting_for_ban_id)

@dp.message(AdminStates.waiting_for_ban_id)
async def admin_process_ban(msg: Message, state: FSMContext):
    if not msg.text.isdigit(): return
    target_uid = int(msg.text)
    db_cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (target_uid,))
    row = db_cursor.fetchone()
    if row:
        new_ban = 0 if row[0] == 1 else 1
        db_cursor.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (new_ban, target_uid))
        db_conn.commit()
        status = "❌ تم الحظر" if new_ban == 1 else "✅ تم فك الحظر"
        await msg.answer(f"⚙️ العضو `{target_uid}` -> **{status}**", reply_markup=BACK_TO_ADMIN)
    await state.clear()

@dp.callback_query(F.data == "admin_stats")
async def show_stats(call: CallbackQuery):
    await call.answer()
    db_cursor.execute("SELECT COUNT(user_id) FROM users")
    u_count = db_cursor.fetchone()[0]
    text = f"📊 **إحصائيات متجرك النظيف:**\n\n👥 عدد المشتركين: `{u_count}`"
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=BACK_TO_ADMIN)

@dp.callback_query(F.data == "admin_add_service")
async def admin_add_service(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.edit_text("✍️ أرسل اسم السلعة الجديدة:")
    await state.set_state(AdminStates.waiting_for_product_name)

@dp.message(AdminStates.waiting_for_product_name)
async def admin_set_name(msg: Message, state: FSMContext):
    await state.update_data(name=msg.text)
    kb_type = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 نص أو كود تفعيل", callback_data="set_type_text", style="primary")],
        [InlineKeyboardButton(text="🔗 رابط تحميل أو قناة", callback_data="set_type_url", style="success")],
        [InlineKeyboardButton(text="📁 ملف", callback_data="set_type_file", style="success")]
    ])
    await msg.answer("⚙️ اختر نوع محتوى هذه السلعة:", reply_markup=kb_type)
    await state.set_state(AdminStates.waiting_for_content_type)

@dp.callback_query(AdminStates.waiting_for_content_type, F.data.startswith("set_type_"))
async def admin_set_type(call: CallbackQuery, state: FSMContext):
    await call.answer()
    ptype = call.data.split("_")[2]
    await state.update_data(content_type=ptype)
    await call.message.edit_text(text="💾 أرسل محتوى السلعة للمخزون (افصل بـ `||` إذا كانت متعددة):")
    await state.set_state(AdminStates.waiting_for_product_stock)

@dp.message(AdminStates.waiting_for_product_stock)
async def admin_set_stock(msg: Message, state: FSMContext):
    data = await state.get_data()
    ptype = data['content_type']
    if ptype == "file":
        stock_content = msg.document.file_id if msg.document else (msg.photo[-1].file_id if msg.photo else msg.text)
    else: stock_content = msg.text
    await state.update_data(stock_data=stock_content)
    await msg.answer("💰 أرسل سعر السلعة بالدولار:")
    await state.set_state(AdminStates.waiting_for_product_price)

@dp.message(AdminStates.waiting_for_product_price)
async def admin_save_full_product(msg: Message, state: FSMContext):
    try: price = float(msg.text)
    except ValueError: return
    data = await state.get_data()
    db_cursor.execute("INSERT INTO products (name, price, content_type, stock_data) VALUES (?, ?, ?, ?)", 
                   (data['name'], price, data['content_type'], data['stock_data']))
    db_conn.commit()
    await msg.answer(f"✅ تم إضافة الخدمة بنجاح!", reply_markup=BACK_TO_ADMIN)
    await state.clear()

@dp.callback_query(F.data == "admin_manage_services")
async def admin_manage_services(call: CallbackQuery, state: FSMContext):
    await call.answer()
    db_cursor.execute("SELECT id, name FROM products LIMIT 15")
    rows = db_cursor.fetchall()
    text = "🔄 **السلع المتاحة حالياً للحذف السريع:**\n\n"
    if not rows: text += "🚫 لا توجد سلع مضافة."
    else:
        for r in rows: text += f"🆔 معرف: `{r[0]}` | *{r[1]}*\n"
        text += "\n✍️ أرسل رقم السلعة لحذفها نهائياً:"
        await state.set_state(AdminStates.waiting_for_del_id)
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=BACK_TO_ADMIN)

@dp.message(AdminStates.waiting_for_del_id)
async def admin_del_id(msg: Message, state: FSMContext):
    if not msg.text.isdigit(): return
    db_cursor.execute("DELETE FROM products WHERE id = ?", (int(msg.text),))
    db_conn.commit()
    await msg.answer("✅ تم الحذف بنجاح.", reply_markup=BACK_TO_ADMIN)
    await state.clear()

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_cmd(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.edit_text("📢 أرسل نص الرسالة التي تريد بثها:")
    await state.set_state(AdminStates.waiting_for_broadcast_msg)

@dp.message(AdminStates.waiting_for_broadcast_msg)
async def b_cast_send(msg: Message, state: FSMContext):
    db_cursor.execute("SELECT user_id FROM users")
    rows = db_cursor.fetchall()
    sc = 0
    for r in rows:
        try:
            await bot.send_message(chat_id=r[0], text=f"📢 **تحديث من إدارة DroV:**\n\n{msg.text}")
            sc += 1
            await asyncio.sleep(0.03)
        except Exception: continue
    await msg.answer(f"✅ تمت الإذاعة بنجاح إلى {sc} مستخدم.", reply_markup=BACK_TO_ADMIN)
    await state.clear()

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
