from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from typing import Optional
from loguru import logger
from rich.console import Console
from rich.traceback import install
import instaloader
import threading
import os

# Install rich traceback handler
install()

# Initialize rich console
console = Console()

def get_filename():
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d")

log_filename = get_filename()
log_filename_str = f"logs/{log_filename}.log"

# Configure loguru to log to a file
logger.remove()
logger.add(log_filename_str, rotation="00:00", retention="7 days", enqueue=True)

app = FastAPI(
    title="Instagram Scraper API",
    description="A simple API to scrape Instagram highlights and posts",
    version="0.1.0",
    docs_url="/",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Global variables to track request statistics
requests_succeeded = 0
requests_failed = 0

INSTALOADER_SESSION_FILE = "session-file"

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

def schedule_reset():
    threading.Timer(3600, schedule_reset).start()
    reset_stats()

schedule_reset()

def authenticate_and_get_loader(user, password, two_factor=False):
    """Authenticate with Instagram and return an Instaloader instance."""
    L = instaloader.Instaloader()

    # Load session if available
    if os.path.isfile(INSTALOADER_SESSION_FILE):
        console.print("[blue]Loading session from file...[/blue]")
        try:
            L.load_session_from_file(user, INSTALOADER_SESSION_FILE)
            console.print("[green]Session loaded successfully from file.[/green]")
            return L
        except Exception as e:
            console.print(f"[red]Error loading session from file: {e}[/red]")
            logger.error(f"Error loading session from file: {e}")

    # Initial Login Attempt
    try:
        L.login(user, password)
        # Save session to file
        L.save_session_to_file(INSTALOADER_SESSION_FILE)
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
                    L.save_session_to_file(INSTALOADER_SESSION_FILE)
                    break
                except instaloader.exceptions.BadCredentialsException as e:
                    console.print(f"[red]2FA error: {e}. Please try again.[/red]")
        else:
            console.print(
                "[red]2FA is required but --two-factor flag not provided.[/red]"
            )
            raise HTTPException(
                status_code=401, detail="2FA required but flag not provided"
            )
    except instaloader.exceptions.BadCredentialsException as e:
        console.print(f"[red]Login error: {e}[/red]")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    except instaloader.exceptions.ConnectionException as e:
        logger.error(f"ConnectionException encountered: {e}")
        raise HTTPException(
            status_code=503,
            detail="Service Unavailable due to connection issues."
        )

    return L

@app.get("/highlights/{profile_name}/{index_of_highlight}")
@app.get("/highlights/{profile_name}")
async def get_highlights(
    profile_name: str,
    index_of_highlight: Optional[int] = None,
    user: str = Query(...),
    password: str = Query(...),
):
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
                return {
                    "error": "Invalid index",
                    "valid_indexes": list(range(len(highlights))),
                }
        else:
            all_highlights = {}
            for i, highlight in enumerate(highlights):
                all_highlights[i] = [item.url for item in highlight.get_items()]
            increment_succeeded()
            return {"all_highlights": all_highlights}
    except instaloader.exceptions.ProfileNotExistsException:
        increment_failed()
        logger.error(f"Profile {profile_name} does not exist.")
        console.print(f"[red]Profile {profile_name} does not exist.[/red]")
        raise HTTPException(status_code=404, detail="Profile not found")
    except instaloader.exceptions.ConnectionException as e:
        increment_failed()
        logger.error(
            f"Connection error while fetching highlights for profile {profile_name}: {e}"
        )
        console.print(
            f"[red]Connection error while fetching highlights for profile {profile_name}: {e}[/red]"
        )
        raise HTTPException(status_code=503, detail="Service Unavailable")
    except instaloader.exceptions.InstaloaderException as e:
        increment_failed()
        logger.error(
            f"Instaloader encountered an error for profile {profile_name}: {e}"
        )
        console.print(
            f"[red]Instaloader encountered an error for profile {profile_name}: {e}[/red]"
        )
        raise HTTPException(status_code=400, detail="Bad Request")
    except Exception as e:
        increment_failed()
        logger.error(f"Error fetching highlights for profile {profile_name}: {e}")
        console.print(
            f"[red]Error fetching highlights for profile {profile_name}: {e}[/red]"
        )
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.get("/posts/{profile_name}")
async def get_posts(
    profile_name: str,
    user: str = Query(...),
    password: str = Query(...),
    skip: Optional[int] = 0,
    limit: Optional[int] = None,
):
    L = authenticate_and_get_loader(user, password)

    try:
        profile = instaloader.Profile.from_username(L.context, profile_name)
        console.print(
            f"Fetching posts for profile: {profile_name} with skip: {skip} and limit: {limit}"
        )
        logger.info(
            f"Fetching posts for profile: {profile_name} with skip: {skip} and limit: {limit}"
        )

        posts = (
            list(profile.get_posts())[skip : skip + limit]
            if limit
            else list(profile.get_posts())[skip:]
        )
        post_media = []

        for post in posts:
            if post.is_video:
                post_media.append(post.video_url)
            else:
                post_media.append(post.url)

        increment_succeeded()
        return {"post_urls": post_media}
    except instaloader.exceptions.ProfileNotExistsException:
        increment_failed()
        logger.error(f"Profile {profile_name} does not exist.")
        console.print(f"[red]Profile {profile_name} does not exist.[/red]")
        raise HTTPException(status_code=404, detail="Profile not found")
    except instaloader.exceptions.ConnectionException as e:
        increment_failed()
        logger.error(f"Connection error while fetching profile {profile_name}: {e}")
        console.print(
            f"[red]Connection error while fetching profile {profile_name}: {e}[/red]"
        )
        raise HTTPException(status_code=503, detail="Service Unavailable")
    except instaloader.exceptions.QueryReturnedNotFoundException as e:
        increment_failed()
        logger.error(f"Query returned not found for profile {profile_name}: {e}")
        console.print(
            f"[red]Query returned not found for profile {profile_name}: {e}[/red]"
        )
        raise HTTPException(status_code=404, detail="Content not found")
    except instaloader.exceptions.InstaloaderException as e:
        increment_failed()
        logger.error(
            f"Instaloader encountered an error for profile {profile_name}: {e}"
        )
        console.print(
            f"[red]Instaloader encountered an error for profile {profile_name}: {e}[/red]"
        )
        raise HTTPException(status_code=400, detail="Bad Request")
    except Exception as e:
        increment_failed()
        logger.error(f"Error fetching posts for profile {profile_name}: {e}")
        console.print(
            f"[red]Error fetching posts for profile {profile_name}: {e}[/red]"
        )
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.get("/profile_contents/{profile_name}")
async def get_profile_contents(
    profile_name: str, user: str = Query(...), password: str = Query(...)
):
    L = authenticate_and_get_loader(user, password)

    try:
        profile = instaloader.Profile.from_username(L.context, profile_name)
        highlights = list(L.get_highlights(profile))
        posts = list(profile.get_posts())

        highlight_info = [
            {"name": h.title, "number_of_items": len(list(h.get_items()))}
            for h in highlights
        ]
        post_info = {"number_of_posts": len(posts)}

        increment_succeeded()
        return {"highlights": highlight_info, "posts": post_info}
    except instaloader.exceptions.ProfileNotExistsException:
        increment_failed()
        logger.error(f"Profile {profile_name} does not exist.")
        console.print(f"[red]Profile {profile_name} does not exist.[/red]")
        raise HTTPException(status_code=404, detail="Profile not found")
    except instaloader.exceptions.ConnectionException as e:
        increment_failed()
        logger.error(f"Connection error while fetching profile {profile_name}: {e}")
        console.print(
            f"[red]Connection error while fetching profile {profile_name}: {e}[/red]"
        )
        raise HTTPException(status_code=503, detail="Service Unavailable")
    except Exception as e:
        increment_failed()
        logger.error(f"Error fetching profile contents for profile {profile_name}: {e}")
        console.print(
            f"[red]Error fetching profile contents for profile {profile_name}: {e}[/red]"
        )
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/download_session")
async def download_session():
    if os.path.isfile(INSTALOADER_SESSION_FILE):
        return FileResponse(
            INSTALOADER_SESSION_FILE,
            media_type="application/octet-stream",
            filename=INSTALOADER_SESSION_FILE,
        )
    else:
        raise HTTPException(status_code=404, detail="Session file not found")


@app.delete("/reset_stats")
async def reset_stats_endpoint():
    reset_stats()
    return {"status": "success"}


@app.get("/stats")
async def get_stats():
    return {
        "requests_succeeded": requests_succeeded,
        "requests_failed": requests_failed,
    }


@app.get("/session/delete")
async def delete_session():
    if os.path.isfile(INSTALOADER_SESSION_FILE):
        os.remove(INSTALOADER_SESSION_FILE)
        return {"status": "success"}
    else:
        raise HTTPException(status_code=404, detail="Session file not found")


@app.get("/session")
async def get_session():
    if os.path.isfile(INSTALOADER_SESSION_FILE):
        return FileResponse(
            INSTALOADER_SESSION_FILE,
            media_type="application/octet-stream",
            filename=INSTALOADER_SESSION_FILE,
        )
    else:
        raise HTTPException(status_code=404, detail="Session file not found")


@app.get("/auth")
async def auth(user: str = Query(...), password: str = Query(...)):
    L = authenticate_and_get_loader(user, password)  # noqa: F841
    return {"status": "success"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
    # uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True)