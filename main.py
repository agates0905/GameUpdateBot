
import requests
import asyncio
import discord
import os
import sqlite3

# initial discord bot setup
intents = discord.Intents.default()
client = discord.Client(intents=intents)

# API keys/tokens
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
STEAM_API_KEY = os.getenv('STEAM_API_KEY')

# Database Setup
conn = sqlite3.connect('database.db')
c = conn.cursor()

# CReating tables if they do not exist
c.execute("CREATE TABLE IF NOT EXISTS games (appid INTEGER, last_update INTEGER)")
c.execute("CREATE TABLE IF NOT EXISTS settings (guild_id INTEGER, channel_id INTEGER, PRIMARY KEY (guild_id))")
conn.commit()


# add game to databse
def add_game(appid):
    c.execute("INSERT INTO games (appid, last_update) VALUES (?, ?)", (appid, 0))
    conn.commit()


# check steam api for game updates
def check_game_updates(appid):
    url = f"https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid={appid}&count=1&maxlength=300&format=json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        news = response.json()

        if news and news['appnews']['newsitems']:
            latest_news = news['appnews']['newsitems'][0]
            news_time = latest_news['date']
            c.execute("UPDATE games SET last_update = ? WHERE appid = ?", (news_time, appid))
            row = c.fetchone()
            if row and row[0] < news_time:
                c.execute("UPDATE games SET last_update = ? WHERE appid = ?", (news_time, appid))
                conn.commit()
                return latest_news['title'], latest_news['url']
        return None, None
    except requests.exceptions.HTTPError as http_error:
        print(f"HTTP error occurred: {http_error}")
        return None, None
    except requests.exceptions.RequestException as request_error:
        print(f"Request error occurred: {request_error}")


# add selected discord channel to database
def set_channel(guild_id, channel_id):
    c.execute("INSERT OR REPLACE INTO settings (guild_id, channel_id) VALUES (?, ?)", (guild_id, channel_id))
    conn.commit()


# Retrieve the channelid of the guild
def get_channel(guild_id):
    c.execute("SELECT channel_id FROM settings WHERE guild_id = ?", (guild_id,))
    row = c.fetchone()
    if row:
        return row[0]
    else:
        return None

# check the list of games for each server and check if they have received any updates
async def get_games():
    await client.wait_until_ready()
    while not client.is_closed:
        c.execute("SELECT guild_id, channel_id FROM settings")
        settings = c.fetchall()

        for guild_id, channel_id in settings:
            c.execute("SELECT appid FROM games")
            games = c.fetchall()
            for game in games:
                appid = game[0]
                title, url = check_game_updates(appid)
                if title and url:
                    channel = client.get_channel(channel_id)
                    if channel:
                        await channel.send(f"New update for game {title}: {url}")
        await asyncio.sleep(3600)


@client.event
async def on_ready():
    print(f"Logged in as {client.user}")


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith("!addgame"):
        try:
            appid = int(message.content.split()[1])
            add_game(appid)
            await message.channel.send(f"New game added: {appid}")
        except (ValueError, TypeError, IndexError):
            await message.channel.send("Usage: !addgame <appid>")
    elif message.content.startswith("!setchannel"):
        set_channel(message.guild.id, message.channel.id)
        await message.channel.send(f"Channel set to {message.guild.id}")


async def main():
    async with client:
        await client.start(DISCORD_TOKEN)

# Run the bot with asyncio
asyncio.run(main())
