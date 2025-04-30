import pytest
import httpx
import time

BASE_URL = "http://127.0.0.1:8000/api"

# بيانات الأب التجريبية
PARENT_USERNAME = "testparent_unique_123"
PARENT_PASSWORD = "test1234"
PARENT_EMAIL = "testparent_unique_123@example.com"

CHILD_USERNAME = "testchild_unique_123"
CHILD_PASSWORD = "test1234"
CHILD_EMAIL = "testchild_unique_123@example.com"

# أدوات الطباعة

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
async def test_parent_endpoints():
    async with httpx.AsyncClient() as client:

        # 1. Parent Signup
        start = time.time()
        response = await client.post(f"{BASE_URL}/parent/signup", json={
            "parentUserName": PARENT_USERNAME,
            "passwordHash": PARENT_PASSWORD,
            "firstName": "Test",
            "lastName": "Parent",
            "email": PARENT_EMAIL
        })
        log_response("1. Parent Signup", response, start)
        assert response.status_code == 200, "Parent signup failed"

        # 2. Parent Login (Valid)
        start = time.time()
        response = await client.post(
            f"{BASE_URL}/parent/login",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "username": PARENT_USERNAME,
                "password": PARENT_PASSWORD,
                "grant_type": "password"
            }
        )
        assert response.status_code == 200, "Parent login failed"
        parent_token = response.json().get("access_token")
        log_response("2. Parent Login (Valid)", response, start)

        # 3. Parent Login (Invalid)
        start = time.time()
        response = await client.post(
            f"{BASE_URL}/parent/login",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "username": PARENT_USERNAME,
                "password": "wrongpass",
                "grant_type": "password"
            }
        )
        log_response("3. Parent Login (Invalid)", response, start)
        assert response.status_code == 401, "Invalid login should fail"

        # 4. Add Child
        start = time.time()
        response = await client.post(
            f"{BASE_URL}/parent/children/add",
            headers={"Authorization": f"Bearer {parent_token}"},
            json={
                "childUserName": CHILD_USERNAME,
                "passwordHash": CHILD_PASSWORD,
                "firstName": "Child",
                "lastName": "User",
                "email": CHILD_EMAIL,
                "dateOfBirth": "2014-05-01",
                "timeControl": 60,
                "parentUserName": PARENT_USERNAME,
                "profileIcon": "default.png"
            }
        )
        log_response("4. Add Child", response, start)
        assert response.status_code == 200, "Child creation failed"

        # 5. Set Usage Time Limit
        start = time.time()
        response = await client.put(
            f"{BASE_URL}/parent/children/{CHILD_USERNAME}/usage/set",
            headers={"Authorization": f"Bearer {parent_token}"},
            json={"minutes": 60}
        )
        log_response("5. Set Usage Time Limit", response, start)
        assert response.status_code == 200, "Setting usage time failed"

        # 6. Get Child Usage
        start = time.time()
        response = await client.get(
            f"{BASE_URL}/parent/children/{CHILD_USERNAME}/usage",
            headers={"Authorization": f"Bearer {parent_token}"}
        )
        log_response("6. Get Child Usage", response, start)
        assert response.status_code == 200, "Getting child usage failed"

        # 7. Get Parent Info
        start = time.time()
        response = await client.get(
            f"{BASE_URL}/parent/info",
            headers={"Authorization": f"Bearer {parent_token}"}
        )
        log_response("7. Get Parent Info", response, start)
        assert response.status_code == 200, "Getting parent info failed"

        # 8. Get All Children
        start = time.time()
        response = await client.get(
            f"{BASE_URL}/parent/children",
            headers={"Authorization": f"Bearer {parent_token}"}
        )
        log_response("8. Get All Children", response, start)
        assert response.status_code == 200, "Getting children list failed"

        # 9. Get Notifications
        start = time.time()
        response = await client.get(
            f"{BASE_URL}/parent/notifications",
            headers={"Authorization": f"Bearer {parent_token}"}
        )
        log_response("9. Get Notifications", response, start)
        assert response.status_code == 200, "Getting notifications failed"

        # 10. Parent Logout
        start = time.time()
        response = await client.post(
            f"{BASE_URL}/parent/logout",
            headers={"Authorization": f"Bearer {parent_token}"}
        )
        log_response("10. Parent Logout", response, start)
        assert response.status_code == 200, "Logout failed"
