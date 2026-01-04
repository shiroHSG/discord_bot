import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
import asyncio
from yt_dlp import YoutubeDL

# =========================
# 임베드 하나만 보이게 + 연결 끊길 시 수정
# =========================

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

# =========================
# 음악 소스 생성
# =========================

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

    async def player_loop(self, guild_id):
        guild = self.bot.get_guild(guild_id)

        try:
            while True:
                queue = self.get_queue(guild_id)
                if not queue:
                    break

                item = queue.pop(0)

                source = await YTDLSource.from_query(
                    item["query"],
                    loop=self.bot.loop
                )

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

                # embed.add_field(name="요청자", value=..., inline=True)

                embed.set_footer(
                    text=item["requester"].display_name,
                    icon_url=item["requester"].display_avatar.url
                )

                # 이전 Embed 삭제
                old_msg = self.now_playing_message.get(guild_id)
                if old_msg:
                    try:
                        await old_msg.delete()
                    except:
                        pass

                vc = guild.voice_client
                if not vc or not vc.is_connected():
                    break

                msg = await guild.text_channels[0].send(
                    embed=embed,
                    view=PlayerControls(vc)
                )
                self.now_playing_message[guild_id] = msg

                try:
                    vc.play(source)
                except discord.ClientException:
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

        if not ctx.author.voice:
            return

        if not ctx.voice_client:
            await ctx.author.voice.channel.connect()

        self.get_queue(ctx.guild.id).append({
            "query": query,
            "requester": ctx.author
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

        vc = ctx.voice_client
        if vc:
            await vc.disconnect()

        self.get_queue(ctx.guild.id).clear()

        task = self.play_tasks.pop(ctx.guild.id, None)
        if task:
            task.cancel()

        msg = self.now_playing_message.pop(ctx.guild.id, None)
        if msg:
            try:
                await msg.delete()
            except:
                pass

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

                    msg = self.now_playing_message.pop(member.guild.id, None)
                    if msg:
                        try:
                            await msg.delete()
                        except:
                            pass

# =========================
# Run
# =========================
@bot.event
async def on_ready():
    print(f"{bot.user} 로그인 완료")

async def main():
    async with bot:
        await bot.add_cog(Music(bot))
        await bot.start(TOKEN)

asyncio.run(main())
