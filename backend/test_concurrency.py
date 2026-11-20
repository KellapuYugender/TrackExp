import os
import requests
from concurrent.futures import ThreadPoolExecutor

BASE_URL = "http://127.0.0.1:8000/api"

TRIP_ID = int(os.environ["TEST_TRIP_ID"])
ACCESS_TOKEN = os.environ["TEST_ACCESS_TOKEN"]

url = f"{BASE_URL}/trips/{TRIP_ID}/expenses/"

headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}"
}

def create_expense(amount, merchant):
    payload = {
        "paid_by": int(os.environ["TEST_USER_ID"]),
        "amount": str(amount),
        "merchant": merchant,
        "category": "OTHER",
        "description": "Concurrent expense test"
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=20
        )

        return {
            "amount": amount,
            "status": response.status_code,
            "response": response.text
        }

    except requests.RequestException as error:
        return {
            "amount": amount,
            "status": "ERROR",
            "response": str(error)
        }


with ThreadPoolExecutor(max_workers=2) as executor:
    futures = [
        executor.submit(create_expense, "80.00", "Test A"),
        executor.submit(create_expense, "70.00", "Test B")
    ]

    for future in futures:
        print(future.result())
