import os
import mimetypes
from pathlib import Path
from flask import Flask, render_template, request, abort, Response, send_file, url_for
from urllib.parse import quote

# ====== CONFIG ======
MOVIES_ROOT = Path(r"C:\\Users\\pc\\Videos\\Animation").resolve()
ALLOWED_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv"}
APP_TITLE = "Movie Download & Streaming"

app = Flask(__name__, static_folder="static", template_folder="templates")

def human_title(name: str) -> str:
    n = os.path.splitext(os.path.basename(name))[0]
    return n.replace("_", " ").replace("-", " ").strip().title()

def list_movies(root: Path):
    """Scan all subfolders for video files and return a list of dicts."""
    movies = []
    if not root.exists():
        return movies
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in ALLOWED_EXTS:
            rel = p.relative_to(root).as_posix()  # keep forward slashes
            category = p.parent.relative_to(root).as_posix() if p.parent != root else "uncategorized"
            movies.append({
                "identifier": rel,              # e.g. "latest/movie.mp4"
                "title": human_title(p.name),   # display title
                "description": human_title(p.name),
                "poster": "",                   # placeholder (optional future work)
                "category": category,
                "genre": "",                    # can be filled via metadata later
            })
    # sort newest first by mtime
    movies.sort(key=lambda m: (root / m["identifier"]).stat().st_mtime if (root / m["identifier"]).exists() else 0, reverse=True)
    return movies

def get_movie_path(identifier: str) -> Path:
    # secure path join
    target = (MOVIES_ROOT / identifier).resolve()
    if MOVIES_ROOT not in target.parents and MOVIES_ROOT != target:
        abort(400)
    return target

def load_all():
    return list_movies(MOVIES_ROOT)

@app.route("/")
def index():
    movies = load_all()
    return render_template("index.html", movies=movies, title=APP_TITLE)

@app.route("/category/<path:name>")
def category(name):
    movies = [m for m in load_all() if m["category"].split("/", 1)[0].lower() == name.lower()]
    title = f"{name.title()} — {APP_TITLE}"
    return render_template("index.html", movies=movies, title=title)

@app.route("/search")
def search():
    q = request.args.get("q", "").strip().lower()
    movies = load_all()
    if q:
        movies = [m for m in movies if q in m["title"].lower() or q in m["identifier"].lower()]
    return render_template("index.html", movies=movies, title=f"Search: {q or 'All'}")

@app.route("/movie/<path:identifier>")
def movie_detail(identifier):
    movies = load_all()
    movie = next((m for m in movies if m["identifier"] == identifier), None)
    if not movie:
        abort(404)
    # recommendations from same top-level category
    top_cat = movie["category"].split("/", 1)[0]
    recommendations = [m for m in movies if m["identifier"] != identifier and m["category"].split("/", 1)[0] == top_cat][:8]
    # links
    watch_link = url_for("watch_movie", identifier=identifier)
    download_link = url_for("download_movie", identifier=identifier)
    return render_template("movie.html", movie=movie, recommendations=recommendations, watch_link=watch_link, download_link=download_link)

@app.route("/watch/<path:identifier>")
def watch_movie(identifier):
    movie_path = get_movie_path(identifier)
    if not movie_path.exists():
        abort(404)
    # Video src will point to stream endpoint which supports Range
    stream_url = url_for("stream_movie", identifier=identifier)
    title = human_title(movie_path.name)
    return render_template("watch.html", title=title, stream_url=stream_url, back_link=url_for("movie_detail", identifier=identifier))

@app.route("/download/<path:identifier>")
def download_movie(identifier):
    movie_path = get_movie_path(identifier)
    if not movie_path.exists():
        abort(404)
    return send_file(movie_path, as_attachment=True, download_name=os.path.basename(movie_path))

# === HTTP Range streaming for HTML5 video ===
@app.route("/stream/<path:identifier>")
def stream_movie(identifier):
    path = get_movie_path(identifier)
    if not path.exists():
        abort(404)

    range_header = request.headers.get('Range', None)
    file_size = path.stat().st_size
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"

    if range_header:
        # Example Range: bytes=0-1023
        try:
            # Only handle single range
            _, range_spec = range_header.split("=")
            start_str, end_str = range_spec.split("-")
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size - 1
            end = min(end, file_size - 1)
            if start > end or start < 0:
                raise ValueError
        except Exception:
            # Malformed range => ignore and send full content
            start, end = 0, file_size - 1
            content_length = file_size
            status = 200
        else:
            content_length = end - start + 1
            status = 206

        def generate():
            with open(path, "rb") as f:
                f.seek(start)
                remaining = content_length
                chunk = 8192
                while remaining > 0:
                    data = f.read(min(chunk, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        rv = Response(generate(), status=status, mimetype=mime, direct_passthrough=True)
        rv.headers.add('Content-Range', f'bytes {start}-{end}/{file_size}')
        rv.headers.add('Accept-Ranges', 'bytes')
        rv.headers.add('Content-Length', str(content_length))
        return rv

    # No Range header: send full file (not ideal for huge files, but okay)
    return send_file(path, mimetype=mime)

if __name__ == "__main__":
    print(f"[INFO] MOVIES_ROOT is set to: {MOVIES_ROOT}")
    movies = list_movies(MOVIES_ROOT)
    print(f"[INFO] Found {len(movies)} movie(s) in MOVIES_ROOT.")
    # Production hint: use `gunicorn 'app:app'` or `waitress-serve --listen=0.0.0.0:5000 app:app`
    app.run(host="0.0.0.0", port=5000, debug=True)