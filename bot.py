import discord
from discord.ext import commands
import sqlite3
import os
import random
import time
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Инициализируем сразу при создании бота — не зависит от on_ready
bot.cooldowns = {}

db_name = "xp.db"
conn = sqlite3.connect(db_name, check_same_thread=False)
c = conn.cursor()

# Тут свою роль
buy_role = 'новая роль'

def init_db():
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        xp INTEGER DEFAULT 0,
        last_daily INTEGER DEFAULT 0,
        coins INTEGER DEFAULT 0
    )
    """)
    conn.commit()

init_db()

@bot.event
async def on_ready():
    print(f"Бот запущен как {bot.user}")

# Опыт при сообщениях
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user = message.author

    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user.id,))
    conn.commit()

    c.execute("SELECT xp FROM users WHERE user_id = ?", (user.id,))
    row = c.fetchone()
    xp = row[0]

    now = int(time.time())
    cooldown = 30

    guild_id = message.guild.id if message.guild else 0
    key = (guild_id, user.id)

    # Чистим устаревшие записи кулдауна (старше 60 секунд)
    expired = [k for k, v in bot.cooldowns.items() if now - v > 60]
    for k in expired:
        del bot.cooldowns[k]

    if key not in bot.cooldowns or now - bot.cooldowns[key] > cooldown:
        bot.cooldowns[key] = now
        xp_gain = random.randint(5, 15)
        xp += xp_gain
        c.execute("UPDATE users SET xp = ? WHERE user_id = ?", (xp, user.id))
        conn.commit()

    await bot.process_commands(message)

# Собрать ежедневную награду
@bot.command()
async def daily(ctx):
    user_id = ctx.author.id

    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()

    c.execute("SELECT coins, last_daily FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    coins, last_daily = row

    now = int(time.time())
    cooldown = 86400

    if now - last_daily >= cooldown:
        coins += 100
        c.execute("UPDATE users SET coins = ?, last_daily = ? WHERE user_id = ?", (coins, now, user_id))
        conn.commit()
        await ctx.send(f"Ты получил 100 монет! Всего: {coins}")
    else:
        remaining = cooldown - (now - last_daily)
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        await ctx.send(f"Ещё {hours}ч {minutes}м до следующей награды.")

# Купить роль
@bot.command()
async def buy(ctx):
    user_id = ctx.author.id
    cost = 50

    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()

    c.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    coins = row[0]

    role = discord.utils.get(ctx.guild.roles, name=buy_role)

    if not role:
        await ctx.send("Такой роли нет на сервере!")
        return

    # Проверяем, нет ли уже этой роли у пользователя
    if role in ctx.author.roles:
        await ctx.send(f"У тебя уже есть роль **{buy_role}**!")
        return

    if coins >= cost:
        try:
            await ctx.author.add_roles(role)
            coins -= cost
            c.execute("UPDATE users SET coins = ? WHERE user_id = ?", (coins, user_id))
            conn.commit()
            await ctx.send(f"Роль **{buy_role}** куплена за {cost} монет! Осталось {coins} монет.")
        except discord.Forbidden:
            await ctx.send("У бота нет прав для выдачи этой роли. Обратитесь к администратору.")
    else:
        remaining = cost - coins
        await ctx.send(f"Не хватает {remaining} монет!")

bot.run(token)
