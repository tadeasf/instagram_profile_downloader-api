import os
import time
import requests
import instaloader
from fastapi import FastAPI, HTTPException, Query
from typing import Optional, List
from loguru import logger
from rich.console import Console
from rich.traceback import install
from PIL import Image
import cv2
import yaml

# Install rich traceback handler
install()

# Initialize rich console
console = Console()

# Configure loguru to log to a file
logger.remove()

CONFIG_PATH = os.path.expanduser("~/.config/instagram_profile_downloader/config.yml")

app = FastAPI()

def load_config():
    """Load the configuration file."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as file:
            return yaml.safe_load(file)
    return {}

def generate_log_filename(profile_name):
    # Create the filename from the name of the profile we are downloading + current date - DD/MM/YYYY
    return f"{profile_name}_{time.strftime('%d-%m-%Y')}.log"

def format_size(size):
    # Format size to be in B/KB/MB
    for unit in ["B", "KB", "MB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024

def download_media(url, output_dir):
    try:
        # Ensure the output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Extract filename from URL
        filename = os.path.join(output_dir, url.split("?")[0].split("/")[-1])
        short_filename = os.path.basename(filename)  # Get only the filename

        # Download the media
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(filename, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            logger.info(f"Downloaded {url} to {filename}")

            file_size = os.path.getsize(filename)
            formatted_size = format_size(file_size)

            if filename.lower().endswith((".png", ".jpg", ".jpeg")):
                with Image.open(filename) as img:
                    width, height = img.size
                console.print(
                    f"[cyan bold]Downloaded:[/cyan bold] {short_filename} [magenta]({width}x{height}px, {formatted_size})[/magenta]"
                )
            elif filename.lower().endswith((".mp4", ".avi", ".mov")):
                cap = cv2.VideoCapture(filename)
                fps = cap.get(cv2.CAP_PROP_FPS)
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                duration = total_frames / fps
                console.print(
                    f"[cyan bold]Downloaded:[/cyan bold] {short_filename} [magenta](FPS: {fps:.2f}, Duration: {duration:.2f}s, {formatted_size})[/magenta]"
                )
            else:
                console.print(
                    f"[cyan bold]Downloaded:[/cyan bold] {short_filename} [magenta]({formatted_size})[/magenta]"
                )
        else:
            logger.error(f"Failed to download {url}: HTTP {response.status_code}")
            console.print(
                f"[red]Failed to download {url}: HTTP {response.status_code}[/red]"
            )
    except Exception as e:
        logger.error(f"Failed to download {url}: {e}")
        console.print(f"[red]Failed to download {url}: {e}[/red]")

def authenticate_and_get_loader(user, password, two_factor=False):
    """Authenticate with Instagram and return an Instaloader instance."""
    L = instaloader.Instaloader()

    # Initial Login Attempt
    try:
        L.login(user, password)
    except instaloader.TwoFactorAuthRequiredException:
        if two_factor:
            while True:
                console.print(
                    "[bold yellow]2FA is required. Please enter the 2FA code:[/bold yellow]",
                    end=" ",
                )
                two_factor_code = input().strip()
                try:
                    L.two_factor_login(two_factor_code)
                    console.print("[green]2FA login successful![/green]")
                    break
                except instaloader.exceptions.BadCredentialsException as e:
                    console.print(f"[red]2FA error: {e}. Please try again.[/red]")
        else:
            console.print(
                "[red]2FA is required but --two-factor flag not provided.[/red]"
            )
            raise HTTPException(status_code=401, detail="2FA required but flag not provided")
    except instaloader.exceptions.BadCredentialsException as e:
        console.print(f"[red]Login error: {e}[/red]")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    return L

@app.get("/highlights/{profile_name}/{index_of_highlight}")
@app.get("/highlights/{profile_name}")
async def get_highlights(profile_name: str, index_of_highlight: Optional[int] = None, user: str = Query(...), password: str = Query(...)):
    config = load_config()
    media_root = config.get("download_directory", ".")
    L = authenticate_and_get_loader(user, password)

    try:
        profile = instaloader.Profile.from_username(L.context, profile_name)
        highlights = list(L.get_highlights(profile))

        if index_of_highlight is not None:
            if 0 <= index_of_highlight < len(highlights):
                highlight = highlights[index_of_highlight]
                highlight_media = [item.url for item in highlight.get_items()]
                return {"highlight_urls": highlight_media}
            else:
                return {"error": "Invalid index", "valid_indexes": list(range(len(highlights)))}
        else:
            all_highlights = {}
            for i, highlight in enumerate(highlights):
                all_highlights[i] = [item.url for item in highlight.get_items()]
            return {"all_highlights": all_highlights}
    except Exception as e:
        logger.error(f"Error fetching highlights for profile {profile_name}: {e}")
        console.print(f"[red]Error fetching highlights for profile {profile_name}: {e}[/red]")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.get("/posts/{profile_name}")
async def get_posts(profile_name: str, user: str = Query(...), password: str = Query(...), skip: Optional[int] = 0, limit: Optional[int] = None):
    config = load_config()
    media_root = config.get("download_directory", ".")
    L = authenticate_and_get_loader(user, password)

    try:
        profile = instaloader.Profile.from_username(L.context, profile_name)
        posts = list(profile.get_posts())[skip:skip + limit] if limit else list(profile.get_posts())[skip:]
        post_media = []

        for post in posts:
            if post.typename == "GraphImage":
                post_media.append(post.url)
            elif post.typename == "GraphVideo":
                post_media.append(post.video_url)
            elif post.typename == "GraphSidecar":
                for sidecar in post.get_sidecar_nodes():
                    post_media.append(sidecar.video_url if sidecar.is_video else sidecar.display_url)
        
        return {"post_urls": post_media}
    except Exception as e:
        logger.error(f"Error fetching posts for profile {profile_name}: {e}")
        console.print(f"[red]Error fetching posts for profile {profile_name}: {e}[/red]")
        raise HTTPException(status_code=500, detail="Internal Server Error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)