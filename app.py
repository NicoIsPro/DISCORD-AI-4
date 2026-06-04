import asyncio
import os
import logging
from pathlib import Path

import discord
from discord.ext import commands
from fastapi import FastAPI
from dotenv import load_dotenv

from ai_engine import generate_reply, engine_status
from memory_store import MemoryStore, should_warn_language, infer_real_name_hint

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
PREFIX = os.getenv("PREFIX", "!").strip() or "!"
ALLOW_DMS = os.getenv("ALLOW_DMS", "true").lower() == "true"
AUTO_REPLY_ALL_CHANNELS = os.getenv("AUTO_REPLY_ALL_CHANNELS", "false").lower() == "true"

# -------------------------
# DISCORD SETUP
# -------------------------

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.dm_messages = True
intents.members = True

allowed_mentions = discord.AllowedMentions(
    everyone=False,
    roles=False,
    users=True,
    replied_user=False,
)

bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents,
    allowed_mentions=allowed_mentions
)

# -------------------------
# FASTAPI
# -------------------------

app = FastAPI(title="Discord AI Bot", version="3.1")

memory = MemoryStore(Path("memory.json"))
synced = False


# -------------------------
# UTILS
# -------------------------

def strip_mention(bot_user, text: str) -> str:
    if not bot_user:
        return text
    return (
        text.replace(f"<@{bot_user.id}>", "")
        .replace(f"<@!{bot_user.id}>", "")
        .strip()
    )


async def warn_if_needed(message: discord.Message, text: str) -> bool:
    try:
        warning = should_warn_language(text)
        if warning:
            await message.reply(warning, mention_author=False)
            return True
    except Exception:
        logger.exception("Erro no warn_if_needed")
    return False


async def send_ai_reply(message: discord.Message, user_text: str):
    try:
        user_id = str(message.author.id)
        guild_id = str(message.guild.id) if message.guild else "dm"
        display_name = message.author.display_name
        name_hint = infer_real_name_hint(display_name)

        profile = memory.get_profile(guild_id, user_id)

        prompt = memory.build_prompt(
            user_name=display_name,
            user_text=user_text,
            profile=profile,
            guild_id=guild_id,
            name_hint=name_hint,
        )

        reply = await asyncio.to_thread(
            generate_reply,
            prompt,
            display_name
        )

        reply = memory.clean_reply(reply) or "Putz, travei aqui 😅"

        memory.update_from_turn(
            guild_id=guild_id,
            user_id=user_id,
            user_text=user_text,
            bot_text=reply,
            display_name=display_name,
        )
        memory.save()

        await message.reply(
            reply,
            mention_author=False,
            allowed_mentions=allowed_mentions
        )

    except Exception:
        logger.exception("Erro ao gerar resposta IA")
        await message.reply("deu ruim aqui 😅 tenta dnv", mention_author=False)


# -------------------------
# EVENTS
# -------------------------

@bot.event
async def on_ready():
    global synced

    if not synced:
        try:
            await bot.tree.sync()
            logger.info("Slash commands sincronizados.")
        except Exception:
            logger.exception("Erro ao sync slash commands")
        synced = True

    logger.info(f"Bot online: {bot.user} | {engine_status()}")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    is_dm = isinstance(message.channel, discord.DMChannel)
    content = (message.content or "").strip()

    if is_dm and not ALLOW_DMS:
        return

    mentioned = bot.user in message.mentions if bot.user else False
    is_command = content.startswith(PREFIX)

    # sempre deixa comandos funcionarem
    if is_command:
        await bot.process_commands(message)
        return

    # auto reply geral
    if AUTO_REPLY_ALL_CHANNELS and content:
        if await warn_if_needed(message, content):
            return
        await send_ai_reply(message, content)
        return

    # DM ou mention
    if is_dm or mentioned:
        if mentioned:
            content = strip_mention(bot.user, content)

        if content:
            if await warn_if_needed(message, content):
                return
            await send_ai_reply(message, content)

    await bot.process_commands(message)


# -------------------------
# COMMANDS
# -------------------------

@bot.command(name="ping")
async def ping(ctx):
    await ctx.reply("pong 🟢", mention_author=False)


@bot.tree.command(name="ai", description="Conversa com a IA")
async def ai(interaction: discord.Interaction, prompt: str):
    if should_warn_language(prompt):
        await interaction.response.send_message("vou deixar quieto essa 😅", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)

    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id) if interaction.guild else "dm"
    display_name = interaction.user.display_name
    name_hint = infer_real_name_hint(display_name)

    profile = memory.get_profile(guild_id, user_id)

    full_prompt = memory.build_prompt(
        user_name=display_name,
        user_text=prompt,
        profile=profile,
        guild_id=guild_id,
        name_hint=name_hint,
    )

    reply = await asyncio.to_thread(
        generate_reply,
        full_prompt,
        display_name
    )

    reply = memory.clean_reply(reply) or "Putz, travei aqui 😅"

    memory.update_from_turn(
        guild_id=guild_id,
        user_id=user_id,
        user_text=prompt,
        bot_text=reply,
        display_name=display_name,
    )
    memory.save()

    await interaction.followup.send(reply)


# -------------------------
# FASTAPI ROUTE
# -------------------------

@app.get("/")
async def home():
    return {
        "ok": True,
        "bot": str(bot.user) if bot.user else None,
        "engine": engine_status()
    }


# -------------------------
# STARTUP FIX (IMPORTANTE)
# -------------------------

@app.on_event("startup")
async def startup():
    if not DISCORD_TOKEN:
        logger.warning("DISCORD_TOKEN não definido")
        return

    logger.info("Iniciando bot Discord...")

    loop = asyncio.get_event_loop()
    loop.create_task(bot.start(DISCORD_TOKEN))

    logger.info("Bot rodando em background.")


@app.on_event("shutdown")
async def shutdown():
    try:
        await bot.close()
    except Exception:
        logger.exception("Erro ao encerrar bot")
