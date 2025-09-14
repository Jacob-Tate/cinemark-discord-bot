# Cinemark Discord Bot

🎬 **A powerful Discord bot that scrapes Cinemark for new and upcoming movies, sending rich, interactive notifications for anime and personalized watchlists.**

![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Discord](https://img.shields.io/badge/Discord-%235865F2.svg?style=for-the-badge&logo=discord&logoColor=white)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Selenium](https://img.shields.io/badge/Selenium-43B02A?style=for-the-badge&logo=selenium&logoColor=white)

## Features

-  scraping Cinemark's "Now Playing" and "Coming Soon" sections for a specific theater.
-  enriqueciendo datos de películas con información de TMDB (géneros, descripciones, y la palabra clave "anime").
- 📨 **Notificaciones de Discord Altamente Personalizables:**
  - Canales dedicados para estrenos de anime, todos los estrenos de películas, y notificaciones de listas de seguimiento personales.
  - Notificaciones de "Película Nueva Añadida" con póster, descripción y géneros.
  - Notificaciones de "Horarios Actualizados" cuando se añaden nuevas fechas para películas de anime o en lista de seguimiento.
- 🤖 **Comandos de Bot Interactivos:**
  - `/check`: Forzar manualmente una comprobación de actualizaciones.
  - `/showtimes`: Obtener una lista completa de fechas y horarios para cualquier película.
  - `/watchlist`: Añadir películas a una lista de seguimiento personal, ¡incluso con patrones regex!
  - `/ignore`: Silenciar notificaciones para películas específicas.
- 🔐 **Seguridad y Persistencia:**
  - Todas las claves y secretos se gestionan de forma segura a través de variables de entorno.
  - La base de datos SQLite persiste en un volumen de Docker, por lo que tus listas de seguimiento nunca se pierden.
- 🚀 **Despliegue Sencillo con Docker:** Empaquetado en un contenedor Docker para un despliegue fácil y consistente.

## Quick Start

### 1. Create a Discord Bot
1.  Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2.  Create a **New Application** and give it a name.
3.  Navigate to the **Bot** tab and click **Reset Token** to get your bot's token.
4.  Enable the **Message Content Intent** under "Privileged Gateway Intents".
5.  Go to **OAuth2 -> URL Generator**, select `bot` and `applications.commands` scopes.
6.  In "Bot Permissions", select **Send Messages** and **Embed Links**.
7.  Copy the generated URL and invite the bot to your server.

### 2. Prepare Your Environment
```bash
# Clone the repository
git clone https://github.com/your-username/cinemark-discord-bot.git
cd cinemark-discord-bot

# Create a .env file from the example
cp .env.example .env

# Edit the .env file with your secrets
nano .env
```
Fill in the `.env` file with the required tokens and channel IDs.

### 3. Deploy with Docker Compose
```bash
# Build and start the bot in the background
docker-compose up -d
```

### 4. Check Logs
```bash
docker-compose logs -f
```

## Environment Variables

Create a `.env` file in the project root. See `.env.example` for the template.

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | **Required** | Your Discord Bot Token. |
| `TMDB_API_KEY` | **Required** | Your API key from The Movie Database. |
| `DISCORD_CHANNEL_ANIME_ID` | **Required** | Channel ID for new anime release notifications. |
| `DISCORD_CHANNEL_WATCHLIST_ID` | **Required** | Channel ID for personalized watchlist notifications. |
| `DISCORD_CHANNEL_ALL_MOVIES_ID` | Optional | Channel ID for all new movie release notifications. |
| `THEATER_URL` | **Required** | The url for the cinemark theatre you prefer |

## Bot Commands

- `/check`: Manually triggers the scraping process. (Bot Owner only)
- `/showtimes <movie>`: Displays available showtimes for a movie.
- `/watchlist view`: Shows your personal movie watchlist.
- `/watchlist add <movie>`: Adds a movie to your watchlist by its exact title.
- `/watchlist add_regex <pattern>`: Adds a movie to your watchlist using a case-insensitive regex pattern (e.g., `spider-man.*`).
- `/watchlist remove <pattern>`: Removes a movie or pattern from your watchlist.
- `/ignore view`: Shows your personal ignore list.
- `/ignore add <movie>`: Stops the bot from processing updates for a specific movie.
- `/ignore remove <movie>`: Removes a movie from your ignore list.

## Notification Examples

**New Anime Movie**
![New Anime Notification](https://i.imgur.com/your-image-link-here.png)

**Showtimes Updated**
![Showtime Update Notification](https://i.imgur.com/your-image-link-here.png)

## Development

### Local Setup
```bash
# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create your .env file
cp .env.example .env
nano .env

# Run the bot directly
python main.py
```

### Manual Build
```bash
# Build the Docker image locally
docker build -t cinemark-discord-bot .

# Run the container
docker run -d --name cinemark-bot --env-file .env -v ./movies.db:/app/movies.db cinemark-discord-bot
```

## Contributing

Contributions are welcome! Please feel free to open a pull request or an issue.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.
