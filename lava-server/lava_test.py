import discord
import os
from dotenv import load_dotenv
from discord.ext import commands
import wavelink

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

class MyBot(commands.Bot):
    async def setup_hook(self):
        await wavelink.Pool.connect(
            client=self,
            nodes=[
                wavelink.Node(
                    uri="http://localhost:2333",
                    password="youshallnotpass"
                )
            ]
        )

        # 🔴 이 출력이 안 나오면 연결 실패
        print("Nodes:", wavelink.Pool.nodes)

bot = MyBot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("Bot ready")

@bot.command()
async def load(ctx, url: str):
    # 🔴 노드 연결 여부 선 체크
    if not wavelink.Pool.nodes:
        await ctx.send("❌ Lavalink 노드 미연결 상태")
        return

    tracks = await wavelink.Playable.search(
        url,
        node=wavelink.Pool.get_node()
    )

    if not tracks:
        await ctx.send("❌ 로드 실패")
        return

    await ctx.send(f"✅ 로드 성공: {tracks[0].title}")

@bot.command()
async def play(ctx, url: str):
    if not ctx.author.voice:
        await ctx.send("❌ 음성 채널에 먼저 들어가")
        return

    vc = ctx.voice_client
    if not vc:
        vc = await ctx.author.voice.channel.connect(cls=wavelink.Player)

    player: wavelink.Player = vc

    tracks = await wavelink.Playable.search(
        url,
        node=wavelink.Pool.get_node()
    )

    if not tracks:
        await ctx.send("❌ 트랙 없음")
        return

    await player.play(tracks[0])
    await ctx.send(f"▶️ 재생 시작: {tracks[0].title}")


bot.run(TOKEN)
