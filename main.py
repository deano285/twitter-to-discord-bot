import os
import json
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from email.utils import parsedate_to_datetime
from playwright.sync_api import sync_playwright

# 📝 Retrieve webhook URLs from environment variables (GitHub Secrets)
WEBHOOKS = {
    os.getenv("WEBHOOK_1"): ["RoyaleAPI", "ClashRoyale"],
    os.getenv("WEBHOOK_2"): ["PokemonGoApp", "LeekDuck", "PokemonGOHubNet", "PokemonSleep"],
    os.getenv("WEBHOOK_3"): ["FortniteStatus", "FNCompetitive", "HYPEX"],
    os.getenv("WEBHOOK_4"): ["survivetheark", "ARKAscendedNews"],
    os.getenv("WEBHOOK_5"): ["NWGameStatus", "playnewworld"],
}

# 📁 Directory to store last tweet IDs
LAST_TWEETS_DIR = "last_tweets"
os.makedirs(LAST_TWEETS_DIR, exist_ok=True)


def get_tweets_from_x(username, max_tweets=3):
    """Fetch the latest tweets from Twitter/X using Playwright."""
    tweet_data = []
    twitter_url = f"https://twitter.com/{username}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(twitter_url, timeout=15000)

        # ✅ Scroll down to load new tweets
        for _ in range(3):  
            page.keyboard.press("End")  
            time.sleep(3)  

        tweets = page.locator("article").all()[:max_tweets]  # Limit the number of tweets fetched
        for tweet in tweets:
            try:
                tweet_id = tweet.get_attribute("data-testid")
                if not tweet_id:
                    continue  # Skip if no valid tweet ID

                tweet_link = f"https://twitter.com/{username}/status/{tweet_id}"
                tweet_text = tweet.locator("div[lang]").first.inner_text()

                # ✅ Extract images
                image_elements = tweet.locator("img").all()
                tweet_images = [img.get_attribute("src") for img in image_elements if img.get_attribute("src") and "twimg" in img.get_attribute("src")]

                # ✅ Extract videos
                video_elements = tweet.locator("video").all()
                tweet_videos = [vid.get_attribute("src") for vid in video_elements if vid.get_attribute("src")]

                # ✅ Extract timestamp and check if it's recent
                timestamp_element = tweet.locator("time").first
                tweet_timestamp = timestamp_element.get_attribute("datetime") if timestamp_element else None

                # ✅ Ignore old tweets (more than 7 days old)
                if tweet_timestamp:
                    parsed_time = parsedate_to_datetime(tweet_timestamp)
                    if (datetime.utcnow() - parsed_time).days > 7:
                        print(f"⚠️ Skipping old tweet from @{username}: {tweet_link}")
                        continue  # Skip tweets older than 7 days

                tweet_data.append({
                    "tweet_id": tweet_id,
                    "tweet_link": tweet_link,
                    "tweet_text": tweet_text,
                    "tweet_images": tweet_images,
                    "tweet_videos": tweet_videos,
                    "tweet_timestamp": tweet_timestamp,
                })
            except Exception as e:
                print(f"⚠️ Failed to extract tweet details for @{username}: {e}")

        browser.close()

    return tweet_data


def send_to_discord(webhook_url, username, tweet):
    """Send new tweet to Discord webhook with images/videos."""
    if not webhook_url:
        print(f"⚠️ Skipping @{username}: Webhook URL is missing.")
        return

    embed = {
        "title": f"📢 New Tweet from @{username}",
        "url": tweet["tweet_link"],
        "description": tweet["tweet_text"] if tweet["tweet_text"] else "Click the link to view the tweet!",
        "color": 1942002,
        "footer": {
            "text": f"Follow @{username} for more updates!",
            "icon_url": "https://abs.twimg.com/icons/apple-touch-icon-192x192.png"
        }
    }

    # ✅ Add images if available
    if tweet["tweet_images"]:
        embed["image"] = {"url": tweet["tweet_images"][0]}  # Only use the first image

    # ✅ Add video link as a field (since Discord doesn't support video embeds)
    if tweet["tweet_videos"]:
        embed["fields"] = [{"name": "🎥 Video", "value": tweet["tweet_videos"][0]}]

    # ✅ Ensure timestamp exists before parsing
    if tweet["tweet_timestamp"]:
        try:
            parsed_time = parsedate_to_datetime(tweet["tweet_timestamp"])
            embed["timestamp"] = parsed_time.isoformat()
        except Exception as e:
            print(f"⚠️ Failed to parse tweet timestamp: {tweet['tweet_timestamp']}. Error: {e}")

    payload = {"embeds": [embed]}
    headers = {"Content-Type": "application/json"}

    response = requests.post(webhook_url, data=json.dumps(payload), headers=headers)
    return response.status_code




def load_last_tweets(username):
    """Load all previously posted tweet IDs to prevent duplicates."""
    file_path = os.path.join(LAST_TWEETS_DIR, f"{username}.txt")

    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return set(f.read().strip().split("\n"))

    return set()


def save_last_tweets(username, tweet_ids):
    """Save all tweet IDs that have been posted to prevent duplicates."""
    file_path = os.path.join(LAST_TWEETS_DIR, f"{username}.txt")
    tweet_ids = list(tweet_ids)[-50:]
    with open(file_path, "w") as f:
        f.write("\n".join(tweet_ids))



def main():
    """Main loop to check multiple Twitter accounts and post tweets to grouped webhooks."""
    while True:
        for webhook_url, usernames in WEBHOOKS.items():
            if not webhook_url:
                continue

            for username in usernames:
                last_tweet_ids = load_last_tweets(username)
                tweets = get_tweets_from_x(username, max_tweets=3)

                for tweet in reversed(tweets):
                    if tweet["tweet_id"] in last_tweet_ids:
                        print(f"⚠️ Skipping duplicate tweet for @{username}: {tweet['tweet_link']}")
                        continue

                    print(f"✅ New tweet found for @{username}: {tweet['tweet_link']}")
                    status = send_to_discord(webhook_url, username, tweet)

                    if status == 204:
                        last_tweet_ids.add(tweet["tweet_id"])
                        save_last_tweets(username, last_tweet_ids)
                        print(f"📢 Tweet posted to Discord webhook {webhook_url} for @{username}!")
                    else:
                        print(f"⚠️ Failed to post tweet for @{username}. Status Code: {status}")

        time.sleep(60)


if __name__ == "__main__":
    main()
