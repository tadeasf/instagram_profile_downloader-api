import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from app import app
from dotenv import load_dotenv
import os
import sys

load_dotenv()

user = os.getenv("USERNAME2")
password = os.getenv("PASSWORD2")

client = TestClient(app)

@pytest.mark.asyncio
async def test_get_highlights_no_index():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"/highlights/kknaislova?user={user}&password={password}")
    print("Response (highlights, no index):", response.json())
    assert response.status_code == 200
    assert "all_highlights" in response.json()

@pytest.mark.asyncio
async def test_get_highlights_with_index():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"/highlights/kknaislova/0?user={user}&password={password}")
    print("Response (highlights with index):", response.json())
    assert response.status_code == 200
    assert "highlight_urls" in response.json()

@pytest.mark.asyncio
async def test_get_highlights_invalid_index():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"/highlights/kknaislova/999?user={user}&password={password}")
    print("Response (invalid highlight index):", response.json())
    assert response.status_code == 200
    assert "error" in response.json()
    assert "valid_indexes" in response.json()

@pytest.mark.asyncio
async def test_get_posts_no_skip_no_limit():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"/posts/kknaislova?user={user}&password={password}")
    print("Response (posts, no skip, no limit):", response.json())
    assert response.status_code == 200
    assert "post_urls" in response.json()

@pytest.mark.asyncio
async def test_get_posts_with_skip_and_limit():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"/posts/kknaislova?user={user}&password={password}&skip=0&limit=5")
    print("Response (posts with skip and limit):", response.json())
    assert response.status_code == 200
    assert "post_urls" in response.json()

@pytest.mark.asyncio
async def test_get_profile_contents():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"/profile_contents/kknaislova?user={user}&password={password}")
    print("Response (profile contents):", response.json())
    assert response.status_code == 200
    assert "highlights" in response.json()
    assert "posts" in response.json()

@pytest.mark.asyncio
async def test_invalid_credentials():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/highlights/kknaislova?user=invalid_user&password=invalid_pass")
    print("Response (invalid credentials):", response.json())
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}

@pytest.mark.asyncio
async def test_root():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/")
    print("Response (root):", response.json())
    assert response.status_code == 200
    assert "requests_succeeded" in response.json()
    assert "requests_failed" in response.json()

@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    print("Response (health):", response.json())
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

if __name__ == "__main__":
    pytest.main()
    sys.exit()