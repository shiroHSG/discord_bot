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
        self.queue = {}
        self.playing = {}

    def get_queue(self, guild_id):
        return self.queue.setdefault(guild_id, [])

    async def play_next(self, guild_id):
        queue = self.get_queue(guild_id)

        if not queue:
            self.playing[guild_id] = False
            return

        ctx, url = queue.pop(0)
        player = await YTDLSource.from_url(url, loop=self.bot.loop)

        ctx.voice_client.play(
            player,
            after=lambda _: self.bot.loop.create_task(self.play_next(guild_id))
        )

        embed = discord.Embed(
            title="🎵 재생 중",
            description=player.title,
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @commands.command(name="join")
    async def join(self, ctx):
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()

    @commands.command(name="p")
    async def play(self, ctx, *, query):
        if ctx.voice_client is None:
            await self.join(ctx)

        queue = self.get_queue(ctx.guild.id)
        queue.append((ctx, query))

        if not self.playing.get(ctx.guild.id, False):
            self.playing[ctx.guild.id] = True
            await self.play_next(ctx.guild.id)

        await ctx.message.delete()

    @commands.command()
    async def skip(self, ctx):
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()

    @commands.command()
    async def pause(self, ctx):
        ctx.voice_client.pause()

    @commands.command()
    async def resume(self, ctx):
        ctx.voice_client.resume()

    @commands.command()
    async def stop(self, ctx):
        await ctx.voice_client.disconnect()
        self.queue[ctx.guild.id] = []
        self.playing[ctx.guild.id] = False

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
