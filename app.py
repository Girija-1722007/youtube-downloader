from flask import Flask, render_template, request, redirect, url_for, session, send_file, abort
from urllib.parse import unquote
import yt_dlp
import os
import time

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_cse_app'

# Directory to save downloaded files
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Optional: Path to ffmpeg (if needed)
FFMPEG_PATH = os.path.join(os.path.dirname(__file__), "bin")

# Initialize download history
DOWNLOAD_HISTORY = []

# Progress hook
def progress_hook(d):
    if d['status'] == 'downloading':
        print(f"Downloading: {d.get('_percent_str', '0%')}")
    elif d['status'] == 'finished':
        print(f"Download finished: {d['filename']}")

# Function to download video
def perform_download(url, category):
    category_dir = os.path.join(DOWNLOAD_DIR, category)
    os.makedirs(category_dir, exist_ok=True)
    filename_template = os.path.join(category_dir, '%(title)s.%(ext)s')

    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'outtmpl': filename_template,
        'noplaylist': True,
        'progress_hooks': [progress_hook],
    }

    if os.path.exists(FFMPEG_PATH):
        ydl_opts['ffmpeg_location'] = FFMPEG_PATH

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'Unknown Title')
            saved_file = ydl.prepare_filename(info)

            # Record history
            rel_path = os.path.relpath(saved_file, os.getcwd())
            DOWNLOAD_HISTORY.append({
                'url': url,
                'title': title,
                'category': category,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'filepath': rel_path
            })

            return f"✅ Successfully downloaded: {title}", None, rel_path

    except Exception as e:
        error = str(e)
        if "ffmpeg" in error.lower():
            return None, "⚠️ ffmpeg not found or misconfigured.", None
        if "Sign in" in error or "authentication" in error:
            return None, "⚠️ YouTube requires login/cookies.", None
        return None, f"❌ Error: {error}", None

# --- ROUTES ---

@app.route("/", methods=["GET", "POST"])
def verify_email():
    msg = ""
    if request.method == "POST":
        email = request.form.get("email")
        if email:
            session['user_email'] = email
            return redirect(url_for('select_category'))
        msg = "Please enter a valid email."
    return render_template("verify_email.html", msg=msg)


@app.route("/select")
def select_category():
    if 'user_email' not in session:
        return redirect(url_for('verify_email'))
    return render_template("select_category.html")


@app.route("/download/<category>", methods=["GET", "POST"])
def download_content(category):
    if 'user_email' not in session:
        return redirect(url_for('verify_email'))
    if category not in ['educational', 'entertainment']:
        return "Invalid category.", 404

    download_msg = ""
    error_msg = ""
    download_link = None

    if request.method == "POST":
        url = request.form.get("url")
        if url:
            download_msg, error_msg, saved_file = perform_download(url, category)
            if saved_file and os.path.exists(saved_file):
                download_link = url_for('get_file', filepath=saved_file)
        else:
            error_msg = "Please paste a YouTube URL."

    return render_template(
        "download.html",
        category=category.capitalize(),
        download_msg=download_msg,
        error_msg=error_msg,
        download_link=download_link
    )


@app.route("/history")
def download_history():
    if 'user_email' not in session:
        return redirect(url_for('verify_email'))
    return render_template("history.html", history=DOWNLOAD_HISTORY)


@app.route("/get_file")
def get_file():
    filepath = request.args.get("filepath")
    if not filepath:
        abort(404)

    filepath = unquote(filepath)
    abs_path = os.path.abspath(filepath)

    # Security check: must be inside DOWNLOAD_DIR
    if not abs_path.startswith(os.path.abspath(DOWNLOAD_DIR)):
        abort(403)

    if os.path.exists(abs_path):
        return send_file(abs_path, as_attachment=True)
    else:
        abort(404)
# --- RUN APP ---

if __name__ == "__main__":
    app.run(debug=True)

 