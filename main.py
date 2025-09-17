import discord
from discord.ext import commands, tasks
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime
import database as db
import scraper
import time
import re
import os

# --- ⚠️ CONFIGURATION - PASTE YOUR TOKENS HERE ⚠️ ---
try:
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    TMDB_API_KEY = os.getenv('TMDB_API_KEY')
    
    DISCORD_CHANNEL_ANIME_ID = int(os.getenv('DISCORD_CHANNEL_ANIME_ID'))
    DISCORD_CHANNEL_WATCHLIST_ID = int(os.getenv('DISCORD_CHANNEL_WATCHLIST_ID'))
    # Optional channel - default to 0 if missing or empty
    all_movies_id_str = os.getenv('DISCORD_CHANNEL_ALL_MOVIES_ID')
    DISCORD_CHANNEL_ALL_MOVIES_ID = int(all_movies_id_str) if all_movies_id_str else 0
except (TypeError, ValueError):
    print("FATAL: One of your required DISCORD_CHANNEL... IDs is missing or is not a valid number in your .env file.")
    exit()
# --------------------------------------------------------------------

intents = discord.Intents.default()
bot = discord.Bot(intents=intents)
watchlist_commands = bot.create_group("watchlist", "Manage your movie watchlist")
ignore_commands = bot.create_group("ignore", "Manage your personal ignore list")

# Global flag to prevent multiple checks from running simultaneously
check_in_progress = False

# --- NEW HELPER FUNCTION FOR SMARTER UPDATES ---
def have_new_dates_been_added(old_showtimes_str: str, new_showtimes_list: list) -> bool:
    """
    Compares old and new showtimes to see if new dates have been added.
    Returns True only if the new list is a proper superset of the old list.
    """
    # If there were no dates before, any new date is an update.
    if not old_showtimes_str or "not listed" in old_showtimes_str:
        return bool(new_showtimes_list) # True only if the new list is not empty
    
    # Convert strings/lists to sets for easy comparison
    old_dates = {date.strip() for date in old_showtimes_str.split(',') if date.strip()}
    new_dates = set(new_showtimes_list)
    
    # An update has occurred if all old dates are still present AND there are more new dates.
    return old_dates.issubset(new_dates) and len(new_dates) > len(old_dates)

def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless'); options.add_argument('--no-sandbox'); options.add_argument('--disable-dev-shm-usage')
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

async def send_notification(channel_id, embed, content=None):
    if not channel_id: return
    try:
        channel = await bot.fetch_channel(channel_id)
        await channel.send(content=content, embed=embed)
        print(f"    -> Notification sent to channel #{channel.name}.")
    except Exception as e:
        print(f"    -> ERROR sending notification: {e}")

async def perform_movie_check():
    """Extracted check logic that can be called from both scheduled task and manual command"""
    global check_in_progress
    
    if check_in_progress:
        print("Check already in progress, skipping...")
        return False
        
    check_in_progress = True
    print(f"[{datetime.now()}] --- Running Movie Check ---")
    
    driver = setup_driver()
    conn = db.get_connection()
    try:
        scraped_movies = scraper.scrape_all_movies(driver)
                
        print(f"Found {len(scraped_movies)} unique movies. Processing...")
        for movie in scraped_movies:
            if db.is_movie_ignored_by_any_user(conn, movie['title']):
                print(f"\nSkipping '{movie['title']}' as it is on a user's ignore list.")
                continue
            
            details, is_anime, genres_str, overview = scraper.get_tmdb_details(movie['title'], TMDB_API_KEY)
            db_movie = db.get_movie(conn, movie['title'])
            watchers = db.get_watchers_for_movie(conn, movie['title'])
            is_watched = bool(watchers)
            
            print(f"\nProcessing: '{movie['title']}' (Anime: {is_anime}, Watched: {is_watched})")
            
            showtimes_list = [] # Use a list to pass to our new check function
            showtimes_str = db_movie['showtimes'] if db_movie else ""
            if is_anime or is_watched:
                showtimes_dict = scraper.get_specific_showtimes(driver, movie['cinemark_url'])
                if "Error" not in showtimes_dict and "Notice" not in showtimes_dict:
                    showtimes_list = list(showtimes_dict.keys())
                    showtimes_str = ", ".join(showtimes_list)
            
            if db_movie is None:
                print("    -> NEW MOVIE!")
                db.add_or_update_movie(conn, movie, showtimes_str, 1 if is_anime else 0, overview)
                desc_field = f"**Release Date:** {movie['release_date']}\n**Genres:** {genres_str}\n\n**Description:**\n{overview}\n"
                                
                all_movies_embed = discord.Embed(title=f"🎬 New Movie Added: {movie['title']}", description=desc_field, url=movie['cinemark_url'], color=discord.Color.dark_grey() if not is_anime else discord.Color.green())
                all_movies_embed.set_image(url=movie['poster_url'])
                await send_notification(DISCORD_CHANNEL_ALL_MOVIES_ID, all_movies_embed)
                
                if is_anime:
                    anime_embed = discord.Embed(title=f"✨ New Anime Movie: {movie['title']}", description=desc_field, url=movie['cinemark_url'], color=discord.Color.green())
                    anime_embed.set_image(url=movie['poster_url'])
                    anime_embed.add_field(name="Available Dates", value=showtimes_str or "Not yet listed")
                    await send_notification(DISCORD_CHANNEL_ANIME_ID, anime_embed)
                
                if is_watched:
                    ping_message = " ".join([f"<@{user_id}>" for user_id in watchers]) if watchers else None
                    watchlist_embed = discord.Embed(title=f"🔔 New Watchlist Movie: {movie['title']}", description=desc_field, url=movie['cinemark_url'], color=discord.Color.gold())
                    watchlist_embed.set_image(url=movie['poster_url'])
                    watchlist_embed.add_field(name="Available Dates", value=showtimes_str or "Not yet listed")
                    await send_notification(DISCORD_CHANNEL_WATCHLIST_ID, watchlist_embed, content=ping_message)
            
            elif (is_anime or is_watched) and have_new_dates_been_added(db_movie['showtimes'], showtimes_list):
                print("    -> NEW SHOWTIMES ADDED!")
                db.update_showtimes(conn, movie['title'], showtimes_str)
                update_embed = discord.Embed(title=f"🔄 Showtimes Updated for: {movie['title']}", url=movie['cinemark_url'], color=discord.Color.blue())
                update_embed.set_image(url=movie['poster_url'])
                update_embed.add_field(name="Old Dates", value=db_movie['showtimes'] or "None", inline=False)
                update_embed.add_field(name="New Dates", value=showtimes_str or "None", inline=False)
                                
                if is_watched:
                    ping_message = " ".join([f"<@{user_id}>" for user_id in watchers]) if watchers else None
                    await send_notification(DISCORD_CHANNEL_WATCHLIST_ID, update_embed, content=ping_message)
                                
                if is_anime:
                    await send_notification(DISCORD_CHANNEL_ANIME_ID, update_embed)
            else:
                print("    -> No changes detected.")
            time.sleep(1)
        return True
    except Exception as e:
        print(f"An unexpected error occurred during the main process: {e}")
        return False
    finally:
        driver.quit()
        conn.close()
        check_in_progress = False
        print(f"--- Movie Check Finished [{datetime.now()}] ---")

@bot.event
async def on_ready():
    db.init_db()
    print(f"Logged in as {bot.user}")
    if not check_for_updates.is_running():
        check_for_updates.start()

@tasks.loop(hours=24)
async def check_for_updates():
    await perform_movie_check()

# --- Autocomplete Functions ---
async def movie_autocomplete(ctx: discord.AutocompleteContext):
    conn = db.get_connection()
    titles = db.get_all_movie_titles(conn)
    conn.close()
    return [title for title in titles if ctx.value.lower() in title.lower()][:25]

async def watchlist_autocomplete(ctx: discord.AutocompleteContext):
    conn = db.get_connection()
    items = db.get_user_watchlist(conn, ctx.interaction.user.id)
    conn.close()
    return [item['pattern'] for item in items if ctx.value.lower() in item['pattern'].lower()][:25]

async def ignore_autocomplete(ctx: discord.AutocompleteContext):
    conn = db.get_connection()
    items = db.get_user_ignore_list(conn, ctx.interaction.user.id)
    conn.close()
    return [item['pattern'] for item in items if ctx.value.lower() in item['pattern'].lower()][:25]
    
# --- Bot Commands ---
@bot.slash_command(name="check", description="Manually trigger a check for movie updates.")
@commands.is_owner()
async def force_check(ctx: discord.ApplicationContext):
    global check_in_progress
    
    if check_in_progress:
        await ctx.respond("ℹ️ A check is already in progress. Please wait for it to complete.", ephemeral=True)
        return
        
    await ctx.respond("✅ Manual check initiated...", ephemeral=True)
    success = await perform_movie_check()
    
    if success:
        await ctx.followup.send("✅ Manual check completed successfully!", ephemeral=True)
    else:
        await ctx.followup.send("❌ Manual check encountered an error. Check the logs for details.", ephemeral=True)

@bot.slash_command(name="showtimes", description="Get the full list of showtimes for a specific movie.")
async def get_showtimes_cmd(ctx, movie: discord.Option(str, autocomplete=movie_autocomplete)):
    await ctx.defer()
    conn = db.get_connection(); movie_data = db.get_movie(conn, movie); conn.close()
    if not movie_data:
        await ctx.followup.send(f"❌ Movie '{movie}' not found."); return
    driver = setup_driver()
    try: showtimes = scraper.get_specific_showtimes(driver, movie_data['cinemark_url'])
    finally: driver.quit()
    embed = discord.Embed(title=f"Showtimes for {movie}", url=movie_data['cinemark_url'], color=discord.Color.gold(), description=movie_data['overview'])
    if movie_data['poster_url']: embed.set_image(url=movie_data['poster_url'])
    if "Error" in showtimes or "Notice" in showtimes:
        embed.add_field(name="Status", value=list(showtimes.values())[0])
    else:
        for date, times in sorted(showtimes.items()):
            embed.add_field(name=date, value=" | ".join(times), inline=False)
    await ctx.followup.send(embed=embed)

@watchlist_commands.command(name="add", description="Add a movie to your personal watchlist by its exact title.")
async def watchlist_add(ctx, movie: discord.Option(str, autocomplete=movie_autocomplete)):
    conn = db.get_connection(); success = db.add_to_watchlist(conn, ctx.author.id, movie, is_regex=False); conn.close()
    if success: await ctx.respond(f"✅ **{movie}** added to your watchlist.")
    else: await ctx.respond(f"ℹ️ **{movie}** is already on your watchlist.")

@watchlist_commands.command(name="add_regex", description="Add a movie pattern to your watchlist (e.g., '(?i)tron.*').")
async def watchlist_add_regex(ctx, pattern: str):
    try: re.compile(pattern, re.IGNORECASE)
    except re.error: await ctx.respond("❌ That is not a valid Python Regex pattern.", ephemeral=True); return
    conn = db.get_connection(); success = db.add_to_watchlist(conn, ctx.author.id, pattern, is_regex=True); conn.close()
    if success: await ctx.respond(f"✅ Regex pattern `{pattern}` added to your watchlist.")
    else: await ctx.respond(f"ℹ️ Pattern `{pattern}` is already on your watchlist.")

@watchlist_commands.command(name="remove", description="Remove a movie or pattern from your watchlist.")
async def watchlist_remove(ctx, pattern: discord.Option(str, autocomplete=watchlist_autocomplete)):
    conn = db.get_connection(); success = db.remove_from_watchlist(conn, ctx.author.id, pattern); conn.close()
    if success: await ctx.respond(f"🗑️ **{pattern}** has been removed from your watchlist.")
    else: await ctx.respond(f"❌ Pattern `{pattern}` not found on your watchlist.")

@watchlist_commands.command(name="view", description="View your watchlist.")
async def watchlist_view(ctx: discord.ApplicationContext):
    conn = db.get_connection(); watchlist = db.get_user_watchlist(conn, ctx.author.id); conn.close()
    if not watchlist: await ctx.respond("Your watchlist is empty.", ephemeral=True); return
    description = "\n".join(f"- `{item['pattern']}` {'(Regex)' if item['is_regex'] else ''}" for item in watchlist)
    embed = discord.Embed(title=f"{ctx.author.name}'s Watchlist", description=description, color=discord.Color.blurple())
    await ctx.respond(embed=embed)

@ignore_commands.command(name="add", description="Ignore a movie to stop all processing for it.")
async def ignore_add(ctx, movie: discord.Option(str, autocomplete=movie_autocomplete)):
    conn = db.get_connection(); success = db.add_to_ignore_list(conn, ctx.author.id, movie, is_regex=False); conn.close()
    if success: await ctx.respond(f"🔇 **{movie}** is now on your ignore list. The bot will no longer process updates for it.")
    else: await ctx.respond(f"ℹ️ You are already ignoring **{movie}**.")

@ignore_commands.command(name="add_regex", description="Ignore movies matching a regex pattern (e.g., '.*English Dub.*').")
async def ignore_add_regex(ctx, pattern: str):
    try: re.compile(pattern, re.IGNORECASE)
    except re.error: await ctx.respond("❌ That is not a valid Python Regex pattern.", ephemeral=True); return
    conn = db.get_connection(); success = db.add_to_ignore_list(conn, ctx.author.id, pattern, is_regex=True); conn.close()
    if success: await ctx.respond(f"🔇 Regex pattern `{pattern}` added to your ignore list. Movies matching this pattern will be ignored.")
    else: await ctx.respond(f"ℹ️ Pattern `{pattern}` is already on your ignore list.")

@ignore_commands.command(name="remove", description="Un-ignore a movie to process its updates again.")
async def ignore_remove(ctx, pattern: discord.Option(str, autocomplete=ignore_autocomplete)):
    conn = db.get_connection(); success = db.remove_from_ignore_list(conn, ctx.author.id, pattern); conn.close()
    if success: await ctx.respond(f"🔊 **{pattern}** has been removed from your ignore list.")
    else: await ctx.respond(f"❌ You aren't ignoring **{pattern}**.")

@ignore_commands.command(name="view", description="View your personal ignore list.")
async def ignore_view(ctx: discord.ApplicationContext):
    conn = db.get_connection(); ignore_list = db.get_user_ignore_list(conn, ctx.author.id); conn.close()
    if not ignore_list: await ctx.respond("Your ignore list is empty.", ephemeral=True); return
    description = "\n".join(f"- `{item['pattern']}` {'(Regex)' if item['is_regex'] else ''}" for item in ignore_list)
    embed = discord.Embed(title=f"{ctx.author.name}'s Ignore List", description=description, color=discord.Color.dark_red())
    await ctx.respond(embed=embed)

if __name__ == "__main__":
    if any(k in ('', 'YOUR_DISCORD_BOT_TOKEN', 'YOUR_TMDB_API_KEY_HERE') for k in [BOT_TOKEN, TMDB_API_KEY]) or any(c == 0 for c in [DISCORD_CHANNEL_ANIME_ID, DISCORD_CHANNEL_WATCHLIST_ID]):
        print("FATAL: Please fill in your BOT_TOKEN, TMDB_API_KEY, and ALL REQUIRED Channel IDs in main.py!")
    else:
        bot.run(BOT_TOKEN)
