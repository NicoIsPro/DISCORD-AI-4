import asyncio
import os
from pathlib import Path

import discord
from discord.ext import commands
from fastapi import FastAPI
from dotenv import load_dotenv

from ai_engine import generate_reply, engine_status
from memory_store import MemoryStore, should_warn_language, infer_real_name_hint

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
PREFIX = os.getenv("PREFIX", "!").strip() or "!"
ALLOW_DMS = os.getenv("ALLOW_DMS", "true").lower() == "true"
AUTO_REPLY_ALL_CHANNELS = os.getenv("AUTO_REPLY_ALL_CHANNELS", "false").lower() == "true"

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.dm_messages = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)
app = FastAPI(title="Discord AI Bot", version="3.1")

memory = MemoryStore(Path("memory.json"))
synced = False


def strip_bot_mention(bot_user: discord.ClientUser | None, text: str) -> str:
    if not bot_user:
        return text
    return (
        text.replace(f"<@{bot_user.id}>", "")
        .replace(f"<@!{bot_user.id}>", "")
        .strip()
    )


async def maybe_warn(message: discord.Message, text: str) -> bool:
    """
    Returns True if a warning was sent and the message should not be answered normally.
    """
    warning = should_warn_language(text)
    if warning:
        await message.reply(warning, mention_author=False)
        return True
    return False


async def ai_answer(message: discord.Message, user_text: str):
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

    reply = await asyncio.to_thread(generate_reply, prompt, display_name)
    reply = memory.clean_reply(reply)

    if not reply:
        reply = "Putz, travei aqui 😅"

    memory.update_from_turn(
        guild_id=guild_id,
        user_id=user_id,
        user_text=user_text,
        bot_text=reply,
        display_name=display_name,
    )

    memory.save()

    allowed = discord.AllowedMentions(
        everyone=False,
        roles=False,
        users=True,
        replied_user=False,
    )
    await message.reply(reply, mention_author=False, allowed_mentions=allowed)


@bot.event
async def on_ready():
    global synced
    if not synced:
        try:
            await bot.tree.sync()
        except Exception as exc:
            print(f"Falha ao sincronizar comandos: {exc}")
        synced = True

    print(f"Logado como {bot.user} | {engine_status()}")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    is_dm = isinstance(message.channel, discord.DMChannel)
    mentioned = bot.user in message.mentions if bot.user else False
    content = message.content.strip()

    if is_dm and not ALLOW_DMS:
        return

    if AUTO_REPLY_ALL_CHANNELS and content:
        if await maybe_warn(message, content):
            return
        await ai_answer(message, content)
        return

    if is_dm or mentioned:
        if mentioned:
            content = strip_bot_mention(bot.user, content)
        if content:
            if await maybe_warn(message, content):
                return
            await ai_answer(message, content)

    await bot.process_commands(message)


@bot.command(name="ping")
async def ping(ctx: commands.Context):
    await ctx.reply("pong 🟢", mention_author=False)


@bot.tree.command(name="ai", description="Conversa com a IA.")
async def ai(interaction: discord.Interaction, prompt: str):
    if should_warn_language(prompt):
        await interaction.response.send_message("Vou ficar de boa nessa aqui 😅", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)

    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id) if interaction.guild else "dm"
    display_name = interaction.user.display_name
    name_hint = infer_real_name_hint(display_name)
    profile = memory.get_profile(guild_id, user_id)

    prompt_full = memory.build_prompt(
        user_name=display_name,
        user_text=prompt,
        profile=profile,
        guild_id=guild_id,
        name_hint=name_hint,
    )

    reply = await asyncio.to_thread(generate_reply, prompt_full, display_name)
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


@bot.tree.command(name="profile", description="Mostra o resumo salvo sobre você.")
async def profile(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id) if interaction.guild else "dm"
    user_id = str(interaction.user.id)
    profile = memory.get_profile(guild_id, user_id)
    if not profile:
        await interaction.response.send_message("Ainda não tenho nada salvo sobre você.", ephemeral=True)
        return
    await interaction.response.send_message(f"Resumo salvo: `{profile}`", ephemeral=True)


@bot.tree.command(name="join", description="Entra no canal de voz onde você está.")
async def join(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("Esse comando só funciona em servidor.", ephemeral=True)
        return

    member = interaction.user
    assert isinstance(member, discord.Member)

    if not member.voice or not member.voice.channel:
        await interaction.response.send_message("Entra em um canal de voz primeiro.", ephemeral=True)
        return

    channel = member.voice.channel
    if interaction.guild.voice_client and interaction.guild.voice_client.is_connected():
        await interaction.guild.voice_client.move_to(channel)
    else:
        await channel.connect()

    await interaction.response.send_message(f"Entrei em {channel.mention}.")


@bot.tree.command(name="leave", description="Sai do canal de voz.")
async def leave(interaction: discord.Interaction):
    if not interaction.guild or not interaction.guild.voice_client or not interaction.guild.voice_client.is_connected():
        await interaction.response.send_message("Não estou em canal de voz.", ephemeral=True)
        return

    await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("Saí do canal de voz.")


@bot.tree.command(name="say", description="Fala um texto no canal de voz.")
async def say(interaction: discord.Interaction, text: str):
    if not interaction.guild:
        await interaction.response.send_message("Esse comando só funciona em servidor.", ephemeral=True)
        return

    member = interaction.user
    assert isinstance(member, discord.Member)

    if not member.voice or not member.voice.channel:
        await interaction.response.send_message("Entra em um canal de voz primeiro.", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)

    vc = interaction.guild.voice_client
    if not vc or not vc.is_connected():
        vc = await member.voice.channel.connect()

    from gtts import gTTS
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="tts_"))
    mp3_path = tmp / "tts.mp3"

    try:
        tts = gTTS(text=text, lang="pt-br")
        tts.save(str(mp3_path))
        if vc.is_playing():
            vc.stop()
        source = discord.FFmpegPCMAudio(str(mp3_path))
        vc.play(source)
        while vc.is_playing():
            await asyncio.sleep(0.5)
    finally:
        try:
            if mp3_path.exists():
                mp3_path.unlink()
            tmp.rmdir()
        except Exception:
            pass

    await interaction.followup.send("Pronto.")


@app.get("/")
async def health():
    return {"ok": True, "bot": str(bot.user) if bot.user else None}


@app.on_event("startup")
async def startup():
    if not DISCORD_TOKEN:
        print("DISCORD_TOKEN não definido.")
        return
    asyncio.create_task(bot.start(DISCORD_TOKEN))


@app.on_event("shutdown")
async def shutdown():
    if bot.is_ready():
        await bot.close()
