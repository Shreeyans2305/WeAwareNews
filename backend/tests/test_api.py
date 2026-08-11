import requests

API_KEY = "5d5d4a6eb5fd8c3b313b58c4d11a629f"
BASE_URL = "https://weaware-api-n4n6cdqpoq-uc.a.run.app"

for _ in range(10):
    res = requests.get(f"{BASE_URL}/stories/next", headers={"x-api-key": API_KEY})
    if res.status_code == 204:
        print("No more stories.")
        break
    data = res.json()
    if data.get("image_url"):
        print("Found one with image!")
        import json
        print(json.dumps(data, indent=2))
        break
    else:
        # Mark as posted
        story_id = data["story_id"]
        requests.post(f"{BASE_URL}/stories/{story_id}/mark-posted", headers={"x-api-key": API_KEY})
        print(f"Skipped {story_id}")
