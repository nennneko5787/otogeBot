import asyncio
import os
from contextlib import asynccontextmanager

import discord
import dotenv
from discord.ext import commands, tasks
from fastapi import FastAPI

from routes import userIcon, imageProxy
from services.database import Database

dotenv.load_dotenv()

discord.utils.setup_logging()

bot = commands.Bot("otogebot#", intents=discord.Intents.default())


@tasks.loop(seconds=20)
async def precenseLoop():
    appInfo = await bot.application_info()
    game = discord.Game(
        f"/help | {len(bot.guilds)} servers | {appInfo.approximate_user_install_count} users"
    )
    await bot.change_presence(status=discord.Status.online, activity=game)


@bot.event
async def on_ready():
    precenseLoop.start()


@bot.event
async def setup_hook():
    await bot.load_extension("cogs.maimai")
    await bot.load_extension("cogs.popn")
    await bot.load_extension("cogs.polaris")
    await bot.load_extension("cogs.nostalgia")
    await bot.tree.sync()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await Database.connect()
    asyncio.create_task(bot.start(os.getenv("discord")))
    yield
    async with asyncio.timeout(60):
        await Database.pool.close()


app = FastAPI(lifespan=lifespan)
app.include_router(userIcon.router)
app.include_router(imageProxy.router)
