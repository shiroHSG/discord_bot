import os
from dotenv import load_dotenv
import discord
from discord.ext import commands

# .env 파일 불러오기
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"로그인 성공: {bot.user}")

@bot.command()
async def hello(ctx):
    await ctx.send("Hello!")

# bot.command(aliases=['입장']) -> as 적용 가능
@bot.command()
async def join(ctx):
    """명령어를 보낸 사용자의 음성 채널로 봇이 들어오거나 이동합니다"""
    # 사용자가 음성 채널에 있는지 확인
    if not ctx.author.voice:
        await ctx.send("먼저 음성 채널에 들어가 주세요")
        return

    # 사용자가 있는 음성 채널
    channel = ctx.author.voice.channel

    # 봇이 이미 연결돼 있는 경우
    if ctx.voice_client:
        # 만약 현재 연결된 채널과 다르다면 이동
        if ctx.voice_client.channel != channel:
            await ctx.voice_client.move_to(channel)
            await ctx.send(f"{channel.name} 채널로 이동했습니다")
        else:
            await ctx.send(f"이미 {channel.name} 채널에 연결되어 있습니다")
    else:
        # 처음 연결하는 경우
        await channel.connect()
        await ctx.send(f"{channel.name} 채널에 접속했습니다")


@bot.command()
async def leave(ctx):
    """봇이 현재 들어가 있는 음성 채널에서 나옵니다."""
    if ctx.voice_client:  # 봇이 현재 연결되어 있는지 확인
        await ctx.voice_client.disconnect()
        await ctx.send("음성 채널에서 나갔어요")
    else:
        await ctx.send("현재 어떤 음성 채널에도 들어가 있지 않아요")

bot.run(TOKEN)