import discord
import pickle
import asyncio
from discord.ext import commands
import csv
import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

if TOKEN is None:
    print("Error: Bot token not found. Please set the DISCORD_BOT_TOKEN in the .env file.")
    exit()

svc_model = pickle.load(open("models/svc_model.pkl", "rb"))
vectorizer = pickle.load(open("models/tfidf_vectorizer.pkl", "rb"))

def load_sus_words(filename="data/sus_words.csv"):
    sus_words = set()
    with open(filename, mode='r', encoding='utf-8') as file:
        csv_reader = csv.reader(file)
        for row in csv_reader:
            sus_words.add(row[0].strip().lower())
    return sus_words

sus_words = load_sus_words()

conn = sqlite3.connect("discord_bully.db")
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS user_data (
                    username TEXT PRIMARY KEY,
                    count INTEGER DEFAULT 0,
                    flag INTEGER DEFAULT 0
                )''')
conn.commit()

def update_user_data(username, guild, member):
    cursor.execute("SELECT count, flag FROM user_data WHERE username = ?", (username,))
    row = cursor.fetchone()

    if row is None:

        cursor.execute("INSERT INTO user_data (username, count, flag) VALUES (?, 1, 0)", (username,))
    else:
        count, flag = row
        count += 1
        
        if count > 10 and flag == 0:
            flag = 1

        if count > 20 and flag == 1:
            asyncio.create_task(kick_user(guild, member))
                    
        cursor.execute("UPDATE user_data SET count = ?, flag = ? WHERE username = ?", (count, flag, username))

    conn.commit()

async def kick_user(guild, member):
    try:
        
        await member.kick(reason="Exceeded cyberbullying limit.")
        print(f"{member} has been kicked for excessive bullying.")
    except Exception as e:
        print(f"Failed to kick {member}: {e}")
        
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

def analyze_text(text):
    words = set(text.lower().split())
    if words & sus_words:
        return "🚨 Cyberbullying detected (Suspicious Words Match)"
    
    text_tfidf = vectorizer.transform([text]).toarray()
    prediction = svc_model.predict(text_tfidf)[0]
    
    return "🚨 Cyberbullying detected" if prediction == 1 else "✅ Safe Message"

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    result = analyze_text(message.content)
    if "🚨" in result:
        username = str(message.author)
        guild = message.guild
        member = message.author

        update_user_data(username, guild, member)
        
        await message.channel.send(f"{message.author.mention} {result}")
    
    await bot.process_commands(message)

@bot.command(name="check_user")
@commands.has_permissions(administrator=True)
async def check_user(ctx, username: str):
    cursor.execute("SELECT count, flag FROM user_data WHERE username = ?", (username,))
    row = cursor.fetchone()

    if row:
        count, flag = row
        await ctx.send(f"User: {username} | Count: {count} | Flag: {flag}")
    else:
        await ctx.send(f"No data found for user: {username}")

@check_user.error
async def check_user_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Please provide a username.")
    else:
        await ctx.send("An error occurred while processing the request.")

bot.run(TOKEN)