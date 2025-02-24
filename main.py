import requests
import json
import time
import os
import re
from bs4 import BeautifulSoup
from datetime import datetime
from email.utils import parsedate_to_datetime

# 📝 Retrieve webhook URLs from environment variables (GitHub Secrets)
WEBHOOKS = {
    os.getenv("WEBHOOK_1"): ["RoyaleAPI", "ClashRoyale"],
    os.getenv("WEBHOOK_2"): ["PokemonGoApp", "LeekDuck", "PokemonGOHubNet", "PokemonSleep"],
    os.getenv("WEBHOOK_3"): ["FortniteStatus", "FNCompetitive", "HYPEX"],
    os.getenv("WEBHOOK_4"): ["survivetheark", "ARKAscendedNews"],
    os.getenv("WEBHOOK_5"): ["NWGameStatus", "playnewworld"],
}

# ✅ Use a stable Nitter instance
NITTER_INSTANCE = "https://nitter.privacydev.net"

# 📁 Directory to store last tweet IDs
LAST_TWEETS_DIR = "last_tweets"
os.makedirs(LAST_TWEETS_DIR, exist_ok=True)


def extract_image_from_description(description):
    """Extract the first image URL from the tweet description."""
    if description:
        soup = BeautifulSoup(description, "html.parser")
        img_tag = soup.find("img")
        if img_tag:
            img_url = img_tag.get("src")
            if img_url and img_url.startswith("http") and "nitter" not in img_url:
                return img_url  # Return only valid image URLs
    return None  # No valid image found


def clean_tweet_description(description):
    """Remove HTML tags from the tweet description."""
    if description:
        soup = BeautifulSoup(description, "html.parser")
        return soup.get_text().strip()  # Extract text only
    return None


def get_latest_tweets(username, max_tweets=3):
    """Fetch the latest tweets from Nitter RSS (up to max_tweets) and extract timestamps."""
    url = f"{NITTER_INSTANCE}/{username}/rss"
    headers = {"User-Agent": "Mozilla/5.0"}

    tweets = []
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        from xml.etree import ElementTree as ET
        root = ET.fromstring(response.text)
        items = root.findall(".//item")[:max_tweets]  # Get latest max_tweets

        for item in items:
            tweet_link = item.find("link").text
            tweet_id = tweet_link.split("/")[-1]
            tweet_description = item.find("description").text
            tweet_image = extract_image_from_description(tweet_description)

            # Extract actual tweet timestamp
            tweet_timestamp = item.find("pubDate").text if item.find("pubDate") is not None else None

            tweets.append((tweet_id, tweet_link, tweet_description, tweet_image, tweet_timestamp))
    
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching tweets for @{username}: {e}")

    return tweets  # Return multiple tweets


def send_to_discord(webhook_url, username, tweet_link, tweet_description, tweet_image, tweet_timestamp):
    """Send new tweet to Discord webhook with improved embed formatting."""
    if not webhook_url:
        print(f"⚠️ Skipping @{username}: Webhook URL is missing.")
        return

    clean_description = clean_tweet_description(tweet_description)

    embed = {
        "title": f"📢 New Tweet from @{username}",
        "url": tweet_link,
        "description": clean_description if clean_description else "Click the link to view the tweet!",
        "color": 1942002,  # Blue color for embed
        "footer": {
            "text": f"Follow @{username} for more updates!",
            "icon_url": "https://abs.twimg.com/icons/apple-touch-icon-192x192.png"
        }
    }

    # ✅ Ensure valid images before adding
    if tweet_image:
        if "nitter" not in tweet_image and tweet_image.startswith("http"):
            embed["image"] = {"url": tweet_image}
        else:
            print(f"⚠️ Skipping invalid image: {tweet_image}")

    # ✅ Use actual tweet timestamp instead of bot run time
    if tweet_timestamp:
        parsed_time = parsedate_to_datetime(tweet_timestamp)
        embed["timestamp"] = parsed_time.isoformat()

    # ✅ Add author field for better formatting
    embed["author"] = {
        "name": f"@{username}",
        "url": f"https://twitter.com/{username}",
        "icon_url": "https://abs.twimg.com/icons/apple-touch-icon-192x192.png"
    }

    payload = {"embeds": [embed]}
    headers = {"Content-Type": "application/json"}

    response = requests.post(webhook_url, data=json.dumps(payload), headers=headers)
    return response.status_code


def load_last_tweets(username):
    """Load all previously posted tweet IDs for a specific Twitter user to prevent duplicates."""
    file_path = os.path.join(LAST_TWEETS_DIR, f"{username}.txt")

    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return set(f.read().strip().split("\n"))  # Store as a set to prevent duplicates

    return set()  # Return empty set if no history exists


def save_last_tweets(username, tweet_ids):
    """Save all tweet IDs that have been posted to prevent duplicates."""
    file_path = os.path.join(LAST_TWEETS_DIR, f"{username}.txt")

    with open(file_path, "w") as f:
        f.write("\n".join(tweet_ids))  # Store all tweet IDs


def main():
    """Main loop to check multiple Twitter accounts and post tweets to grouped webhooks."""
    while True:
        for webhook_url, usernames in WEBHOOKS.items():
            if not webhook_url:  # Skip if webhook is empty
                continue

            for username in usernames:
                last_tweet_ids = load_last_tweets(username)  # Load all posted tweets
                tweets = get_latest_tweets(username, max_tweets=3)  # Fetch latest 3 tweets

                for tweet_id, tweet_link, tweet_description, tweet_image, tweet_timestamp in reversed(tweets):
                    if tweet_id and tweet_id not in last_tweet_ids:
                        print(f"✅ New tweet found for @{username}: {tweet_link}")
                        status = send_to_discord(webhook_url, username, tweet_link, tweet_description, tweet_image, tweet_timestamp)

                        if status == 204:  # Discord success code
                            last_tweet_ids.add(tweet_id)
                            save_last_tweets(username, last_tweet_ids)
                            print(f"📢 Tweet posted to Discord webhook {webhook_url} for @{username}!")
                        else:
                            print(f"⚠️ Failed to post tweet for @{username}. Status Code: {status}")

        time.sleep(60)  # Check every 60 seconds instead of 300


if __name__ == "__main__":
    main()