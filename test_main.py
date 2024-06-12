import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from app import app
from dotenv import load_dotenv
import os

load_dotenv()

user = os.getenv("USERNAME2")
password = os.getenv("PASSWORD2")

client = TestClient(app)

@pytest.mark.asyncio
async def test_get_highlights_no_index():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"/highlights/kknaislova?user={user}&password={password}")
    print("Response:", response.json())
    assert response.status_code == 200
    assert "all_highlights" in response.json()

@pytest.mark.asyncio
async def test_get_highlights_with_index():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"/highlights/kknaislova/0?user={user}&password={password}")
    print("Response:", response.json())
    assert response.status_code == 200
    assert "highlight_urls" in response.json()

@pytest.mark.asyncio
async def test_get_highlights_invalid_index():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"/highlights/kknaislova/999?user={user}&password={password}")
    print("Response:", response.json())
    assert response.status_code == 200
    assert "error" in response.json()
    assert "valid_indexes" in response.json()

@pytest.mark.asyncio
async def test_get_posts_no_skip_no_limit():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"/posts/kknaislova?user={user}&password={password}")
    print("Response:", response.json())
    assert response.status_code == 200
    assert "post_urls" in response.json()

@pytest.mark.asyncio
async def test_get_posts_with_skip_and_limit():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"/posts/kknaislova?user={user}&password={password}&skip=0&limit=5")
    print("Response:", response.json())
    assert response.status_code == 200
    assert "post_urls" in response.json()

@pytest.mark.asyncio
async def test_invalid_credentials():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/highlights/kknaislova?user=invalid_user&password=invalid_pass")
    print("Response:", response.json())
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}
    
    
if __name__ == "__main__":
    print(f"/highlights/kknaislova/0?user={user}&password={password}")