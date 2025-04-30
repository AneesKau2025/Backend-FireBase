import pytest
import httpx
import time

BASE_URL = "http://127.0.0.1:8000/api"

CHILD_USERNAME = "testchild_unique_123"
CHILD_PASSWORD = "test1234"
FRIEND_USERNAME = "friendchild_unique_456"


def print_separator():
    print("\n" + "-" * 80 + "\n")

def log_response(title, response, start):
    print(f"🧪 {title}")
    print(f"⏱️ Duration: {time.time() - start:.2f} seconds")
    print(f"📦 Status Code: {response.status_code}")
    try:
        print(f"📄 Response: {response.json()}")
    except Exception:
        print(f"📄 Raw Response: {response.text}")
    print_separator()

@pytest.mark.asyncio
async def test_child_endpoints():
    async with httpx.AsyncClient() as client:

        # 1. Child Login (valid)
        start = time.time()
        response = await client.post(f"{BASE_URL}/child/login", data={
            "username": CHILD_USERNAME,
            "password": CHILD_PASSWORD
        })
        child_token = None
        if response.status_code == 200:
            child_token = response.json().get("access_token")
        log_response("1. Child Login (Valid)", response, start)

        # 2. Child Login (invalid)
        start = time.time()
        response = await client.post(f"{BASE_URL}/child/login", data={
            "username": CHILD_USERNAME,
            "password": "wrongpass"
        })
        log_response("2. Child Login (Invalid)", response, start)

        # 3. Add Friend Request
        start = time.time()
        response = await client.post(f"{BASE_URL}/child/friend/request", headers={
            "Authorization": f"Bearer {child_token}"
        }, json={"receiverChildUserName": FRIEND_USERNAME})
        log_response("3. Add Friend Request", response, start)

        # 4. Send Message
        start = time.time()
        response = await client.post(f"{BASE_URL}/child/message", headers={
            "Authorization": f"Bearer {child_token}"
        }, json={
            "senderChildUserName": CHILD_USERNAME,
            "receiverChildUserName": FRIEND_USERNAME,
            "content": "Hello, this is a test message."
        })
        log_response("4. Send Message", response, start)

        # 5. Block Friend
        start = time.time()
        response = await client.post(f"{BASE_URL}/child/friend/block/{FRIEND_USERNAME}", headers={
            "Authorization": f"Bearer {child_token}"
        })
        log_response("5. Block Friend", response, start)
