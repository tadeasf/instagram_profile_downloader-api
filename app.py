import os
import time
import requests
import instaloader
from fastapi import FastAPI, HTTPException, Query
from typing import Optional
from loguru import logger
from rich.console import Console
from rich.traceback import install

# Install rich traceback handler
install()

# Initialize rich console
console = Console()

# Configure loguru to log to a file
logger.remove()

app = FastAPI()

# Global variables to track request statistics
requests_succeeded = 0
requests_failed = 0

def increment_succeeded():
    global requests_succeeded
    requests_succeeded += 1

def increment_failed():
    global requests_failed
    requests_failed += 1

def reset_stats():
    global requests_succeeded, requests_failed
    requests_succeeded = 0
    requests_failed = 0

# Schedule reset of stats every hour
import threading

def schedule_reset():
    threading.Timer(3600, schedule_reset).start()
    reset_stats()

schedule_reset()

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
    L = authenticate_and_get_loader(user, password)

    try:
        profile = instaloader.Profile.from_username(L.context, profile_name)
        highlights = list(L.get_highlights(profile))

        if index_of_highlight is not None:
            if 0 <= index_of_highlight < len(highlights):
                highlight = highlights[index_of_highlight]
                highlight_media = [item.url for item in highlight.get_items()]
                increment_succeeded()
                return {"highlight_urls": highlight_media}
            else:
                increment_failed()
                return {"error": "Invalid index", "valid_indexes": list(range(len(highlights)))}
        else:
            all_highlights = {}
            for i, highlight in enumerate(highlights):
                all_highlights[i] = [item.url for item in highlight.get_items()]
            increment_succeeded()
            return {"all_highlights": all_highlights}
    except Exception as e:
        increment_failed()
        logger.error(f"Error fetching highlights for profile {profile_name}: {e}")
        console.print(f"[red]Error fetching highlights for profile {profile_name}: {e}[/red]")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.get("/posts/{profile_name}")
async def get_posts(profile_name: str, user: str = Query(...), password: str = Query(...), skip: Optional[int] = 0, limit: Optional[int] = None):
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
        
        increment_succeeded()
        return {"post_urls": post_media}
    except Exception as e:
        increment_failed()
        logger.error(f"Error fetching posts for profile {profile_name}: {e}")
        console.print(f"[red]Error fetching posts for profile {profile_name}: {e}[/red]")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.get("/profile_contents/{profile_name}")
async def get_profile_contents(profile_name: str, user: str = Query(...), password: str = Query(...)):
    L = authenticate_and_get_loader(user, password)

    try:
        profile = instaloader.Profile.from_username(L.context, profile_name)
        highlights = list(L.get_highlights(profile))
        posts = list(profile.get_posts())

        highlight_info = [{"name": h.title, "number_of_items": len(list(h.get_items()))} for h in highlights]
        post_info = {"number_of_posts": len(posts)}

        increment_succeeded()
        return {"highlights": highlight_info, "posts": post_info}
    except Exception as e:
        increment_failed()
        logger.error(f"Error fetching profile contents for profile {profile_name}: {e}")
        console.print(f"[red]Error fetching profile contents for profile {profile_name}: {e}[/red]")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.get("/")
async def root():
    return {
        "requests_succeeded": requests_succeeded,
        "requests_failed": requests_failed,
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)