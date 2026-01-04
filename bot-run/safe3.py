import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
import asyncio
from yt_dlp import YoutubeDL

# =========================
# Settings
# =========================

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# =========================
# Intents
# =========================
intents = discord.Intents.default()
intents.message_content = True  # 명령어 읽기
intents.voice_states = True     # 음성 채널 연결 관리

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

# =========================
# yt-dlp / ffmpeg
# =========================
ytdl_opts = {
    'format': 'bestaudio/best',
    'quiet': True,
    'default_search': 'ytsearch1',
    'source_address': '0.0.0.0',
    'noplaylist': True,
}

ffmpeg_opts = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = YoutubeDL(ytdl_opts)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.08):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get("title")
        self.url = data.get("url")
        self.duration = data.get("duration")

    @classmethod
    async def from_url(cls, query, *, loop):
        data = await loop.run_in_executor(
            None, lambda: ytdl.extract_info(query, download=False)
        )

        if 'entries' in data:
            data = data['entries'][0]

        return cls(
            discord.FFmpegPCMAudio(data['url'], **ffmpeg_opts),
            data=data
        )

# =========================
# Music Cog
# =========================
class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}       # guild_id -> [url]
        self.play_tasks = {}  # guild_id -> asyncio.Task

    def get_queue(self, guild_id):
        return self.queues.setdefault(guild_id, [])

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

                vc = guild.voice_client
                if not vc or not vc.is_connected():
                    break

                url = queue.pop(0)
                source = await YTDLSource.from_url(url, loop=self.bot.loop)

                vc.play(source)

                while vc.is_playing() or vc.is_paused():
                    await asyncio.sleep(0.5)

        finally:
            self.play_tasks.pop(guild_id, None)

    # =========================
    # Commands
    # =========================
    @commands.command(name="p")
    async def play(self, ctx, *, query):
        if not ctx.author.voice:
            await ctx.send("먼저 음성 채널에 들어가 주세요")
            return

        if not ctx.voice_client or not ctx.voice_client.is_connected():
            await ctx.author.voice.channel.connect()

        queue = self.get_queue(ctx.guild.id)
        queue.append(query)

        if ctx.guild.id not in self.play_tasks:
            self.play_tasks[ctx.guild.id] = asyncio.create_task(
                self.player_loop(ctx.guild.id)
            )

        await ctx.message.delete()

    @commands.command()
    async def join(self, ctx):
        if not ctx.author.voice:
            await ctx.send("먼저 음성 채널에 들어가 주세요")
            return

        channel = ctx.author.voice.channel
        vc = ctx.voice_client

        if vc and vc.is_connected():
            if vc.channel != channel:
                await vc.move_to(channel)
        else:
            await channel.connect()

    @commands.command()
    async def skip(self, ctx):
        vc = ctx.voice_client
        if vc and vc.is_playing():
            vc.stop()

    @commands.command()
    async def pause(self, ctx):
        vc = ctx.voice_client
        if vc and vc.is_playing():
            vc.pause()

    @commands.command()
    async def resume(self, ctx):
        vc = ctx.voice_client
        if vc and vc.is_paused():
            vc.resume()

    @commands.command()
    async def stop(self, ctx):
        vc = ctx.voice_client
        if vc:
            vc.stop()
            await vc.disconnect()

        self.get_queue(ctx.guild.id).clear()

        task = self.play_tasks.pop(ctx.guild.id, None)
        if task:
            task.cancel()

    @commands.command(aliases=["q", "queue"])
    async def queue_list(self, ctx):
        guild_id = ctx.guild.id
        queue = self.get_queue(guild_id)

        if not queue:
            return await ctx.send("📭 현재 대기열에 노래가 없습니다.")

        lines = []
        for idx, query in enumerate(queue, start=1):
            lines.append(f"{idx}. {query}")

        message = "🎶 **대기열 목록**\n" + "\n".join(lines)

        if len(message) > 1900:
            message = message[:1900] + "\n..."

        await ctx.send(message)

    @commands.command()
    async def leave(self, ctx):
        vc = ctx.voice_client
        if vc:
            await vc.disconnect()

        self.get_queue(ctx.guild.id).clear()

        task = self.play_tasks.pop(ctx.guild.id, None)
        if task:
            task.cancel()

    # =========================
    # Events
    # =========================
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return

        if before.channel and after.channel != before.channel:
            guild = member.guild
            vc = guild.voice_client

            if vc and vc.channel == before.channel:
                human_count = sum(
                    1 for m in before.channel.members if not m.bot
                )

                if human_count == 0:
                    await vc.disconnect()
                    self.get_queue(guild.id).clear()

                    task = self.play_tasks.pop(guild.id, None)
                    if task:
                        task.cancel()

                    print(f"{before.channel.name} 채널에 아무도 없어 자동 나가기")


# =========================
# Events
# =========================
@bot.event
async def on_ready():
    print(f"{bot.user} 로그인 완료")

# =========================
# Run
# =========================
async def main():
    async with bot:
        await bot.add_cog(Music(bot))
        await bot.start(TOKEN)

asyncio.run(main())
