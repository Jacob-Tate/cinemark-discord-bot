import re
import requests
import time
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from datetime import datetime
import os

ANIME_KEYWORD_ID = 210024
THEATER_URL = os.getenv('THEATER_URL')
COMING_SOON_URL = "https://www.cinemark.com/movies/coming-soon"
NOW_PLAYING_URL = "https://www.cinemark.com/movies/now-playing"
EVENTS_URL = "https://www.cinemark.com/movies/events"

# Known anime studios and distributors for fallback detection
ANIME_STUDIOS = [
    'studio ghibli', 'toei animation', 'madhouse', 'pierrot', 'bones', 'mappa',
    'wit studio', 'trigger', 'kyoani', 'kyoto animation', 'a-1 pictures',
    'cloverworks', 'ufotable', 'production i.g', 'sunrise', 'shaft',
    'j.c.staff', 'white fox', 'doga kobo', 'studio deen', 'gonzo'
]

ANIME_DISTRIBUTORS = [
    'funimation', 'crunchyroll', 'aniplex', 'viz media', 'sentai filmworks',
    'eleven arts', 'shout factory', 'discotek media'
]

def scrape_all_movies(driver):
    driver.get(THEATER_URL)
    print("Setting theater location...")
    time.sleep(5)
    coming_soon = _scrape_movie_list_page(driver, COMING_SOON_URL, "Coming Soon")
    now_playing = _scrape_movie_list_page(driver, NOW_PLAYING_URL, "Now Playing")
    events = _scrape_movie_list_page(driver, EVENTS_URL, "Events")
    all_movies = {movie['title']: movie for movie in coming_soon + now_playing + events}
    return list(all_movies.values())

def _scrape_movie_list_page(driver, url, page_name):
    print(f"\nNavigating to '{page_name}' page: {url}")
    driver.get(url)
    time.sleep(10)
    print(f"Scraping movie data from '{page_name}' page...")
    movie_blocks = driver.find_elements(By.CLASS_NAME, 'movieBlock')
    movies_data = []
    for block in movie_blocks:
        try:
            title = block.find_element(By.CLASS_NAME, 'title').text
            release_date_str = block.get_attribute('data-movie-releasedate')
            poster_link = block.find_element(By.CLASS_NAME, 'movie-poster')
            movie_url = poster_link.get_attribute('href')
            poster_img = poster_link.find_element(By.TAG_NAME, 'img')
            poster_url = poster_img.get_attribute('data-srcset') or poster_img.get_attribute('src')
            try: formatted_date = datetime.strptime(release_date_str, '%m/%d/%Y %I:%M:%S %p').strftime('%Y-%m-%d')
            except (ValueError, TypeError): formatted_date = "N/A"
            movies_data.append({'title': title, 'release_date': formatted_date, 'cinemark_url': movie_url, 'poster_url': poster_url})
        except Exception: continue
    print(f"Found {len(movies_data)} movies on this page.")
    return movies_data

def get_specific_showtimes(driver, movie_url):
    if not movie_url or 'cinemark.com' not in movie_url: return {"Error": "Invalid URL"}
    print(f"    -> Visiting movie page for specific showtimes: {movie_url}")
    driver.get(movie_url)
    time.sleep(5)
    showtimes_by_date = {}
    try:
        date_links = driver.find_elements(By.CSS_SELECTOR, '#showdatesCarousel .showdate-link')
        if not date_links: return {"Notice": "Showtimes not available yet."}
        for i in range(len(date_links)):
            current_date_link = driver.find_elements(By.CSS_SELECTOR, '#showdatesCarousel .showdate-link')[i]
            date_text = current_date_link.text.replace('\n', ' ')
            current_date_link.click(); time.sleep(2)
            time_elements = driver.find_elements(By.CSS_SELECTOR, '#theaterList .showtime-link')
            times = [t.text for t in time_elements if t.text]
            if times: showtimes_by_date[date_text] = sorted(list(set(times)))
        return showtimes_by_date if showtimes_by_date else {"Notice": "No showtimes listed for available dates."}
    except Exception: return {"Error": "Could not scrape showtimes."}

def clean_movie_title(title):
    """Clean movie title for TMDB search, removing format indicators and event suffixes."""
    cleaned = re.sub(r'\s*\(.*\)', '', title).strip()
    
    # Remove quality indicators like "4K", "IMAX", "3D", etc.
    cleaned = re.sub(r'\s+(4K|IMAX|3D|HDR|Dolby)\b', '', cleaned, flags=re.IGNORECASE).strip()
    
    if ':' in cleaned:
        base, edition = cleaned.split(':', 1)
        if any(kw in edition.lower() for kw in ['anniversary', 'imax', 'exclusive', 'remastered', "director's cut", 'fathom']):
            return base.strip()
    
    if '|' in cleaned:
        base, edition = cleaned.split('|', 1)
        if any(kw in edition.lower() for kw in ['studio ghibli fest', 'ghibli fest', 'anime night', 'fathom events']):
            return base.strip()
    
    return cleaned

def is_anime_by_title_patterns(original_title, cleaned_title):
    """Check if a movie is anime based on title patterns and known indicators."""
    original_lower = original_title.lower()
    cleaned_lower = cleaned_title.lower()
    
    # Check for Studio Ghibli specifically
    if 'studio ghibli' in original_lower or 'ghibli' in original_lower:
        return True
    
    # Check for known anime studios in the title
    for studio in ANIME_STUDIOS:
        if studio in original_lower:
            return True
    
    # Check for known anime distributors
    for distributor in ANIME_DISTRIBUTORS:
        if distributor in original_lower:
            return True
    
    # Check for anime-specific patterns
    anime_patterns = [
        r'japanese\s+with\s+english\s+subtitles',
        r'english\s+dub(bed)?',
        r'anime\s+(movie|film|night)',
        r'(sub|dub)\s*\|',
        r'\|\s*(sub|dub)',
    ]
    
    for pattern in anime_patterns:
        if re.search(pattern, original_lower):
            return True
    
    return False

def get_tmdb_details(title, api_key):
    """Fetches details, checks for anime keyword, and gets overview in one go."""
    cleaned_title = clean_movie_title(title)
    
    # First check if it's anime by title patterns (fallback detection)
    is_anime_by_pattern = is_anime_by_title_patterns(title, cleaned_title)
    
    try:
        search_url = f"https://api.themoviedb.org/3/search/movie?api_key={api_key}&query={cleaned_title}"
        search_res = requests.get(search_url); search_res.raise_for_status()
        results = search_res.json()['results']
        if not results: 
            # If no results but we detected anime by pattern, still return as anime
            if is_anime_by_pattern:
                return None, True, "Animation", "Anime movie detected by title pattern."
            return None, False, "N/A", "N/A"

        movie_details = results[0]
        movie_id = movie_details.get('id')
        
        # Get overview and truncate if necessary
        overview = movie_details.get('overview', 'No description available.')
        if len(overview) > 500:
            overview = overview[:497] + '...'

        genres_url = f"https://api.themoviedb.org/3/genre/movie/list?api_key={api_key}"
        genres_res = requests.get(genres_url); genres_res.raise_for_status()
        genre_map = {g['id']: g['name'] for g in genres_res.json()['genres']}
        genres = [genre_map.get(gid, '?') for gid in movie_details.get('genre_ids', [])]

        is_anime_by_keyword = False
        if movie_id:
            keywords_url = f"https://api.themoviedb.org/3/movie/{movie_id}/keywords?api_key={api_key}"
            kw_res = requests.get(keywords_url); kw_res.raise_for_status()
            is_anime_by_keyword = any(kw['id'] == ANIME_KEYWORD_ID for kw in kw_res.json().get('keywords', []))
        
        # Final anime determination: either TMDB keyword OR pattern detection
        is_anime = is_anime_by_keyword or is_anime_by_pattern
        
        return movie_details, is_anime, ", ".join(genres), overview
    except requests.exceptions.RequestException:
        # If API fails but we detected anime by pattern, still return as anime
        if is_anime_by_pattern:
            return None, True, "Animation", "Anime movie detected by title pattern (API error)."
        return None, False, "API Error", "API Error"
