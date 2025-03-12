import asyncio
import discord
import requests
import sqlite3

from discord import TextChannel

class Client(discord.Client):
    def __init__(self) -> None:
        # init discord bot
        super().__init__(intents=discord.Intents.all(), prefix="!")

        # create db conn & cursor
        self.conn : sqlite3.Connection = sqlite3.connect("bot.db")
        self.cursor : sqlite3.Cursor = self.conn.cursor()

        # create table if doesn't exit
        self.cursor.execute("CREATE TABLE IF NOT EXISTS sales (id TEXT PRIMARY KEY, title TEXT)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS channels (server_id INTEGER PRIMARY KEY, channel_id INTEGER)")

    async def on_ready(self) -> None:
        print(f'Logged on as {self.user}!')
        await self.change_presence(status=discord.Status.idle, activity=discord.Game('Watching for sales!')) # create status
        asyncio.create_task(self.hourly_update()) # create hourly sale update

    async def on_guild_join(self, guild : discord.Guild) -> int:
        channel_id = -1 # channel id (stays -1 if not found)

        # check if sales channel exists
        for channel in guild.text_channels:
            # channel exists
            if channel.name == 'sales' and channel.permissions_for(guild.me).send_messages:
                await channel.send('Welcome! BAPCS bot will send all sales here.')  # send welcome message
                channel_id = channel.id

        # create new channel if doesnt exist
        if channel_id == -1:
            # else, create sales channel and send creation message
            bapcs_channel : TextChannel = await guild.create_text_channel('sales')
            await bapcs_channel.send("Welcome! We've created a new channel for all sales to be sent to.")
            channel_id = bapcs_channel.id

        # insert new record if server_id doesn't exist, else update it
        self.cursor.execute('INSERT OR REPLACE INTO channels (server_id, channel_id) VALUES (?,?)', (guild.id, channel_id))
        self.conn.commit()

        return channel_id

    async def send_message(self, message : str, channel_id : int) -> None:
        """Sends a message to the specified channel"""
        channel = await self.fetch_channel(channel_id)
        await channel.send(message)

    async def hourly_update(self) -> None:
        """Checks for new posts hourly and pushes them to all the guilds"""
        while True:
            request = requests.get('https://www.reddit.com/r/buildapcsales/new.json?limit=5')
            # ensure request was successful
            if request.status_code == 200:
                print('successfully fetched posts')
                data = request.json()
                data = data['data']['children'] # data to parse
                feed_data = "" # stores new feed data

                # parse through each post
                for i in range(len(data)):
                    post_data = data[i]['data'] # grab post
                    result = self.cursor.execute("SELECT id FROM sales WHERE id=?", (str(post_data['id']),)).fetchone() # get record for post

                    # ensure post record does not exist already
                    if result is None:
                        self.cursor.execute("INSERT INTO sales (id, title) VALUES (?, ?)", (str(post_data['id']), post_data['title'])) # add post record
                        feed_data += f"{post_data['title']}, <https://redd.it/{post_data['id']}>\n\n"

                self.conn.commit() # commit inserts

                # if new feed data, send to all servers
                if feed_data != "":
                    for guild in self.guilds:
                        # find channel id for guild
                        channel_id = self.cursor.execute("SELECT channel_id FROM channels WHERE server_id=?", (guild.id,)).fetchone()
                        # create a guild channel if doesn't exist yet and place it in the db
                        if channel_id is None:
                            channel_id = await self.on_guild_join(guild)

                        await self.send_message(feed_data, channel_id) # send message

                await asyncio.sleep(3600) # wait an hour

            # else, error (likely rate-limited)
            else:
                print('error fetching posts')