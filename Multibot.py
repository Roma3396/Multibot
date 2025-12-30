import asyncio
import logging
import sqlite3
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# --- KONFIGURATSIYA ---
TOKEN = os.getenv("BOT_TOKEN", "8511080877:AAF44psWL5zdY7Mdomi03e1rojguMwWG7zg")
ADMINS = [7829422043, 6881599988]
CHANNEL_ID = -1003155796926
CHANNEL_LINK = "https://t.me/FeaF_Helping"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- MA'LUMOTLAR BAZASI ---
def init_db():
    conn = sqlite3.connect('films.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)''')
    c.execute('''CREATE TABLE IF NOT EXISTS films 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, photo TEXT, video TEXT, name TEXT, year TEXT, code TEXT, desc TEXT, likes INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS favorites (user_id INTEGER, film_id INTEGER)''')
    conn.commit()
    conn.close()

init_db()

# --- STATES ---
class AdminState(StatesGroup):
    waiting_for_data = State()
    waiting_for_video = State()
    waiting_for_post = State()
    waiting_for_reply = State()

class UserState(StatesGroup):
    waiting_for_search = State()
    waiting_for_support = State()

# --- KEYBOARDS ---
def main_menu(user_id):
    kb = [
        [KeyboardButton(text="🔍 Qidiruv"), KeyboardButton(text="🔥 Rek")],
        [KeyboardButton(text="💾 Saqlangan"), KeyboardButton(text="📩 Murojat")]
    ]
    if user_id in ADMINS:
        kb.append([KeyboardButton(text="🎬 Film joylash"), KeyboardButton(text="📢 Post Joylash")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def back_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔙 Orqaga")]], resize_keyboard=True)

def sub_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Kanalga o'tish", url=CHANNEL_LINK)],
        [InlineKeyboardButton(text="Tasdiqlash ✅", callback_data="check_sub")]
    ])

# --- FUNKSIYALAR ---
async def check_sub(user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["creator", "administrator", "member"]
    except:
        return False

async def send_film_card(chat_id, film):
    text = f"🎬 **{film[3]}**\n\n📅 Yili: {film[4]}\n🔢 Kodi: {film[5]}\n📝 Izoh: {film[6]}\n\n❤️ {film[7]} ta like"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Chapga", callback_data=f"prev_{film[0]}"),
         InlineKeyboardButton(text=f"❤️ {film[7]}", callback_data=f"like_{film[0]}"),
         InlineKeyboardButton(text="💾 Saqlash", callback_data=f"save_{film[0]}"),
         InlineKeyboardButton(text="➡️ O'nga", callback_data=f"next_{film[0]}")],
        [InlineKeyboardButton(text="👁 Tomosha qilish", callback_data=f"watch_{film[0]}")]
    ])
    await bot.send_photo(chat_id, film[1], caption=text, reply_markup=kb, parse_mode="Markdown")

# --- HANDLERS ---
@dp.message(CommandStart())
async def start(message: types.Message):
    conn = sqlite3.connect('films.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users VALUES (?)", (message.from_user.id,))
    conn.commit()
    conn.close()
    
    if await check_sub(message.from_user.id):
        await message.answer(f"Salom {message.from_user.full_name}! Botga xush kelibsiz 🎥", reply_markup=main_menu(message.from_user.id))
    else:
        await message.answer("Botdan foydalanish uchun kanalga obuna bo'ling!", reply_markup=sub_kb())

@dp.callback_query(F.data == "check_sub")
async def verify_sub(call: types.CallbackQuery):
    if await check_sub(call.from_user.id):
        await call.message.delete()
        await call.message.answer("Obuna tasdiqlandi! Asosiy menyu:", reply_markup=main_menu(call.from_user.id))
    else:
        await call.answer("Hali obuna bo'lmagansiz!", show_alert=True)

# --- FILM JOYLASH ---
@dp.message(F.text == "🎬 Film joylash", F.from_user.id.in_(ADMINS))
async def add_film_start(message: types.Message, state: FSMContext):
    await state.set_state(AdminState.waiting_for_data)
    await message.answer(
        "Film oblojkasini (rasm) yuboring va rasm ostiga quyidagicha yozing:\n\n"
        "Nomi\n"
        "Yili\n"
        "Kodi\n"
        "Izoh\n\n"
        "Namuna:\n"
        "Muz yurak\n"
        "2024\n"
        "001\n"
        "Juda zo'r multfilm", 
        reply_markup=back_kb()
    )

@dp.message(AdminState.waiting_for_data, F.photo)
async def get_data(message: types.Message, state: FSMContext):
    if not message.caption:
        await message.answer("Xatolik! Rasm ostiga ma'lumotlarni yozishingiz shart.")
        return
    lines = message.caption.split('\n')
    if len(lines) < 4:
        await message.answer("Ma'lumotlar to'liq emas! Namuna bo'yicha yozing.")
        return
    await state.update_data(
        photo=message.photo[-1].file_id,
        name=lines[0],
        year=lines[1],
        code=lines[2],
        desc="\n".join(lines[3:])
    )
    await state.set_state(AdminState.waiting_for_video)
    await message.answer(f"Ma'lumotlar qabul qilindi! Endi **{lines[0]}** videosini yuboring.")

@dp.message(AdminState.waiting_for_video, F.video)
async def get_video(message: types.Message, state: FSMContext):
    data = await state.get_data()
    conn = sqlite3.connect('films.db')
    c = conn.cursor()
    c.execute("INSERT INTO films (photo, video, name, year, code, desc) VALUES (?,?,?,?,?,?)",
              (data['photo'], message.video.file_id, data['name'], data['year'], data['code'], data['desc']))
    conn.commit()
    conn.close()
    await state.clear()
    await message.answer("Film muvaffaqiyatli saqlandi! 🎬✅", reply_markup=main_menu(message.from_user.id))

# --- KNOPKALAR ISHLASHI (LIKE, SAVE, WATCH, NAVIGATSIYA) ---
@dp.callback_query(F.data.startswith(("next_", "prev_", "like_", "save_", "watch_")))
async def film_actions(call: types.CallbackQuery):
    action, f_id = call.data.split("_")
    conn = sqlite3.connect('films.db')
    c = conn.cursor()

    if action == "like":
        c.execute("UPDATE films SET likes = likes + 1 WHERE id = ?", (f_id,))
        conn.commit()
        c.execute("SELECT likes FROM films WHERE id = ?", (f_id,))
        new_likes = c.fetchone()[0]
        await call.answer(f"Sizga yoqdi! ❤️ (Jami: {new_likes})")
        # Like bosilganda raqam o'zgarishi uchun xabarni yangilash lozim bo'lsa navigatsiya logikasini ishlatsa bo'ladi

    elif action == "save":
        c.execute("SELECT * FROM favorites WHERE user_id = ? AND film_id = ?", (call.from_user.id, f_id))
        if not c.fetchone():
            c.execute("INSERT INTO favorites (user_id, film_id) VALUES (?, ?)", (call.from_user.id, f_id))
            conn.commit()
            await call.answer("Saqlanganlarga qo'shildi! 💾", show_alert=True)
        else:
            await call.answer("Bu film allaqachon saqlangan! ✅", show_alert=True)

    elif action == "watch":
        c.execute("SELECT video FROM films WHERE id = ?", (f_id,))
        v = c.fetchone()
        if v:
            await bot.send_video(call.message.chat.id, v[0], caption="Marhamat, tomosha qiling! 🍿")
        await call.answer()

    elif action in ["next", "prev"]:
        if action == "next":
            c.execute("SELECT * FROM films WHERE id < ? ORDER BY id DESC LIMIT 1", (f_id,))
        else:
            c.execute("SELECT * FROM films WHERE id > ? ORDER BY id ASC LIMIT 1", (f_id,))
        
        film = c.fetchone()
        if film:
            text = f"🎬 **{film[3]}**\n\n📅 Yili: {film[4]}\n🔢 Kodi: {film[5]}\n📝 Izoh: {film[6]}\n\n❤️ {film[7]} ta like"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Chapga", callback_data=f"prev_{film[0]}"),
                 InlineKeyboardButton(text=f"❤️ {film[7]}", callback_data=f"like_{film[0]}"),
                 InlineKeyboardButton(text="💾 Saqlash", callback_data=f"save_{film[0]}"),
                 InlineKeyboardButton(text="➡️ O'nga", callback_data=f"next_{film[0]}")],
                [InlineKeyboardButton(text="👁 Tomosha qilish", callback_data=f"watch_{film[0]}")]
            ])
            await call.message.edit_media(
                types.InputMediaPhoto(media=film[1], caption=text, parse_mode="Markdown"), 
                reply_markup=kb
            )
        else:
            await call.answer("Boshqa film topilmadi! 😊", show_alert=True)

    conn.close()

# --- QIDIRUV ---
@dp.message(F.text == "🔍 Qidiruv")
async def search_start(message: types.Message, state: FSMContext):
    await state.set_state(UserState.waiting_for_search)
    await message.answer("Film nomi yoki kodini yozing:", reply_markup=back_kb())

@dp.message(UserState.waiting_for_search)
async def search_result(message: types.Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await state.clear()
        await message.answer("Asosiy menyu", reply_markup=main_menu(message.from_user.id))
        return
    
    q = message.text.strip()
    conn = sqlite3.connect('films.db')
    c = conn.cursor()
    c.execute("SELECT * FROM films WHERE name LIKE ? OR code = ?", (f'%{q}%', q))
    film = c.fetchone()
    conn.close()
    
    if film:
        await send_film_card(message.chat.id, film)
        await state.clear()
    else:
        await message.answer(f"'{q}' bo'yicha hech narsa topilmadi. Qaytadan urinib ko'ring yoki '🔙 Orqaga' tugmasini bosing.")

# --- BOSHQA FUNKSIYALAR ---
@dp.message(F.text == "🔥 Rek")
async def show_rek(message: types.Message):
    conn = sqlite3.connect('films.db')
    c = conn.cursor()
    c.execute("SELECT * FROM films ORDER BY id DESC LIMIT 1")
    film = c.fetchone()
    conn.close()
    if film: await send_film_card(message.chat.id, film)
    else: await message.answer("Hozircha filmlar yo'q.")

@dp.message(F.text == "💾 Saqlangan")
async def show_saved(message: types.Message):
    conn = sqlite3.connect('films.db')
    c = conn.cursor()
    c.execute("SELECT f.* FROM films f JOIN favorites fav ON f.id = fav.film_id WHERE fav.user_id = ?", (message.from_user.id,))
    films = c.fetchall()
    conn.close()
    if films:
        for film in films: await send_film_card(message.chat.id, film)
    else: await message.answer("Sizda saqlangan filmlar yo'q 📭")

@dp.message(F.text == "📩 Murojat")
async def support(message: types.Message, state: FSMContext):
    await state.set_state(UserState.waiting_for_support)
    await message.answer("Murojatingizni yozing:", reply_markup=back_kb())

@dp.message(UserState.waiting_for_support)
async def send_support(message: types.Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await state.clear()
        await message.answer("Asosiy menyu", reply_markup=main_menu(message.from_user.id))
        return
    for admin in ADMINS:
        await bot.send_message(admin, f"📩 Yangi murojat ({message.from_user.id}):\n{message.text}")
    await message.answer("Murojatingiz yuborildi! ✅")
    await state.clear()

@dp.message(F.text == "📢 Post Joylash", F.from_user.id.in_(ADMINS))
async def post_start(message: types.Message, state: FSMContext):
    await state.set_state(AdminState.waiting_for_post)
    await message.answer("Reklama postini yuboring:", reply_markup=back_kb())

@dp.message(AdminState.waiting_for_post)
async def broadcast(message: types.Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await state.clear()
        await message.answer("Admin panel", reply_markup=main_menu(message.from_user.id))
        return
    conn = sqlite3.connect('films.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = c.fetchall()
    conn.close()
    count = 0
    for user in users:
        try:
            await message.copy_to(user[0])
            count += 1
        except: pass
    await message.answer(f"Post {count} ta foydalanuvchiga yuborildi!")
    await state.clear()

@dp.message(F.text == "🔙 Orqaga")
async def go_back(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Asosiy menyu", reply_markup=main_menu(message.from_user.id))

# --- RUN BOT ---
async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
                                                                               
