import urllib.request
import json
try:
    url = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?actor=nytimes.com&limit=1"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as response:
        print(json.loads(response.read().decode("utf-8")))
except Exception as e:
    print(f"Error: {e}")
