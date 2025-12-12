import os
from yt_dlp import YoutubeDL
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

# 서버별 플레이리스트
music_queues = {}

#### 기본 event 처리
@bot.event
async def on_ready(): # 봇 실행시 호출
    print(f"로그인 성공: {bot.user}")

@bot.event # 음성 상태 변경시 호출
async def on_voice_state_update(member, before, after):
    # 봇 자신은 무시
    if member.bot:
        return

    # before.channel: 바뀌기 전 상태
    # after.channel: 바뀐 후 상태
    # -> 즉, before은 음성 채널을 '떠난' 경우에만 값이 있음
    if before.channel is not None and after.channel != before.channel:
        channel = before.channel
        vc = discord.utils.get(bot.voice_clients, guild=member.guild)

        if vc and vc.channel == channel:
            # 사람(봇 제외) 수 세기
            human_count = sum(1 for m in channel.members if not m.bot)
            if human_count == 0:
                await vc.disconnect()
                print(f"{channel.name} 채널에 아무도 없어 자동 나가기")

#### 입력 커맨드 처리 : bot.command()
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

#### 유튜브 음원 처리
@bot.command()
async def play(ctx, *, query: str):
    """YouTube URL 또는 검색어를 받아 음성 채널에서 음악을 재생합니다."""
    if not ctx.author.voice:
        await ctx.send("먼저 음성 채널에 들어가 주세요")
        return

    channel = ctx.author.voice.channel
    if not ctx.voice_client:
        await channel.connect()

    vc = ctx.voice_client

    # 이미 재생 중이면 방지
    if vc.is_playing():
        await ctx.send("이미 음악이 재생 중입니다. 잠시만 기다려주세요.")
        return

    # yt-dlp 옵션
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'nocheckcertificate': True,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch1',
        'source_address': '0.0.0.0'
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)

            # 검색결과 또는 재생목록 구조일 경우 첫 번째 항목 사용
            if 'entries' in info and len(info['entries']) > 0:
                info = info['entries'][0]

            audio_url = info['url']
            title = info.get('title', '알 수 없는 제목')

    except Exception as e:
        await ctx.send(f"음원 정보를 불러오는 중 오류가 발생했습니다.\n```{e}```")
        return

    ffmpeg_options = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn -filter:a "volume=0.05"'
    }

    source = discord.FFmpegPCMAudio(audio_url, **ffmpeg_options)
    vc.play(source, after=lambda e: print(f"재생 완료: {title}" if not e else f"에러 발생: {e}"))

    await ctx.send(f"🎵 **{title}** 재생을 시작합니다.")


bot.run(TOKEN)


# 모듈화할 함수
# 사용자가 음성 채널에 있는지 확인할 것

# 봇 입장로직 함수화할 것

# 연결되어있는지도 나눌것

# ctx.author.voice -> 명령어를 입력한 사람의 음성상태
# ctx.author.voice -> 명령어를 입력한 사람이 입장중인 채널

# ctx.voice_client 봇이 연결되어있는지 객체 그자체
