import os
import asyncio
from yt_dlp import YoutubeDL
from dotenv import load_dotenv
import discord
from discord.ext import commands

import wavelink

# -------------------------
#      기본환경
# -------------------------

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

@bot.event
async def on_ready():
    print("봇 로그인 완료")

    node = wavelink.Node(
        uri="http://localhost:2333",
        password="youshallnotpass"
    )

    await wavelink.Pool.connect(
        client=bot,
        nodes=[node]
    )

    print("✅ Lavalink WebSocket 연결 성공")

# 입장 테스트
@bot.command()
async def join(ctx):
    # 1. 사용자가 음성 채널에 있는지 확인
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("먼저 음성 채널에 들어가 주세요.")
        return

    channel = ctx.author.voice.channel

    # 2. 이미 Player가 있는지 확인
    player: wavelink.Player = ctx.guild.voice_client

    if player is None:
        # 3. Player 생성 + 음성 채널 연결
        player = await channel.connect(cls=wavelink.Player)
        await ctx.send(f"🔊 음성 채널 입장: {channel.name}")
    else:
        await ctx.send("이미 음성 채널에 있습니다.")

# 쿼리 테스트
@bot.command()
async def load(ctx, *, query: str):
    player: wavelink.Player = ctx.guild.voice_client

    if not player:
        await ctx.send("먼저 !join 으로 음성 채널에 들어와 주세요.")
        return

    tracks = await wavelink.Playable.search(query, source="ytsearch")

    if not tracks:
        await ctx.send("트랙을 찾지 못했습니다.")
        return

    track = tracks[0]
    await ctx.send(f"✅ 트랙 로드 성공: {track.title}")

@bot.command()
async def play(ctx, *, query: str):
    # 1. 유저가 음성 채널에 있는지 확인
    if not ctx.author.voice:
        await ctx.send("먼저 음성 채널에 들어가 주세요.")
        return

    # 2. 음성 채널 연결
    if not ctx.voice_client:
        player: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
    else:
        player: wavelink.Player = ctx.voice_client

    # 3. 트랙 검색 (ytsearch)
    tracks = await wavelink.Playable.search(query, source="ytsearch")

    if not tracks:
        await ctx.send("검색 결과가 없습니다.")
        return

    track = tracks[0]

    # 4. 재생
    await player.play(track)

    await ctx.send(f"🎶 재생 시작: **{track.title}**")


bot.run(TOKEN)
