
import requests
from flask import Flask, render_template, request, abort, url_for

APP_TITLE = "TMDB Movie Explorer"
TMDB_API_KEY = "72669aae995afd81bab6bb70df77710c"
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

app = Flask(__name__, static_folder="static", template_folder="templates")

def get_trending_movies():
    url = f"{TMDB_BASE_URL}/trending/movie/week"
    params = {"api_key": TMDB_API_KEY}
    r = requests.get(url, params=params)
    if r.status_code == 200:
        movies = r.json().get("results", [])
        return [format_tmdb_movie(m) for m in movies]
    return []

def search_movies(query):
    url = f"{TMDB_BASE_URL}/search/movie"
    params = {"api_key": TMDB_API_KEY, "query": query}
    r = requests.get(url, params=params)
    if r.status_code == 200:
        movies = r.json().get("results", [])
        return [format_tmdb_movie(m) for m in movies]
    return []

def get_movie_details(movie_id):
    url = f"{TMDB_BASE_URL}/movie/{movie_id}"
    params = {"api_key": TMDB_API_KEY}
    r = requests.get(url, params=params)
    if r.status_code == 200:
        return format_tmdb_movie(r.json())
    return None

def format_tmdb_movie(m):
    return {
        "id": m.get("id"),
        "title": m.get("title"),
        "description": m.get("overview", "No description available."),
        "poster": f"{TMDB_IMAGE_BASE}{m['poster_path']}" if m.get("poster_path") else url_for('static', filename='default-poster.jpg'),
        "category": m.get("release_date", "Unknown"),
        "genre": ", ".join([g["name"] for g in m.get("genres", [])]) if m.get("genres") else "",
        "release_date": m.get("release_date", "Unknown"),
        "vote_average": m.get("vote_average", "N/A"),
    }

@app.route("/")
def index():
    movies = get_trending_movies()
    return render_template("index.html", movies=movies, title=APP_TITLE)


# Remove category route (TMDB does not use folder categories)

@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    movies = search_movies(q) if q else get_trending_movies()
    return render_template("index.html", movies=movies, title=f"Search: {q or 'Trending'}")

@app.route("/movie/<int:movie_id>")
def movie_detail(movie_id):
    movie = get_movie_details(movie_id)
    if not movie:
        abort(404)
    # For recommendations, show trending movies except the current one
    recommendations = [m for m in get_trending_movies() if m["id"] != movie_id][:8]
    return render_template("movie.html", movie=movie, recommendations=recommendations)


# Remove watch, download, and stream routes (not applicable for TMDB API)

if __name__ == "__main__":
    print(f"[INFO] TMDB Movie Explorer started.")
    app.run(host="0.0.0.0", port=5000, debug=True)