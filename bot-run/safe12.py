import os
from dotenv import load_dotenv
import discord
from discord.ext import commands, tasks
import asyncio
from yt_dlp import YoutubeDL
import json

# =========================
# 전용채널에서 명령어 입력
# =========================

# =========================
# 채널 추가 및 불러오는 함수
# =========================

CHANNEL_FILE = "music_channels.json"

def load_music_channels():
    try:
        with open(CHANNEL_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f).get("music_channels", []))
    except FileNotFoundError:
        return set()

def save_music_channels(channels):
    with open(CHANNEL_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"music_channels": list(channels)},
            f,
            ensure_ascii=False,
            indent=2
        )

# =========================
# Settings
# =========================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# =========================
# Intents
# =========================
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# Bot Status Task
# =========================
@tasks.loop(hours=24)
async def update_server_count():
    server_count = len(bot.guilds)
    await bot.change_presence(
        activity=discord.Game(
            name=f"🎶 서버 {server_count}개에서 음악 재생중"
        )
    )

# =========================
# yt-dlp / ffmpeg
# =========================
ytdl_opts = {
    "format": "bestaudio/best",
    "quiet": True,
    "default_search": "ytsearch1",
    "source_address": "0.0.0.0",
    "noplaylist": True,
}

ffmpeg_opts = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

ytdl = YoutubeDL(ytdl_opts)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.08):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get("title")
        self.duration = data.get("duration")
        self.url = data.get("webpage_url")
        self.thumbnail = data.get("thumbnail")

    @classmethod
    async def from_query(cls, query, *, loop):

        data = await loop.run_in_executor(
            None, lambda: ytdl.extract_info(query, download=False)
        )

        if "entries" in data:
            data = data["entries"][0]

        source = discord.FFmpegPCMAudio(data["url"], **ffmpeg_opts)
        return cls(source, data=data)

# =========================
# Button Control
# =========================
class PlayerControls(discord.ui.View):
    def __init__(self, vc):
        super().__init__(timeout=None)
        self.vc = vc

    @discord.ui.button(label="⏯", style=discord.ButtonStyle.primary)
    async def pause_resume(self, interaction, button):
        if self.vc.is_playing():
            self.vc.pause()
        elif self.vc.is_paused():
            self.vc.resume()
        await interaction.response.defer()

    @discord.ui.button(label="⏭", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction, button):
        if self.vc.is_playing() or self.vc.is_paused():
            self.vc.stop()
        await interaction.response.defer()

# =========================
# Music Cog
# =========================
class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self.play_tasks = {}
        self.now_playing_message = {}

    def get_queue(self, guild_id):
        return self.queues.setdefault(guild_id, [])

    # =========================
    # Voice Channel Check
    # =========================
    async def ensure_author_in_voice(self, ctx):
        if not ctx.author.voice:
            await ctx.send(
                "❌ 음성 채널에 들어가 있어야 사용할 수 있는 명령어입니다.",
                delete_after=10
            )
            return False
        return True

    # =========================
    # Embed Builder
    # =========================
    def build_now_playing_embed(self, source, requester):
        embed = discord.Embed(
            title="🎶 지금 재생중",
            description=f"[{source.title}]({source.url})",
            color=0x1DB954
        )

        if source.thumbnail:
            embed.set_thumbnail(url=source.thumbnail)

        m, s = divmod(source.duration or 0, 60)
        embed.add_field(
            name="곡 길이",
            value=f"{m:02}:{s:02}",
            inline=True
        )

        embed.set_footer(
            text=requester.display_name,
            icon_url=requester.display_avatar.url
        )

        return embed

    # =========================
    # Message Cleanup
    # =========================
    async def cleanup_now_playing(self, guild_id):
        old = self.now_playing_message.pop(guild_id, None)
        if old:
            try:
                await old.delete()
            except:
                pass

    # =========================
    # Safe Play
    # =========================
    def safe_play(self, vc, source):
        try:
            vc.play(source)
            return True
        except discord.ClientException:
            return False

    # =========================
    # Core playback loop
    # =========================
    async def player_loop(self, guild_id):
        guild = self.bot.get_guild(guild_id)

        try:
            while True:
                queue = self.get_queue(guild_id)
                if not queue:
                    break

                item = queue.pop(0)

                vc = guild.voice_client
                if not vc or not vc.is_connected():
                    break

                source = await YTDLSource.from_query(
                    item["query"],
                    loop=self.bot.loop
                )

                embed = self.build_now_playing_embed(
                    source,
                    item["requester"]
                )

                await self.cleanup_now_playing(guild_id)

                text_channel = item["channel"]  # ✅ 요청 채널 사용
                msg = await text_channel.send(
                    embed=embed,
                    view=PlayerControls(vc)
                )
                self.now_playing_message[guild_id] = msg

                if not self.safe_play(vc, source):
                    break

                while vc.is_playing() or vc.is_paused():
                    await asyncio.sleep(0.5)

        except asyncio.CancelledError:
            pass
        finally:
            self.play_tasks.pop(guild_id, None)

    # =========================
    # Commands
    # =========================
    @commands.command(name="p")
    async def play(self, ctx, *, query):
        try:
            await ctx.message.delete()
        except:
            pass

        if not await self.ensure_author_in_voice(ctx):
            return

        if not ctx.voice_client:
            await ctx.author.voice.channel.connect()

        self.get_queue(ctx.guild.id).append({
            "query": query,
            "requester": ctx.author,
            "channel": ctx.channel   # ✅ 추가
        })

        if ctx.guild.id not in self.play_tasks:
            self.play_tasks[ctx.guild.id] = asyncio.create_task(
                self.player_loop(ctx.guild.id)
            )

    @commands.command(aliases=["q", "queue"])
    async def queue_list(self, ctx):
        try:
            await ctx.message.delete()
        except:
            pass

        queue = self.get_queue(ctx.guild.id)
        embed = discord.Embed(title="🎶 재생목록", color=0x1DB954)

        if not queue:
            embed.description = "📭 현재 대기중인 곡이 없습니다."
        else:
            for idx, item in enumerate(queue, start=1):
                embed.add_field(
                    name=f"{idx}️⃣ {item['query']}",
                    value=item["requester"].display_name,
                    inline=False
                )

        await ctx.send(embed=embed)

    @commands.command()
    async def stop(self, ctx):
        try:
            await ctx.message.delete()
        except:
            pass

        if not await self.ensure_author_in_voice(ctx):
            return

        vc = ctx.voice_client
        if not vc:
            return

        if vc.is_playing() or vc.is_paused():
            vc.stop()

        # 🗑 큐 초기화
        self.get_queue(ctx.guild.id).clear()

        # 재생 루프 종료
        task = self.play_tasks.pop(ctx.guild.id, None)
        if task:
            task.cancel()

        # Now Playing 메시지 제거
        await self.cleanup_now_playing(ctx.guild.id)

    @commands.command()
    async def join(self, ctx):
        try:
            await ctx.message.delete()
        except:
            pass

        if not await self.ensure_author_in_voice(ctx):
            return

        if ctx.voice_client and ctx.voice_client.is_connected():
            return  # 이미 연결되어 있으면 아무것도 안 함

        await ctx.author.voice.channel.connect()

    @commands.command()
    async def leave(self, ctx):
        try:
            await ctx.message.delete()
        except:
            pass

        vc = ctx.voice_client
        if not vc:
            return

        await vc.disconnect()

        # 큐 / 태스크 / 메시지 정리
        self.get_queue(ctx.guild.id).clear()

        task = self.play_tasks.pop(ctx.guild.id, None)
        if task:
            task.cancel()

        await self.cleanup_now_playing(ctx.guild.id)

    # =========================
    # 채널 추가 및 삭제
    # =========================
    @commands.command(name="채널추가")
    async def add_music_channel(self, ctx):
        try:
            await ctx.message.delete()
        except:
            pass

        channels = load_music_channels()
        channel_id = ctx.channel.id

        if channel_id in channels:
            await ctx.send("이미 추가된 채널입니다.", delete_after=5)
            return

        channels.add(channel_id)
        save_music_channels(channels)

        await ctx.send("전용채널로 추가되었습니다.", delete_after=5)

    @commands.command(name="채널삭제")
    async def remove_music_channel(self, ctx):
        try:
            await ctx.message.delete()
        except:
            pass

        channels = load_music_channels()
        channel_id = ctx.channel.id

        if channel_id not in channels:
            await ctx.send("전용채널이 아닙니다.", delete_after=5)
            return

        channels.remove(channel_id)
        save_music_channels(channels)

        await ctx.send("전용채널에서 삭제되었습니다.", delete_after=5)

    # =========================
    # 전용채널 명령어
    # =========================
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        channels = load_music_channels()

        if message.channel.id not in channels:
            return

        content = message.content.strip()
        if not content:
            return

        # 전용 채널: 메시지 삭제
        try:
            await message.delete()
        except:
            pass

        # !로 시작하면 기존 명령어에 맡김 (아무 것도 안 함)
        if content.startswith("!"):
            return

        # ===== 여기부터 핵심 =====
        # ! 없이 입력 → play(query) 직접 호출

        ctx = await self.bot.get_context(message)

        # play command 객체 가져오기
        play_cmd = self.bot.get_command("p")
        if not play_cmd:
            return

        # play(ctx, query=content) 실행
        await play_cmd.callback(self, ctx, query=content)


    # =========================
    # Auto leave
    # =========================
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return

        if before.channel and after.channel != before.channel:
            vc = member.guild.voice_client
            if vc and vc.channel == before.channel:
                humans = [m for m in before.channel.members if not m.bot]
                if not humans:
                    await vc.disconnect()
                    self.get_queue(member.guild.id).clear()

                    task = self.play_tasks.pop(member.guild.id, None)
                    if task:
                        task.cancel()

                    await self.cleanup_now_playing(member.guild.id)

# =========================
# Run
# =========================
@bot.event
async def on_ready():
    print(f"{bot.user} 로그인 완료")

    await update_server_count()
    if not update_server_count.is_running():
        update_server_count.start()

async def main():
    async with bot:
        await bot.add_cog(Music(bot))
        await bot.start(TOKEN)

asyncio.run(main())
