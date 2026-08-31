
import os, sqlite3, random, time
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
from aiogram.types import BufferedInputFile

TOKEN = os.getenv("BOT_TOKEN")
DB="database.db"
COOLDOWN=1*60*60
ADMIN_ID=5952134460

db=sqlite3.connect(DB)
c=db.cursor()
c.execute("CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY,name TEXT,size INTEGER DEFAULT 0,debt INTEGER DEFAULT 0,last_grow INTEGER DEFAULT 0)")
c.execute("CREATE TABLE IF NOT EXISTS battles(id INTEGER PRIMARY KEY AUTOINCREMENT,creator INTEGER,bet INTEGER,active INTEGER DEFAULT 1)")
c.execute("CREATE TABLE IF NOT EXISTS loans(lender_id INTEGER, borrower_id INTEGER, amount INTEGER, loan_time INTEGER DEFAULT 0)")
c.execute("CREATE TABLE IF NOT EXISTS listings(id INTEGER PRIMARY KEY AUTOINCREMENT, seller_id INTEGER, celeb TEXT, price INTEGER, active INTEGER DEFAULT 1)")
c.execute("CREATE TABLE IF NOT EXISTS game_loans(user_id INTEGER PRIMARY KEY, amount INTEGER, due_time INTEGER)")
db.commit()

def user(uid,name):
    c.execute("INSERT OR IGNORE INTO users(user_id,name) VALUES(?,?)",(uid,name))
    c.execute("UPDATE users SET name=? WHERE user_id=?",(name,uid))
    db.commit()

dp=Dispatcher()

@dp.message(Command("grow"))
async def grow(m:Message):
    user(m.from_user.id,m.from_user.full_name)
    size,last=c.execute("SELECT size,last_grow FROM users WHERE user_id=?",(m.from_user.id,)).fetchone()
    now=int(time.time())
    if now-last<COOLDOWN:
        rem=(COOLDOWN-(now-last))//60
        return await m.reply(f"⏳ هنوز {rem} دقیقه تا رشد بعدی مونده!")
    delta=random.randint(5,20)
    size=max(0,size+delta)
    c.execute("UPDATE users SET size=?,last_grow=? WHERE user_id=?",(size,now,m.from_user.id)); db.commit()
    await m.reply(
        f"🌱 نتیجه رشد\n\n🍆 تغییر: {delta:+} سانت\n📏 اندازه فعلی: {size} سانت\n😎 ادامه بده قهرمان!"
    )

@dp.message(Command("size"))
async def size(m:Message):
    user(m.from_user.id,m.from_user.full_name)
    s,d=c.execute("SELECT size,debt FROM users WHERE user_id=?",(m.from_user.id,)).fetchone()
    await m.reply(
        f"📊 پروفایل شما\n\n🍆 اندازه: {s} سانت\n💸 بدهی: {d} سانت"
    )

@dp.message(Command("loan"))
async def loan(m:Message):
    try:
        amt=int(m.text.split()[1])
    except:
        return await m.reply("Reply to a user and use /loan 5")

    if not m.reply_to_message:
        return await m.reply("Reply to a user and use /loan 5")

    lender=m.from_user.id
    borrower=m.reply_to_message.from_user.id

    if lender==borrower:
        return await m.reply("You can't loan yourself.")

    user(lender,m.from_user.full_name)
    user(borrower,m.reply_to_message.from_user.full_name)

    s=c.execute("SELECT size FROM users WHERE user_id=?",(lender,)).fetchone()[0]

    if s<amt:
        return await m.reply("Not enough cm.")

    day_ago = int(time.time()) - 24*60*60
    borrowed_today = c.execute(
        "SELECT COALESCE(SUM(amount),0) FROM loans WHERE borrower_id=? AND loan_time>?",
        (borrower, day_ago)
    ).fetchone()[0]

    if borrowed_today + amt > 50:
        remaining = max(0, 50 - borrowed_today)
        return await m.reply(
            f"❌ این کاربر امروز {borrowed_today} سانت وام گرفته!\n"
            f"حداکثر روزانه ۵۰ سانته.\n"
            f"{'دیگه نمیتونه وام بگیره!' if remaining == 0 else f'فقط {remaining} سانت دیگه میتونه بگیره.'}"
        )

    c.execute("UPDATE users SET size=size-? WHERE user_id=?",(amt,lender))
    c.execute("UPDATE users SET size=size+? WHERE user_id=?",(amt,borrower))
    c.execute("INSERT INTO loans VALUES(?,?,?)",(lender,borrower,int(time.time())))
    db.commit()

    await m.reply(f"💸 وام انجام شد!\n\nمقدار: {amt} سانت\n📊 این کاربر امروز {borrowed_today+amt}/50 سانت وام گرفته")

@dp.message(Command("repay"))
async def repay(m:Message):
    try: amt=int(m.text.split()[1])
    except: return await m.reply("Usage: /repay 5")
    user(m.from_user.id,m.from_user.full_name)
    s,d=c.execute("SELECT size,debt FROM users WHERE user_id=?",(m.from_user.id,)).fetchone()
    amt=min(amt,s,d)
    c.execute("UPDATE users SET size=?,debt=? WHERE user_id=?",(s-amt,d-amt,m.from_user.id)); db.commit()
    await m.reply(f"✅ Repaid {amt} cm")

@dp.message(Command("top"))
async def top(m:Message):
    rows=c.execute("SELECT name,size FROM users ORDER BY size DESC LIMIT 10").fetchall()
    txt="🏆 جدول بزرگان\n\n"
    for i,(n,s) in enumerate(rows,1): txt+=f"{i}. {n} — {s} سانت\n"
    await m.reply(txt)

@dp.message(Command("pvp"))
async def pvp(m:Message):
    try: bet=int(m.text.split()[1])
    except: return await m.reply("Usage: /pvp 30")
    user(m.from_user.id,m.from_user.full_name)
    s=c.execute("SELECT size FROM users WHERE user_id=?",(m.from_user.id,)).fetchone()[0]
    if s<bet: return await m.reply("Not enough cm.")
    cur = c.execute(
        "INSERT INTO battles(creator,bet) VALUES(?,?)",
        (m.from_user.id, bet)
    )
    db.commit()
    bid=cur.lastrowid
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⚔️ قبول دوئل",callback_data=f"pvp:{bid}")]])
    await m.reply(f"⚔️ دوئل مرگبار!\n\n💰 شرط: {bet} سانت\n\nبرنده همه رو می‌بره!",reply_markup=kb)

@dp.callback_query(F.data.startswith("pvp:"))
async def accept(q:CallbackQuery):
    bid=int(q.data.split(":")[1])
    row=c.execute("SELECT creator,bet,active FROM battles WHERE id=?",(bid,)).fetchone()
    if not row or row[2]==0: return await q.answer("Expired")
    creator,bet,_=row
    if q.from_user.id==creator: return await q.answer("Not yourself")
    user(q.from_user.id,q.from_user.full_name)
    s1=c.execute("SELECT size FROM users WHERE user_id=?",(creator,)).fetchone()[0]
    s2=c.execute("SELECT size FROM users WHERE user_id=?",(q.from_user.id,)).fetchone()[0]
    if s1<bet or s2<bet: return await q.answer("Not enough cm")
    winner=random.choice([creator,q.from_user.id])
    loser=q.from_user.id if winner==creator else creator
    c.execute("UPDATE users SET size=size+? WHERE user_id=?",(bet,winner))
    c.execute("UPDATE users SET size=size-? WHERE user_id=?",(bet,loser))
    c.execute("UPDATE battles SET active=0 WHERE id=?",(bid,))
    db.commit()
    winner_name=c.execute("SELECT name FROM users WHERE user_id=?",(winner,)).fetchone()[0]
    await q.message.edit_text(f"🏆 پایان دوئل!\n\n👑 برنده: {winner_name}\n💰 جایزه: {bet} سانت\n\n😂 بازنده باید بیشتر تمرین کنه!")


# ===== Mafia Team PvP System =====
c.execute("CREATE TABLE IF NOT EXISTS mafia_battles(id INTEGER PRIMARY KEY AUTOINCREMENT,creator INTEGER,opponent INTEGER,bet INTEGER,active INTEGER DEFAULT 1,chat_id INTEGER)")
c.execute("CREATE TABLE IF NOT EXISTS mafia_members(battle_id INTEGER,user_id INTEGER,name TEXT,team INTEGER)")
db.commit()

def mafia_counts(bid):
    t1=c.execute("SELECT COUNT(*) FROM mafia_members WHERE battle_id=? AND team=1",(bid,)).fetchone()[0]
    t2=c.execute("SELECT COUNT(*) FROM mafia_members WHERE battle_id=? AND team=2",(bid,)).fetchone()[0]
    return t1,t2

def mafia_board(bid,creator_name,opp_name,bet,status="🔫 جنگ مافیا شروع شد!"):
    t1,t2=mafia_counts(bid)
    return (
        f"{status}\n\n"
        f"🔴 تیم {creator_name}  در مقابل  🔵 تیم {opp_name}\n"
        f"💰 ورودی هر نفر: {bet} سانت\n\n"
        f"هر کی میخواد وارد بشه دکمه تیمش رو بزنه (مخفیانه ثبت میشه، تیم‌بندی معلوم نیست)!\n"
        f"👥 تعداد شرکت‌کننده‌ها: {t1+t2}\n\n"
        f"وقتی آماده بودید، سازنده یا حریف دکمه «شروع نبرد» رو بزنه."
    )

@dp.message(Command("mafia"))
async def mafia_start(m:Message):
    if not m.reply_to_message:
        return await m.reply("⚠️ روی پیام حریف ریپلای کن و بنویس /mafia [مبلغ]\nمثال: /mafia 5")
    try:
        bet=int(m.text.split()[1])
    except:
        return await m.reply("⚠️ استفاده: /mafia [مبلغ]\nمثال: /mafia 5")
    if bet<=0:
        return await m.reply("❌ مبلغ باید مثبت باشه!")
    creator=m.from_user.id
    opponent=m.reply_to_message.from_user.id
    if creator==opponent:
        return await m.reply("❌ نمیتونی با خودت مافیا بازی کنی!")
    if m.reply_to_message.from_user.is_bot:
        return await m.reply("❌ نمیتونی با بات مافیا بازی کنی!")
    user(creator,m.from_user.full_name)
    user(opponent,m.reply_to_message.from_user.full_name)
    s=c.execute("SELECT size FROM users WHERE user_id=?",(creator,)).fetchone()[0]
    if s<bet:
        return await m.reply("❌ سانت کافی نداری!")
    c.execute("UPDATE users SET size=size-? WHERE user_id=?",(bet,creator))
    cur=c.execute("INSERT INTO mafia_battles(creator,opponent,bet,chat_id) VALUES(?,?,?,?)",(creator,opponent,bet,m.chat.id))
    db.commit()
    bid=cur.lastrowid
    c.execute("INSERT INTO mafia_members(battle_id,user_id,name,team) VALUES(?,?,?,1)",(bid,creator,m.from_user.full_name))
    db.commit()
    kb=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔴 تیم {m.from_user.full_name}",callback_data=f"mjoin:{bid}:1"),
         InlineKeyboardButton(text=f"🔵 تیم {m.reply_to_message.from_user.full_name}",callback_data=f"mjoin:{bid}:2")],
        [InlineKeyboardButton(text="🏁 شروع نبرد و شمارش",callback_data=f"mstart:{bid}")]
    ])
    await m.reply(
        mafia_board(bid,m.from_user.full_name,m.reply_to_message.from_user.full_name,bet),
        reply_markup=kb
    )

@dp.callback_query(F.data.startswith("mjoin:"))
async def mafia_join(q:CallbackQuery):
    _,bid,team=q.data.split(":")
    bid=int(bid); team=int(team)
    row=c.execute("SELECT creator,opponent,bet,active FROM mafia_battles WHERE id=?",(bid,)).fetchone()
    if not row or row[3]==0:
        return await q.answer("⚠️ این نبرد تموم شده!",show_alert=True)
    creator,opponent,bet,_=row
    uid=q.from_user.id
    already=c.execute("SELECT team FROM mafia_members WHERE battle_id=? AND user_id=?",(bid,uid)).fetchone()
    if already:
        return await q.answer("⚠️ قبلاً مخفیانه وارد یه تیم شدی!",show_alert=True)
    user(uid,q.from_user.full_name)
    s=c.execute("SELECT size FROM users WHERE user_id=?",(uid,)).fetchone()[0]
    if s<bet:
        return await q.answer("❌ سانت کافی نداری!",show_alert=True)
    c.execute("UPDATE users SET size=size-? WHERE user_id=?",(bet,uid))
    c.execute("INSERT INTO mafia_members(battle_id,user_id,name,team) VALUES(?,?,?,?)",(bid,uid,q.from_user.full_name,team))
    db.commit()
    creator_name=c.execute("SELECT name FROM users WHERE user_id=?",(creator,)).fetchone()[0]
    opp_name=c.execute("SELECT name FROM users WHERE user_id=?",(opponent,)).fetchone()[0]
    await q.answer("✅ مخفیانه وارد تیم شدی!")
    try:
        await q.message.edit_text(
            mafia_board(bid,creator_name,opp_name,bet),
            reply_markup=q.message.reply_markup
        )
    except:
        pass

@dp.callback_query(F.data.startswith("mstart:"))
async def mafia_resolve(q:CallbackQuery):
    bid=int(q.data.split(":")[1])
    row=c.execute("SELECT creator,opponent,bet,active FROM mafia_battles WHERE id=?",(bid,)).fetchone()
    if not row or row[3]==0:
        return await q.answer("⚠️ این نبرد تموم شده!",show_alert=True)
    creator,opponent,bet,_=row
    if q.from_user.id not in (creator,opponent):
        return await q.answer("⚠️ فقط سازنده یا حریف میتونه نبرد رو شروع کنه!",show_alert=True)
    members=c.execute("SELECT user_id,name,team FROM mafia_members WHERE battle_id=?",(bid,)).fetchall()
    team1=[(u,n) for u,n,t in members if t==1]
    team2=[(u,n) for u,n,t in members if t==2]
    tie=len(team1)==len(team2)
    if len(team1)>len(team2):
        winners,losers,wteam=team1,team2,1
    elif len(team2)>len(team1):
        winners,losers,wteam=team2,team1,2
    else:
        wteam=random.choice([1,2])
        winners,losers=(team1,team2) if wteam==1 else (team2,team1)
    total_pot=bet*len(members)
    share=total_pot//len(winners) if winners else 0
    for uid,_ in winners:
        c.execute("UPDATE users SET size=size+? WHERE user_id=?",(share,uid))
    c.execute("UPDATE mafia_battles SET active=0 WHERE id=?",(bid,))
    db.commit()
    win_names="، ".join(n for _,n in winners) or "-"
    lose_names="، ".join(n for _,n in losers) or "-"
    color="🔴" if wteam==1 else "🔵"
    await q.message.edit_text(
        f"🔫 پایان جنگ مافیا!\n\n"
        f"{color} تیم برنده ({len(winners)} نفر): {win_names}\n"
        f"💀 تیم بازنده ({len(losers)} نفر): {lose_names}\n\n"
        f"💰 کل جایزه: {total_pot} سانت\n"
        f"🎁 سهم هر برنده: {share} سانت\n\n"
        f"{'😂 مساوی بودن، شانس تصمیم گرفت!' if tie else '👑 تیم بزرگتر برد!'}"
    )
    await q.answer("🏁 نبرد تموم شد!")


# ===== Mafia2 Team PvP (reveals full team lineup at the end) =====
c.execute("CREATE TABLE IF NOT EXISTS mafia2_battles(id INTEGER PRIMARY KEY AUTOINCREMENT,creator INTEGER,opponent INTEGER,bet INTEGER,active INTEGER DEFAULT 1,chat_id INTEGER)")
c.execute("CREATE TABLE IF NOT EXISTS mafia2_members(battle_id INTEGER,user_id INTEGER,name TEXT,team INTEGER)")
db.commit()

def mafia2_counts(bid):
    t1=c.execute("SELECT COUNT(*) FROM mafia2_members WHERE battle_id=? AND team=1",(bid,)).fetchone()[0]
    t2=c.execute("SELECT COUNT(*) FROM mafia2_members WHERE battle_id=? AND team=2",(bid,)).fetchone()[0]
    return t1,t2

def mafia2_board(bid,creator_name,opp_name,bet,status="🔫 جنگ مافیا شروع شد!"):
    t1,t2=mafia2_counts(bid)
    return (
        f"{status}\n\n"
        f"🔴 تیم {creator_name}  در مقابل  🔵 تیم {opp_name}\n"
        f"💰 ورودی هر نفر: {bet} سانت\n\n"
        f"هر کی میخواد وارد بشه دکمه تیمش رو بزنه (مخفیانه ثبت میشه، تیم‌بندی معلوم نیست)!\n"
        f"👥 تعداد شرکت‌کننده‌ها: {t1+t2}\n\n"
        f"وقتی آماده بودید، سازنده یا حریف دکمه «شروع نبرد» رو بزنه.\n"
        f"ℹ️ در پایان، لیست کامل هر دو تیم فاش میشه."
    )

@dp.message(Command("mafia2"))
async def mafia2_start(m:Message):
    if not m.reply_to_message:
        return await m.reply("⚠️ روی پیام حریف ریپلای کن و بنویس /mafia2 [مبلغ]\nمثال: /mafia2 5")
    try:
        bet=int(m.text.split()[1])
    except:
        return await m.reply("⚠️ استفاده: /mafia2 [مبلغ]\nمثال: /mafia2 5")
    if bet<=0:
        return await m.reply("❌ مبلغ باید مثبت باشه!")
    creator=m.from_user.id
    opponent=m.reply_to_message.from_user.id
    if creator==opponent:
        return await m.reply("❌ نمیتونی با خودت مافیا بازی کنی!")
    if m.reply_to_message.from_user.is_bot:
        return await m.reply("❌ نمیتونی با بات مافیا بازی کنی!")
    user(creator,m.from_user.full_name)
    user(opponent,m.reply_to_message.from_user.full_name)
    s=c.execute("SELECT size FROM users WHERE user_id=?",(creator,)).fetchone()[0]
    if s<bet:
        return await m.reply("❌ سانت کافی نداری!")
    c.execute("UPDATE users SET size=size-? WHERE user_id=?",(bet,creator))
    cur=c.execute("INSERT INTO mafia2_battles(creator,opponent,bet,chat_id) VALUES(?,?,?,?)",(creator,opponent,bet,m.chat.id))
    db.commit()
    bid=cur.lastrowid
    c.execute("INSERT INTO mafia2_members(battle_id,user_id,name,team) VALUES(?,?,?,1)",(bid,creator,m.from_user.full_name))
    db.commit()
    kb=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔴 تیم {m.from_user.full_name}",callback_data=f"m2join:{bid}:1"),
         InlineKeyboardButton(text=f"🔵 تیم {m.reply_to_message.from_user.full_name}",callback_data=f"m2join:{bid}:2")],
        [InlineKeyboardButton(text="🏁 شروع نبرد و شمارش",callback_data=f"m2start:{bid}")]
    ])
    await m.reply(
        mafia2_board(bid,m.from_user.full_name,m.reply_to_message.from_user.full_name,bet),
        reply_markup=kb
    )

@dp.callback_query(F.data.startswith("m2join:"))
async def mafia2_join(q:CallbackQuery):
    _,bid,team=q.data.split(":")
    bid=int(bid); team=int(team)
    row=c.execute("SELECT creator,opponent,bet,active FROM mafia2_battles WHERE id=?",(bid,)).fetchone()
    if not row or row[3]==0:
        return await q.answer("⚠️ این نبرد تموم شده!",show_alert=True)
    creator,opponent,bet,_=row
    uid=q.from_user.id
    already=c.execute("SELECT team FROM mafia2_members WHERE battle_id=? AND user_id=?",(bid,uid)).fetchone()
    if already:
        return await q.answer("⚠️ قبلاً مخفیانه وارد یه تیم شدی!",show_alert=True)
    user(uid,q.from_user.full_name)
    s=c.execute("SELECT size FROM users WHERE user_id=?",(uid,)).fetchone()[0]
    if s<bet:
        return await q.answer("❌ سانت کافی نداری!",show_alert=True)
    c.execute("UPDATE users SET size=size-? WHERE user_id=?",(bet,uid))
    c.execute("INSERT INTO mafia2_members(battle_id,user_id,name,team) VALUES(?,?,?,?)",(bid,uid,q.from_user.full_name,team))
    db.commit()
    creator_name=c.execute("SELECT name FROM users WHERE user_id=?",(creator,)).fetchone()[0]
    opp_name=c.execute("SELECT name FROM users WHERE user_id=?",(opponent,)).fetchone()[0]
    await q.answer("✅ مخفیانه وارد تیم شدی!")
    try:
        await q.message.edit_text(
            mafia2_board(bid,creator_name,opp_name,bet),
            reply_markup=q.message.reply_markup
        )
    except:
        pass

@dp.callback_query(F.data.startswith("m2start:"))
async def mafia2_resolve(q:CallbackQuery):
    bid=int(q.data.split(":")[1])
    row=c.execute("SELECT creator,opponent,bet,active FROM mafia2_battles WHERE id=?",(bid,)).fetchone()
    if not row or row[3]==0:
        return await q.answer("⚠️ این نبرد تموم شده!",show_alert=True)
    creator,opponent,bet,_=row
    if q.from_user.id not in (creator,opponent):
        return await q.answer("⚠️ فقط سازنده یا حریف میتونه نبرد رو شروع کنه!",show_alert=True)
    members=c.execute("SELECT user_id,name,team FROM mafia2_members WHERE battle_id=?",(bid,)).fetchall()
    team1=[(u,n) for u,n,t in members if t==1]
    team2=[(u,n) for u,n,t in members if t==2]
    tie=len(team1)==len(team2)
    if len(team1)>len(team2):
        winners,wteam=team1,1
    elif len(team2)>len(team1):
        winners,wteam=team2,2
    else:
        wteam=random.choice([1,2])
        winners=team1 if wteam==1 else team2
    total_pot=bet*len(members)
    share=total_pot//len(winners) if winners else 0
    for uid,_ in winners:
        c.execute("UPDATE users SET size=size+? WHERE user_id=?",(share,uid))
    c.execute("UPDATE mafia2_battles SET active=0 WHERE id=?",(bid,))
    db.commit()
    creator_name=c.execute("SELECT name FROM users WHERE user_id=?",(creator,)).fetchone()[0]
    opp_name=c.execute("SELECT name FROM users WHERE user_id=?",(opponent,)).fetchone()[0]
    win_label=f"🔴 تیم {creator_name}" if wteam==1 else f"🔵 تیم {opp_name}"
    await q.message.edit_text(
        f"🔫 پایان جنگ مافیا!\n\n"
        f"👥 مجموع شرکت‌کننده‌ها: {len(members)} نفر\n\n"
        f"👑 برنده: {win_label} ({len(winners)} نفر)\n"
        f"💰 کل جایزه: {total_pot} سانت\n"
        f"🎁 سهم هر برنده: {share} سانت\n\n"
        f"{'😂 مساوی بودن، شانس تصمیم گرفت!' if tie else '👑 تیم بزرگتر برد!'}\n\n"
        f"🤫 اینکه کی تو کدوم تیم بود مخفی می‌مونه!"
    )
    await q.answer("🏁 نبرد تموم شد!")


# ===== Celebrity Collection System =====
c.execute("CREATE TABLE IF NOT EXISTS collections(user_id INTEGER, celeb TEXT, paid_price INTEGER DEFAULT 0, locked INTEGER DEFAULT 0)")
db.commit()


CELEBS = {
    "Ana de Armas": ("S",300,150,"https://i.postimg.cc/JzdhGdRj/download-(4).jpg"),
    "Kylie Jenner": ("S",300,150,"https://i.postimg.cc/HkKppcty/download-(5).jpg"),
    "Sydney Sweeney": ("S",300,150,"https://i.postimg.cc/4NxZVbLF/download-(6).jpg"),
    "Olivia Cooke": ("A",200,100,"https://i.postimg.cc/G3kJGv8k/olivia-cooke-in-the-girlfriend.jpg"),
    "Scarlett Johansson": ("A",200,100,"https://i.postimg.cc/rmT2mSRG/download-(7).jpg"),
    "Sabrina Carpenter": ("A",200,100,"https://i.postimg.cc/4dPqxjgJ/Sabrina-Carpenter.jpg"),
    "Dua Lipa": ("A",100,50,"https://i.postimg.cc/VsM021zP/download-(8).jpg"),
    "Anya Taylor Joy": ("B",100,50,"https://i.postimg.cc/1XF4D05F/margot-anya-taylor-joy.jpg"),
    "Jenna Ortega": ("A",100,50,"https://i.postimg.cc/cL068nqV/jenna-ortega.jpg"),
    "Sophie Tatcher": ("A",100,50,"https://i.postimg.cc/d0S0XNhp/1031465120909581257.jpg"),
    "Mia Plays": ("B",100,50,"https://i.postimg.cc/GmLhpnYg/1083186147870726920.jpg"),
    "Angelina Jolie": ("A",100,50,"https://i.postimg.cc/g05Y4w5Y/angelina-jolie-(1).jpg"),
    "Anne Hauthway": ("B",100,50,"https://i.postimg.cc/kgY9X67D/Anne-Hathaway.jpg"),
    "Emma Watson": ("B",100,50,"https://i.postimg.cc/kGyPrDjq/Belle.jpg"),
    "Billie Eilish": ("S",100,50,"https://i.postimg.cc/L6NFNYYY/Billie-Eilish.jpg"),
    "Emilia Clarke": ("B",100,50,"https://i.postimg.cc/vZkjNWQ2/download-(1).jpg"),
    "Billie Eiliish": ("A",100,50,"https://i.postimg.cc/kGbjb56c/download-(9).jpg"),
    "Folorance Pugh": ("B",100,50,"https://i.postimg.cc/D0NdwPp4/florence.jpg"),
    "AZAD": ("B",100,50,"https://i.postimg.cc/k4XxNpkW/images-(1).jpg"),
    "Elizabet Olson": ("B",100,50,"https://i.postimg.cc/MKxj14V6/Sally-Owen-icon.jpg"),
    "Victoria Pederetti": ("B",100,50,"https://i.postimg.cc/5tFthq8y/victoria-pedretti.jpg"),
    "Double KIIR": ("A",100,50,"https://i.postimg.cc/G38vrV1C/ssss.jpg"),
    "Habibi": ("B",100,50,"https://i.postimg.cc/wBj6zCZN/sd.jpg"),
    "Faghih": ("B",100,50,"https://i.postimg.cc/sXfGtH4f/sss-1.jpg"),
    "Natalie Dyer": ("B",100,50,"https://i.postimg.cc/j5cYmL3J/this-pic.jpg"),
}


TIER_CELEBS = {
    "S": [(n, v[1], v[3]) for n, v in CELEBS.items() if v[0] == "S"],
    "A": [(n, v[1], v[3]) for n, v in CELEBS.items() if v[0] == "A"],
    "B": [(n, v[1], v[3]) for n, v in CELEBS.items() if v[0] == "B"],
}
TIER_LABELS = {
    "S": "🥇 Tier S",
    "A": "🥈 Tier A",
    "B": "🥉 Tier B",
}
TIER_PRICES = {"S": (300, 150), "A": (200, 100), "B": (100, 50)}

def build_market_caption(tier, page):
    celebs = TIER_CELEBS[tier]
    name, price, photo = celebs[page]
    buy_price, spin_price = TIER_PRICES[tier]
    label = TIER_LABELS[tier]
    txt = (
        f"🛒 بازار سلبریتی\n"
        f"{label} — صفحه {page+1}/{len(celebs)}\n\n"
        f"👑 {name}\n"
        f"💰 خرید: {price} سانت\n"
        f"🎰 اسپین: {spin_price} سانت\n\n"
        f"🛒 /buy {name}\n"
        f"🎰 /spin {tier.lower()}"
    )
    return txt, photo

def build_market_kb(tier, page):
    celebs = TIER_CELEBS[tier]
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"mkt:{tier}:{page-1}"))
    if page < len(celebs) - 1:
        buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"mkt:{tier}:{page+1}"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else None

async def fetch_photo(url: str) -> BufferedInputFile | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    filename = url.split("/")[-1]
                    return BufferedInputFile(data, filename=filename)
    except Exception:
        pass
    return None

# ===== Telegram file_id photo cache (avoid re-downloading/re-uploading every time) =====
c.execute("CREATE TABLE IF NOT EXISTS photo_cache(url TEXT PRIMARY KEY, file_id TEXT)")
db.commit()

async def resolve_photo(url: str):
    """Accepts either a Telegram file_id (used directly, zero download) or an http(s) URL
    (downloaded once, then cached as a file_id from then on)."""
    if not url:
        return None
    if not url.startswith("http://") and not url.startswith("https://"):
        # Already a Telegram file_id — use it straight away, nothing to download.
        return url
    row = c.execute("SELECT file_id FROM photo_cache WHERE url=?", (url,)).fetchone()
    if row:
        return row[0]
    return await fetch_photo(url)

def cache_photo(url: str, sent_message):
    """Call after successfully sending/editing a photo that was NOT already cached, to store its file_id."""
    try:
        if sent_message and sent_message.photo:
            c.execute("INSERT OR REPLACE INTO photo_cache(url,file_id) VALUES(?,?)", (url, sent_message.photo[-1].file_id))
            db.commit()
    except Exception:
        pass

@dp.message(Command("getfileid"))
async def get_file_id(m: Message):
    if m.from_user.id != ADMIN_ID:
        return
    target = m.reply_to_message.photo[-1] if (m.reply_to_message and m.reply_to_message.photo) else (m.photo[-1] if m.photo else None)
    if not target:
        return await m.reply("⚠️ یه عکس بفرست (یا روی یه عکس ریپلای بزن) و /getfileid رو بنویس.")
    await m.reply(f"🆔 file_id:\n`{target.file_id}`", parse_mode="Markdown")

@dp.message(Command("market"))
async def market(m:Message):
    for tier in ["S", "A", "B"]:
        txt, photo_url = build_market_caption(tier, 0)
        kb = build_market_kb(tier, 0)
        photo = await resolve_photo(photo_url) if photo_url else None
        if photo:
            sent = await m.bot.send_photo(m.chat.id, photo, caption=txt, reply_markup=kb)
            if isinstance(photo, BufferedInputFile):
                cache_photo(photo_url, sent)
        else:
            await m.bot.send_message(m.chat.id, txt, reply_markup=kb)

@dp.callback_query(F.data.startswith("mkt:"))
async def market_page_nav(q: CallbackQuery):
    _, tier, page = q.data.split(":")
    page = int(page)
    txt, photo_url = build_market_caption(tier, page)
    kb = build_market_kb(tier, page)
    photo = await resolve_photo(photo_url) if photo_url else None
    try:
        if photo and q.message.photo:
            edited = await q.message.edit_media(
                media=InputMediaPhoto(media=photo, caption=txt),
                reply_markup=kb
            )
            if isinstance(photo, BufferedInputFile) and hasattr(edited, "photo"):
                cache_photo(photo_url, edited)
        elif q.message.photo:
            await q.message.edit_caption(caption=txt, reply_markup=kb)
        else:
            await q.message.edit_text(txt, reply_markup=kb)
    except Exception as e:
        await q.answer(f"خطا: {e}", show_alert=True)
        return
    await q.answer()

@dp.message(Command("collection"))
async def collection(m:Message):
    if m.reply_to_message:
        target = m.reply_to_message.from_user
        user(target.id, target.full_name)
        rows = c.execute("SELECT celeb FROM collections WHERE user_id=?", (target.id,)).fetchall()
        if not rows:
            return await m.reply(f"📚 {target.full_name} هنوز چیزی نداره.")
        celebs = [r[0] for r in rows]
        await send_collection_page(m.chat.id, target.id, celebs, 0, m.bot, viewer_id=m.from_user.id)
    else:
        user(m.from_user.id, m.from_user.full_name)
        rows = c.execute("SELECT celeb FROM collections WHERE user_id=?", (m.from_user.id,)).fetchall()
        if not rows:
            return await m.reply("📚 هنوز چیزی نداری.")
        celebs = [r[0] for r in rows]
        await send_collection_page(m.chat.id, m.from_user.id, celebs, 0, m.bot, viewer_id=m.from_user.id)

async def send_collection_page(chat_id, owner_id, celebs, page, bot, viewer_id=None):
    name = celebs[page]
    tier, price, spin, photo_url = CELEBS[name]
    tier_label = {"S": "🥇 S", "A": "🥈 A", "B": "🥉 B"}[tier]
    txt = (
        f"📚 کالکشن — {page+1}/{len(celebs)}\n\n"
        f"👑 {name}\n"
        f"🏅 تیر: {tier_label}\n"
        f"💰 ارزش: {price} سانت\n\n"
        f"🛒 /sell {name}\n"
        f"🏪 /list {name} [قیمت]"
    )
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"col:{owner_id}:{page-1}"))
    if page < len(celebs) - 1:
        buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"col:{owner_id}:{page+1}"))
    kb = InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else None
    photo = await resolve_photo(photo_url) if photo_url else None
    if photo:
        sent = await bot.send_photo(chat_id, photo, caption=txt, reply_markup=kb)
        if isinstance(photo, BufferedInputFile):
            cache_photo(photo_url, sent)
    else:
        await bot.send_message(chat_id, txt, reply_markup=kb)

@dp.callback_query(F.data.startswith("col:"))
async def collection_nav(q: CallbackQuery):
    _, owner_id, page = q.data.split(":")
    owner_id = int(owner_id)
    page = int(page)
    # allow anyone to browse
    rows = c.execute("SELECT celeb FROM collections WHERE user_id=?", (owner_id,)).fetchall()
    celebs = [r[0] for r in rows]
    if page >= len(celebs):
        page = len(celebs) - 1
    name = celebs[page]
    tier, price, spin, photo_url = CELEBS[name]
    tier_label = {"S": "🥇 S", "A": "🥈 A", "B": "🥉 B"}[tier]
    txt = (
        f"📚 کالکشن — {page+1}/{len(celebs)}\n\n"
        f"👑 {name}\n"
        f"🏅 تیر: {tier_label}\n"
        f"💰 ارزش: {price} سانت\n\n"
        f"🛒 /sell {name}\n"
        f"🏪 /list {name} [قیمت]"
    )
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"col:{owner_id}:{page-1}"))
    if page < len(celebs) - 1:
        buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"col:{owner_id}:{page+1}"))
    kb = InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else None
    photo = await resolve_photo(photo_url) if photo_url else None
    try:
        if photo and q.message.photo:
            edited = await q.message.edit_media(
                media=InputMediaPhoto(media=photo, caption=txt),
                reply_markup=kb
            )
            if isinstance(photo, BufferedInputFile) and hasattr(edited, "photo"):
                cache_photo(photo_url, edited)
        elif q.message.photo:
            await q.message.edit_caption(caption=txt, reply_markup=kb)
        else:
            await q.message.edit_text(txt, reply_markup=kb)
    except Exception as e:
        await q.answer(f"خطا: {e}", show_alert=True)
        return
    await q.answer()


@dp.message(Command("buy"))
async def buy(m:Message):
    name=m.text.replace("/buy","",1).strip()

    if name not in CELEBS:
        return await m.reply("❌ سلبریتی پیدا نشد.")

    tier,price,spin,photo=CELEBS[name]

    user(m.from_user.id,m.from_user.full_name)

    size=c.execute("SELECT size FROM users WHERE user_id=?",(m.from_user.id,)).fetchone()[0]

    if size<price:
        return await m.reply("💸 سانت کافی نداری!")

    tier_key = CELEBS[name][0]

    # check if user already owns it
    user_owned = c.execute("SELECT 1 FROM collections WHERE user_id=? AND celeb=?", (m.from_user.id, name)).fetchone()
    if user_owned:
        return await m.reply("📚 این سلبریتی رو داری!")

    # tier S and A are exclusive — check if anyone owns it (locked or not)
    # tier B is only exclusive if locked
    if tier_key in ("S", "A"):
        owned = c.execute("SELECT user_id FROM collections WHERE celeb=?", (name,)).fetchone()
        if owned:
            owner_name = c.execute("SELECT name FROM users WHERE user_id=?", (owned[0],)).fetchone()[0]
            return await m.reply(f"❌ این سلبریتی قبلاً توسط {owner_name} خریداری شده!")
    else:
        # tier B — only block if locked
        locked = c.execute("SELECT user_id FROM collections WHERE celeb=? AND locked=1", (name,)).fetchone()
        if locked:
            owner_name = c.execute("SELECT name FROM users WHERE user_id=?", (locked[0],)).fetchone()[0]
            return await m.reply(f"🔒 این سلبریتی توسط {owner_name} قفل شده!")

    c.execute("UPDATE users SET size=size-? WHERE user_id=?",(price,m.from_user.id))
    c.execute("INSERT INTO collections(user_id,celeb,paid_price) VALUES(?,?,?)",(m.from_user.id,name,price))
    db.commit()

    photo_url = photo
    photo = await resolve_photo(photo_url) if photo_url else None
    if photo:
        sent = await m.bot.send_photo(m.chat.id, photo, caption=f"🎉 خرید موفق!\n\n👑 {name}")
        if isinstance(photo, BufferedInputFile):
            cache_photo(photo_url, sent)
    else:
        await m.reply(f"🎉 خرید موفق!\n\n👑 {name}")

@dp.message(Command("spin"))
async def spin(m:Message):
    try:
        tier=m.text.split()[1].upper()
    except:
        return await m.reply("استفاده: /spin s | a | b")

    prices={"S":150,"A":100,"B":50}

    if tier not in prices:
        return await m.reply("Tier باید s یا a یا b باشد.")

    cost=prices[tier]

    user(m.from_user.id,m.from_user.full_name)

    size=c.execute("SELECT size FROM users WHERE user_id=?",(m.from_user.id,)).fetchone()[0]

    if size<cost:
        return await m.reply("💸 سانت کافی نداری!")

    pool=[n for n,v in CELEBS.items() if v[0]==tier]
    celeb=random.choice(pool)

    c.execute("UPDATE users SET size=size-? WHERE user_id=?",(cost,m.from_user.id))

    spin_tier = CELEBS[celeb][0]
    user_owned = c.execute("SELECT 1 FROM collections WHERE user_id=? AND celeb=?", (m.from_user.id, celeb)).fetchone()
    if user_owned:
        c.execute("UPDATE users SET size=size+? WHERE user_id=?",(cost,m.from_user.id))
        db.commit()
        return await m.reply(f"🔄 این سلبریتی رو قبلاً داری!\n\n👑 {celeb}\n💰 {cost} سانت برگشت داده شد.")

    if spin_tier in ("S", "A"):
        owned = c.execute("SELECT user_id FROM collections WHERE celeb=?", (celeb,)).fetchone()
        if owned:
            c.execute("UPDATE users SET size=size+? WHERE user_id=?",(cost,m.from_user.id))
            db.commit()
            owner_name=c.execute("SELECT name FROM users WHERE user_id=?",(owned[0],)).fetchone()[0]
            return await m.reply(f"🔄 این سلبریتی قبلاً توسط {owner_name} خریداری شده!\n\n👑 {celeb}\n💰 {cost} سانت برگشت داده شد.")
    else:
        locked = c.execute("SELECT user_id FROM collections WHERE celeb=? AND locked=1", (celeb,)).fetchone()
        if locked:
            c.execute("UPDATE users SET size=size+? WHERE user_id=?",(cost,m.from_user.id))
            db.commit()
            owner_name=c.execute("SELECT name FROM users WHERE user_id=?",(locked[0],)).fetchone()[0]
            return await m.reply(f"🔒 این سلبریتی توسط {owner_name} قفل شده!\n\n👑 {celeb}\n💰 {cost} سانت برگشت داده شد.")

    c.execute(
        "INSERT INTO collections(user_id,celeb,paid_price) VALUES(?,?,?)",
        (m.from_user.id,celeb,cost//2)
    )
    db.commit()

    photo_url=CELEBS[celeb][3]
    photo = await resolve_photo(photo_url) if photo_url else None
    if photo:
        sent = await m.bot.send_photo(m.chat.id, photo, caption=f"🎰 اسپین موفق!\n\n👑 {celeb}")
        if isinstance(photo, BufferedInputFile):
            cache_photo(photo_url, sent)
    else:
        await m.reply(f"🎰 اسپین موفق!\n\n👑 {celeb}")

@dp.message(Command("collectors"))
async def collectors(m:Message):
    rows=c.execute("""
        SELECT users.name,COUNT(collections.celeb) AS total
        FROM users
        LEFT JOIN collections
        ON users.user_id=collections.user_id
        GROUP BY users.user_id
        ORDER BY total DESC
        LIMIT 10
    """).fetchall()

    txt="🏆 بهترین کلکسیونرها\n\n"

    for i,(name,total) in enumerate(rows,1):
        txt+=f"{i}. {name} — {total} سلبریتی\n"

    await m.reply(txt)


@dp.message(Command("list"))
async def list_celeb(m:Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2:
        return await m.reply("Usage: /list [نام] [قیمت]\nمثال: /list Kylie Jenner 500")
    try:
        rest = parts[1].rsplit(None, 1)
        name = rest[0].strip()
        price = int(rest[1])
    except:
        return await m.reply("Usage: /list [نام] [قیمت]\nمثال: /list Kylie Jenner 500")
    if name not in CELEBS:
        return await m.reply("❌ سلبریتی پیدا نشد.")
    user(m.from_user.id, m.from_user.full_name)
    owned = c.execute("SELECT 1 FROM collections WHERE user_id=? AND celeb=?", (m.from_user.id, name)).fetchone()
    if not owned:
        return await m.reply("❌ این سلبریتی رو نداری!")
    # cancel any previous listing for this celeb
    c.execute("UPDATE listings SET active=0 WHERE seller_id=? AND celeb=?", (m.from_user.id, name))
    cur = c.execute("INSERT INTO listings(seller_id, celeb, price) VALUES(?,?,?)", (m.from_user.id, name, price))
    db.commit()
    lid = cur.lastrowid
    tier, orig_price, spin, photo_url = CELEBS[name]
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"🛒 خرید به قیمت {price} سانت", callback_data=f"buyoff:{lid}")
    ]])
    caption = (
        f"🏪 فروش سلبریتی!\n\n"
        f"👑 {name}\n"
        f"💰 قیمت: {price} سانت\n"
        f"👤 فروشنده: {m.from_user.full_name}"
    )
    photo = await resolve_photo(photo_url) if photo_url else None
    if photo:
        sent = await m.bot.send_photo(m.chat.id, photo, caption=caption, reply_markup=kb)
        if isinstance(photo, BufferedInputFile):
            cache_photo(photo_url, sent)
    else:
        await m.reply(caption, reply_markup=kb)

@dp.callback_query(F.data.startswith("buyoff:"))
async def buyoff(q: CallbackQuery):
    lid = int(q.data.split(":")[1])
    row = c.execute("SELECT seller_id, celeb, price, active FROM listings WHERE id=?", (lid,)).fetchone()
    if not row or row[3] == 0:
        return await q.answer("❌ این آگهی دیگه فعال نیست!", show_alert=True)
    seller_id, name, price, _ = row
    buyer_id = q.from_user.id
    if buyer_id == seller_id:
        return await q.answer("❌ نمیتونی از خودت بخری!", show_alert=True)
    user(buyer_id, q.from_user.full_name)
    buyer_size = c.execute("SELECT size FROM users WHERE user_id=?", (buyer_id,)).fetchone()[0]
    if buyer_size < price:
        return await q.answer("❌ سانت کافی نداری!", show_alert=True)
    # transfer
    c.execute("UPDATE users SET size=size-? WHERE user_id=?", (price, buyer_id))
    c.execute("UPDATE users SET size=size+? WHERE user_id=?", (price, seller_id))
    c.execute("DELETE FROM collections WHERE user_id=? AND celeb=?", (seller_id, name))
    c.execute("INSERT INTO collections(user_id, celeb) VALUES(?,?)", (buyer_id, name))
    c.execute("UPDATE listings SET active=0 WHERE id=?", (lid,))
    db.commit()
    seller_name = c.execute("SELECT name FROM users WHERE user_id=?", (seller_id,)).fetchone()[0]
    await q.message.edit_caption(
        caption=(
            f"✅ معامله انجام شد!\n\n"
            f"👑 {name}\n"
            f"💰 قیمت: {price} سانت\n"
            f"🛒 خریدار: {q.from_user.full_name}\n"
            f"💸 فروشنده: {seller_name}"
        )
    )
    await q.answer("✅ خرید موفق!")

@dp.message(Command("sell"))
async def sell(m:Message):
    name=m.text.replace("/sell","",1).strip()
    if name not in CELEBS:
        return await m.reply("❌ سلبریتی پیدا نشد.")
    user(m.from_user.id,m.from_user.full_name)
    owned=c.execute(
        "SELECT paid_price FROM collections WHERE user_id=? AND celeb=?",
        (m.from_user.id,name)
    ).fetchone()
    if not owned:
        return await m.reply("❌ این سلبریتی رو نداری!")
    paid=owned[0]
    c.execute("DELETE FROM collections WHERE user_id=? AND celeb=?",(m.from_user.id,name))
    c.execute("UPDATE users SET size=size+? WHERE user_id=?",(paid,m.from_user.id))
    db.commit()
    await m.reply(f"💸 فروش موفق!\n\n👑 {name}\n💰 {paid} سانت به حسابت اضافه شد!")

@dp.message(Command("lock"))
async def lock_celeb(m:Message):
    name = m.text.replace("/lock","",1).strip()
    if name not in CELEBS:
        return await m.reply("❌ سلبریتی پیدا نشد.")
    tier_key = CELEBS[name][0]
    if tier_key != "B":
        return await m.reply("❌ فقط سلبریتی‌های Tier B نیاز به قفل دارن!")
    user(m.from_user.id, m.from_user.full_name)
    owned = c.execute("SELECT locked FROM collections WHERE user_id=? AND celeb=?", (m.from_user.id, name)).fetchone()
    if not owned:
        return await m.reply("❌ این سلبریتی رو نداری!")
    if owned[0] == 1:
        return await m.reply("🔒 این سلبریتی قبلاً قفله!")
    size = c.execute("SELECT size FROM users WHERE user_id=?", (m.from_user.id,)).fetchone()[0]
    if size < 25:
        return await m.reply("❌ برای قفل کردن به ۲۵ سانت نیاز داری!")
    c.execute("UPDATE users SET size=size-25 WHERE user_id=?", (m.from_user.id,))
    c.execute("UPDATE collections SET locked=1 WHERE user_id=? AND celeb=?", (m.from_user.id, name))
    db.commit()
    await m.reply(f"🔒 {name} قفل شد!\n\n💰 ۲۵ سانت کسر شد.\nحالا کسی دیگه نمیتونه این سلبریتی رو بخره.")

@dp.message(Command("gloan"))
async def gloan(m:Message):
    try:
        amt = int(m.text.split()[1])
    except:
        return await m.reply("Usage: /gloan [مقدار]\nمثال: /gloan 50")
    if amt < 1 or amt > 100:
        return await m.reply("❌ حداکثر وام از بازی 100 سانته!")
    user(m.from_user.id, m.from_user.full_name)
    existing = c.execute("SELECT amount, due_time FROM game_loans WHERE user_id=?", (m.from_user.id,)).fetchone()
    if existing:
        due = existing[1]
        rem = (due - int(time.time())) // 3600
        return await m.reply(f"❌ قبلاً {existing[0]} سانت وام داری!\n⏳ {rem} ساعت تا موعد پرداخت")
    due_time = int(time.time()) + 24*60*60
    c.execute("INSERT OR REPLACE INTO game_loans(user_id, amount, due_time) VALUES(?,?,?)", (m.from_user.id, amt, due_time))
    c.execute("UPDATE users SET size=size+? WHERE user_id=?", (amt, m.from_user.id))
    db.commit()
    await m.reply(
        f"💰 وام از بازی\n\n"
        f"💵 مقدار: {amt} سانت\n"
        f"⏳ مهلت پرداخت: ۲۴ ساعت\n\n"
        f"برای پرداخت: /gpay {amt}"
    )

@dp.message(Command("gpay"))
async def gpay(m:Message):
    user(m.from_user.id, m.from_user.full_name)
    loan = c.execute("SELECT amount, due_time FROM game_loans WHERE user_id=?", (m.from_user.id,)).fetchone()
    if not loan:
        return await m.reply("❌ وامی نداری!")
    amt, due_time = loan
    size = c.execute("SELECT size FROM users WHERE user_id=?", (m.from_user.id,)).fetchone()[0]
    if size < amt:
        return await m.reply(f"❌ سانت کافی نداری! باید {amt} سانت داشته باشی.")
    c.execute("UPDATE users SET size=size-? WHERE user_id=?", (amt, m.from_user.id))
    c.execute("DELETE FROM game_loans WHERE user_id=?", (m.from_user.id,))
    db.commit()
    await m.reply(f"✅ وام {amt} سانت پرداخت شد!")

async def check_loans(bot):
    while True:
        await asyncio.sleep(60)
        now = int(time.time())
        overdue = c.execute("SELECT user_id, amount FROM game_loans WHERE due_time<?", (now,)).fetchall()
        for uid, amt in overdue:
            size = c.execute("SELECT size FROM users WHERE user_id=?", (uid,)).fetchone()
            if not size:
                continue
            size = size[0]
            paid = 0
            msg = f"⚠️ وام {amt} سانت موعدش گذشت!\n\n"
            # sell celebs to cover debt
            if size < amt:
                celebs = c.execute("SELECT celeb, paid_price FROM collections WHERE user_id=? ORDER BY paid_price DESC", (uid,)).fetchall()
                for celeb, paid_price in celebs:
                    if paid >= amt:
                        break
                    c.execute("DELETE FROM collections WHERE user_id=? AND celeb=?", (uid, celeb))
                    c.execute("UPDATE users SET size=size+? WHERE user_id=?", (paid_price, uid))
                    paid += paid_price
                    msg += f"💸 {celeb} فروخته شد (+{paid_price} سانت)\n"
                db.commit()
                size = c.execute("SELECT size FROM users WHERE user_id=?", (uid,)).fetchone()[0]
            # deduct what we can
            deduct = min(amt, size)
            c.execute("UPDATE users SET size=size-? WHERE user_id=?", (deduct, uid))
            remaining = amt - deduct
            if remaining > 0:
                c.execute("UPDATE users SET size=size-? WHERE user_id=?", (remaining, uid))
                msg += f"📉 {remaining} سانت بدهی — حساب منفی شد!"
            else:
                msg += f"✅ {amt} سانت کسر شد."
            c.execute("DELETE FROM game_loans WHERE user_id=?", (uid,))
            db.commit()
            try:
                await bot.send_message(uid, msg)
            except:
                pass

@dp.message(Command("addcm"))
async def addcm(m:Message):
    if m.from_user.id != ADMIN_ID:
        return await m.reply("❌ دسترسی ندارید!")
    try:
        parts = m.text.split()
        amount = int(parts[1])
    except:
        return await m.reply("Usage: /addcm [amount] (reply to a user)")
    if not m.reply_to_message:
        return await m.reply("Reply to a user to add cm.")
    target = m.reply_to_message.from_user.id
    user(target, m.reply_to_message.from_user.full_name)
    c.execute("UPDATE users SET size=size+? WHERE user_id=?", (amount, target))
    db.commit()
    new_size = c.execute("SELECT size FROM users WHERE user_id=?", (target,)).fetchone()[0]
    await m.reply(f"✅ {amount} سانت به {m.reply_to_message.from_user.full_name} اضافه شد!\n📏 اندازه جدید: {new_size} سانت")


@dp.message(Command("addcb"))
async def addcb(m:Message):
    if m.from_user.id != ADMIN_ID:
        return await m.reply("❌ دسترسی ندارید!")
    name = m.text.replace("/addcb","",1).strip()
    if not name:
        return await m.reply("Usage: /addcb [نام سلبریتی] (reply to a user)\nمثال: /addcb Dua Lipa")
    if name not in CELEBS:
        return await m.reply("❌ سلبریتی پیدا نشد.")
    if not m.reply_to_message:
        return await m.reply("Reply to a user to give the celeb.")
    target = m.reply_to_message.from_user.id
    user(target, m.reply_to_message.from_user.full_name)
    already = c.execute("SELECT 1 FROM collections WHERE user_id=? AND celeb=?", (target, name)).fetchone()
    if already:
        return await m.reply(f"❌ {m.reply_to_message.from_user.full_name} این سلبریتی رو داره!")
    tier, price, spin, photo = CELEBS[name]
    c.execute("INSERT INTO collections(user_id,celeb,paid_price,locked) VALUES(?,?,?,0)", (target, name, price))
    db.commit()
    await m.reply(f"✅ {name} به {m.reply_to_message.from_user.full_name} داده شد!\n👑 Tier {tier}")

async def main():
    bot=Bot(TOKEN)
    from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeDefault
    commands = [
        BotCommand(command="grow", description="🌱 رشد کن"),
        BotCommand(command="size", description="📊 اندازه و پروفایل"),
        BotCommand(command="top", description="🏆 جدول بزرگان"),
        BotCommand(command="market", description="🛒 بازار سلبریتی"),
        BotCommand(command="collection", description="📚 کالکشن من"),
        BotCommand(command="spin", description="🎰 اسپین سلبریتی"),
        BotCommand(command="buy", description="🛍 خرید سلبریتی"),
        BotCommand(command="sell", description="💸 فروش سلبریتی"),
        BotCommand(command="list", description="🏪 فروش به دیگران"),
        BotCommand(command="pvp", description="⚔️ دوئل"),
        BotCommand(command="mafia", description="🔫 جنگ مافیا تیمی"),
        BotCommand(command="mafia2", description="🔫 مافیا (فاش‌شدن تیم‌ها در پایان)"),
        BotCommand(command="loan", description="💰 وام دادن"),
        BotCommand(command="repay", description="✅ پرداخت بدهی"),
        BotCommand(command="collectors", description="🏆 بهترین کلکسیونرها"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    await bot.set_my_commands(commands, scope=BotCommandScopeAllGroupChats())
    asyncio.create_task(check_loans(bot))
    await dp.start_polling(bot)

if __name__=="__main__":
    import asyncio
    asyncio.run(main())
