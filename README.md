# discord_bot
디스코드봇 개발일지

토큰을 분리하여 CI/CD를 고려해 Github Actions에 workflow를 작성할 예정

## Run order
1. Run Lavalink
2. Run Discord bot

## Lavalink
- Java 17+
- Default port (8080) or configured port

## Bot
- Python 3.10+
- .env with DISCORD_TOKEN