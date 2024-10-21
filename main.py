import requests
import asyncio
import discord
import os
import sqlite3

# Initial Discord bot setup
intents = discord.Intents.default()
intents.message_content = True  # Ensure message content intent is enabled
client = discord.Client(intents=intents)

# API keys/tokens
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
STEAM_API_KEY = os.getenv('STEAM_API_KEY')

# Database Setup
conn = sqlite3.connect('database.db')
c = conn.cursor()

# Creating tables if they do not exist
c.execute("CREATE TABLE IF NOT EXISTS games (appid INTEGER, guild_id INTEGER, last_update INTEGER)")
c.execute("CREATE TABLE IF NOT EXISTS settings (guild_id INTEGER, channel_id INTEGER, PRIMARY KEY (guild_id))")
conn.commit()


# Add game to database
def add_game(appid, guild_id):
    title, url = check_game_updates(appid, guild_id)  # Pass guild_id to the function
    print(f"Adding game with appid: {appid}, Title: {title}, URL: {url}")  # Debug output
    c.execute("INSERT OR IGNORE INTO games (appid, guild_id, last_update) VALUES (?, ?, ?)", (appid, guild_id, 0))
    conn.commit()

    if title and url:
        print(f"Latest update for game {appid}: {title} - {url}")
        return title, url
    else:
        print(f"No news available for game {appid} at this moment.")
        return None, None


# Check Steam API for game updates
def check_game_updates(appid, guild_id):  # Accept guild_id as a parameter
    url = f"https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid={appid}&count=1&maxlength=300&format=json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        print(f"Response status code: {response.status_code}")
        news = response.json()
        print("Raw response data:", news)  # Log raw response data

        if news and news['appnews']['newsitems']:
            latest_news = news['appnews']['newsitems'][0]
            news_time = latest_news['date']
            print(f"Latest news item: {latest_news}")  # Log the latest news item

            # Fetch the last_update for the specific game and guild
            c.execute("SELECT last_update FROM games WHERE appid = ? AND guild_id = ?", (appid, guild_id))
            row = c.fetchone()
            last_update = row[0] if row else None

            # Debugging: print last_update value
            print(f"Last update for appid {appid} in guild {guild_id}: {last_update}")

            # Compare last_update with news_time
            if last_update is None or last_update < news_time:
                # Update last_update and return news
                c.execute("UPDATE games SET last_update = ? WHERE appid = ? AND guild_id = ?",
                          (news_time, appid, guild_id))
                conn.commit()
                return latest_news['title'], latest_news['url']
            else:
                print(f"No new updates for appid {appid} in guild {guild_id}.")
        else:
            print("No news items found for this appid.")
        return None, None
    except requests.exceptions.HTTPError as http_error:
        print(f"HTTP error occurred: {http_error}")
        return None, None
    except requests.exceptions.RequestException as request_error:
        print(f"Request error occurred: {request_error}")
        return None, None


# Add selected Discord channel to the database
def set_channel(guild_id, channel_id):
    c.execute("INSERT OR REPLACE INTO settings (guild_id, channel_id) VALUES (?, ?)", (guild_id, channel_id))
    conn.commit()
    print(f"Channel set for guild {guild_id}: {channel_id}")  # Debug output


# Retrieve the channel ID of the guild
def get_channel(guild_id):
    c.execute("SELECT channel_id FROM settings WHERE guild_id = ?", (guild_id,))
    row = c.fetchone()
    if row:
        return row[0]
    else:
        return None


# Check the list of games for each server and check if they have received any updates
async def get_games():
    await client.wait_until_ready()
    while not client.is_closed():
        c.execute("SELECT guild_id, channel_id FROM settings")
        settings = c.fetchall()

        for guild_id, channel_id in settings:
            c.execute("SELECT appid FROM games WHERE guild_id = ?", (guild_id,))
            games = c.fetchall()
            for game in games:
                appid = game[0]
                title, url = check_game_updates(appid, guild_id)
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

    print(f"Received message: {message.content}")  # Log received messages

    if message.content.startswith("!addgame"):
        parts = message.content.split()
        print(f"Parts: {parts}")  # Log the parts for debugging

        if len(parts) < 2:
            await message.channel.send("Usage: !addgame <appid>")
            return

        try:
            appid = int(parts[1])  # Convert appid to integer
            title, url = add_game(appid, message.guild.id)  # Pass guild_id to add_game

            # Debugging output to check the return values
            print(f"add_game returned: Title: {title}, URL: {url}")

            if title and url:
                await message.channel.send(f"New game added: {appid}\nLatest update: {title} - {url}")
            else:
                await message.channel.send(f"New game added: {appid}, but no recent updates were found.")
        except ValueError:
            await message.channel.send("Please provide a valid app ID as a number.")
        except Exception as e:
            await message.channel.send(f"An error occurred: {str(e)}")

    elif message.content.startswith("!setchannel"):
        # Set the channel for updates
        set_channel(message.guild.id, message.channel.id)
        await message.channel.send(f"Channel set to {message.channel.name} in guild {message.guild.name}")
        print(f"Channel set to {message.channel.name} for guild {message.guild.id}")  # Debug output


# Start the bot
async def main():
    async with client:
        await client.start(DISCORD_TOKEN)


# Run the bot with asyncio
asyncio.run(main())
