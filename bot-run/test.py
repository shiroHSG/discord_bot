import os
from dotenv import load_dotenv
import discord
from discord.ext import commands, tasks
import asyncio
import json
import wavelink

# =========================
# 
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


# =========================
# Bot (중요)
# =========================
class MyBot(commands.Bot):
    async def setup_hook(self):
        await wavelink.Pool.connect(
            client=self,
            nodes=[
                wavelink.Node(
                    uri="http://127.0.0.1:2333",
                    password="youshallnotpass"
                )
            ]
        )

bot = MyBot(
    command_prefix="!",
    intents=intents,
    help_command=None
)

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
# Button Control
# =========================
class PlayerControls(discord.ui.View):
    def __init__(self, player: wavelink.Player):
        super().__init__(timeout=None)
        self.player = player

    @discord.ui.button(label="⏯", style=discord.ButtonStyle.primary)
    async def pause_resume(self, interaction, button):
        if self.player.playing:
            await self.player.pause()
        else:
            await self.player.resume()
        await interaction.response.defer()

    @discord.ui.button(label="⏭", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction, button):
        await self.player.stop()
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

    async def ensure_author_in_voice(self, ctx):
        if not ctx.author.voice:
            await ctx.send("❌ 음성 채널에 들어가 있어야 합니다.", delete_after=10)
            return False
        return True

    def build_now_playing_embed(self, track, requester):
        embed = discord.Embed(
            title="🎶 지금 재생중",
            description=f"[{track.title}]({track.uri})",
            color=0x1DB954
        )

        if track.artwork:
            embed.set_thumbnail(url=track.artwork)

        m, s = divmod(track.length // 1000, 60)
        embed.add_field(name="곡 길이", value=f"{m:02}:{s:02}", inline=True)

        embed.set_footer(
            text=requester.display_name,
            icon_url=requester.display_avatar.url
        )
        return embed

    async def cleanup_now_playing(self, guild_id):
        old = self.now_playing_message.pop(guild_id, None)
        if old:
            try:
                await old.delete()
            except:
                pass

    async def player_loop(self, guild_id):
        guild = self.bot.get_guild(guild_id)

        try:
            while True:
                queue = self.get_queue(guild_id)
                if not queue:
                    break

                item = queue.pop(0)
                player: wavelink.Player = guild.voice_client

                if not player or not player.connected:
                    break

                tracks = await wavelink.Playable.search(
                    item["query"],
                    node=wavelink.Pool.get_node(),
                    source=wavelink.TrackSource.SoundCloud
                )

                if not tracks:
                    continue

                track = tracks[0]

                embed = self.build_now_playing_embed(track, item["requester"])
                await self.cleanup_now_playing(guild_id)

                msg = await item["channel"].send(
                    embed=embed,
                    view=PlayerControls(player)
                )
                self.now_playing_message[guild_id] = msg

                await player.play(track)

                while player.playing:
                    await asyncio.sleep(0.5)

        except asyncio.CancelledError:
            pass
        finally:
            self.play_tasks.pop(guild_id, None)

    @commands.command(aliases=["p"])
    async def play(self, ctx, *, query):
        try:
            await ctx.message.delete()
        except:
            pass

        if not await self.ensure_author_in_voice(ctx):
            return

        if not ctx.voice_client:
            await ctx.author.voice.channel.connect(cls=wavelink.Player)

        self.get_queue(ctx.guild.id).append({
            "query": query,
            "requester": ctx.author,
            "channel": ctx.channel
        })

        if ctx.guild.id not in self.play_tasks:
            self.play_tasks[ctx.guild.id] = asyncio.create_task(
                self.player_loop(ctx.guild.id)
            )

# =========================
# Run
# =========================
@bot.event
async def on_ready():
    print(f"{bot.user} 로그인 완료")

    if not update_server_count.is_running():
        update_server_count.start()

async def main():
    async with bot:
        await bot.add_cog(Music(bot))
        await bot.start(TOKEN)

asyncio.run(main())
