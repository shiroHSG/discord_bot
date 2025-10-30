import os
from dotenv import load_dotenv
import discord
from discord.ext import commands

# .env 파일 불러오기
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.voice_states = True # 음성 상태 변경 감지
intents.message_content = True  # 채널에 입력된 메세지 감지
bot = commands.Bot(command_prefix="!", intents=intents)

#### 기본 event 처리
@bot.event
async def on_ready(): # 봇 실행시 호출
    print(f"로그인 성공: {bot.user}")

# @bot.event # 음성 상태 변경시 호출
# async def on_voice_state_update(member, before, after):
#     # 봇 자신은 무시
#     if member.bot:
#         return

#     # before.channel: 바뀌기 전 상태
#     # after.channel: 바뀐 후 상태
#     # -> 즉, before은 음성 채널을 '떠난' 경우에만 값이 있음
#     if before.channel is not None and after.channel != before.channel:
#         channel = before.channel
#         vc = discord.utils.get(bot.voice_clients, guild=member.guild)

#         if vc and vc.channel == channel:
#             # 사람(봇 제외) 수 세기
#             human_count = sum(1 for m in channel.members if not m.bot)
#             if human_count == 0:
#                 await vc.disconnect()
#                 print(f"{channel.name} 채널에 아무도 없어 자동 나가기")

#### 입력 커맨드 처리
# bot.command(aliases=['입장']) -> as 적용 가능
# @bot.command()
# async def join(ctx):
#     """명령어를 보낸 사용자의 음성 채널로 봇이 들어오거나 이동합니다"""
#     # 사용자가 음성 채널에 있는지 확인
#     if not ctx.author.voice:
#         await ctx.send("먼저 음성 채널에 들어가 주세요")
#         return

#     # 사용자가 있는 음성 채널
#     channel = ctx.author.voice.channel

#     # 봇이 이미 연결돼 있는 경우
#     if ctx.voice_client:
#         # 만약 현재 연결된 채널과 다르다면 이동
#         if ctx.voice_client.channel != channel:
#             await ctx.voice_client.move_to(channel)
#             await ctx.send(f"{channel.name} 채널로 이동했습니다")
#         else:
#             await ctx.send(f"이미 {channel.name} 채널에 연결되어 있습니다")
#     else:
#         # 처음 연결하는 경우
#         await channel.connect()
#         await ctx.send(f"{channel.name} 채널에 접속했습니다")


@bot.command()
async def join(ctx):
    """사용자가 있는 음성 채널에 봇이 들어옵니다."""
    if ctx.author.voice:  # 사용자가 음성 채널에 있는지 확인
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send(f"{channel.name}에 접속했어요")
    else:
        await ctx.send("먼저 음성 채널에 들어가주세요")


@bot.command()
async def leave(ctx):
    """봇이 현재 들어가 있는 음성 채널에서 나옵니다."""
    if ctx.voice_client:  # 봇이 현재 연결되어 있는지 확인
        await ctx.voice_client.disconnect()
        await ctx.send("음성 채널에서 나갔어요")
    else:
        await ctx.send("현재 어떤 음성 채널에도 들어가 있지 않아요")

bot.run(TOKEN)