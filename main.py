import requests
import json
import time
import os
import re
from bs4 import BeautifulSoup
from datetime import datetime
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

# 📝 Retrieve webhook URLs from environment variables (GitHub Secrets)
WEBHOOKS = {
    os.getenv("WEBHOOK_1"): ["RoyaleAPI", "ClashRoyale"],
    os.getenv("WEBHOOK_2"): ["PokemonGoApp", "LeekDuck", "PokemonGOHubNet", "PokemonSleep"],
    os.getenv("WEBHOOK_3"): ["FortniteStatus", "FNCompetitive", "HYPEX"],
    os.getenv("WEBHOOK_4"): ["survivetheark", "ARKAscendedNews"],
    os.getenv("WEBHOOK_5"): ["NWGameStatus", "playnewworld"],
}

# ✅ List of Nitter instances to try
NITTER_INSTANCES = [
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://nitter.42l.fr",
    "https://nitter.cz"
]

# 📁 Directory to store last tweet IDs
LAST_TWEETS_DIR = "last_tweets"
os.makedirs(LAST_TWEETS_DIR, exist_ok=True)


def get_working_nitter_instance(username):
    """Try different Nitter instances until one works for the given username."""
    for instance in NITTER_INSTANCES:
        url = f"{instance}/{username}/rss"
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200 and response.text.strip().startswith("<?xml"):
                print(f"✅ Using Nitter instance: {instance} for @{username}")
                return instance
        except requests.RequestException:
            continue
    print(f"❌ No working Nitter instance found for @{username}")
    return None


import random

def extract_media_from_tweet(tweet_link):
    """Fetch the Nitter tweet page and extract media (image/video) using OpenGraph metadata."""
    try:
        # ✅ Introduce a random delay to prevent hitting rate limits
        time.sleep(random.uniform(1, 3))  # Delay between 1-3 seconds

        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(tweet_link, headers=headers, timeout=5)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        meta_image = soup.find("meta", property="og:image")
        
        if meta_image:
            og_image = meta_image.get("content")
            if og_image and og_image.startswith("http"):
                print(f"✅ Extracted media from tweet page: {og_image}")
                return og_image

    except requests.exceptions.HTTPError as e:
        if response.status_code == 429:
            print(f"⚠️ Rate limited by Nitter for {tweet_link}. Retrying with another instance...")
            return retry_media_extraction(tweet_link)  # Retry with another Nitter instance

    except requests.exceptions.RequestException as e:
        print(f"⚠️ Failed to extract media from tweet page {tweet_link}: {e}")

    return None  # No valid image found

def retry_media_extraction(tweet_link):
    """Retry extracting media using another Nitter instance if rate-limited."""
    for instance in NITTER_INSTANCES:
        alternate_tweet_link = tweet_link.replace(NITTER_INSTANCES[0], instance)  # Swap instances
        try:
            print(f"🔄 Retrying media extraction with {instance}")
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(alternate_tweet_link, headers=headers, timeout=5)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            meta_image = soup.find("meta", property="og:image")
            
            if meta_image:
                og_image = meta_image.get("content")
                if og_image and og_image.startswith("http"):
                    print(f"✅ Extracted media from alternate instance: {og_image}")
                    return og_image

        except requests.exceptions.RequestException:
            print(f"⚠️ Failed to fetch media from {instance}. Trying next instance...")

    print(f"❌ All Nitter instances failed for {tweet_link}")
    return None


def extract_image_from_description(description, tweet_link):
    """
    Extract a valid media URL from the tweet description using Nitter RSS.
    If no image is found in the description, fallback to fetching the tweet page.
    """
    if description:
        soup = BeautifulSoup(description, "html.parser")
        img_tag = soup.find("img")
        if img_tag:
            img_url = img_tag.get("src")
            if img_url and img_url.startswith("http") and "nitter" not in img_url:
                print(f"✅ Extracted image from RSS: {img_url}")
                return img_url
    # Fallback: fetch media from the tweet page
    print("⚠️ No image found in RSS description, attempting to fetch media from tweet page...")
    return extract_media_from_tweet(tweet_link)


def clean_tweet_description(description):
    """Remove HTML tags and unwanted characters from the tweet description."""
    if description:
        soup = BeautifulSoup(description, "html.parser")
        return soup.get_text().strip()
    return None


def get_latest_tweets(username, max_tweets=3):
    """Fetch the latest tweets from a working Nitter instance and extract timestamps."""
    working_instance = get_working_nitter_instance(username)
    if not working_instance:
        return []  # Skip if no instance is available

    url = f"{working_instance}/{username}/rss"
    headers = {"User-Agent": "Mozilla/5.0"}
    tweets = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        root = ElementTree.fromstring(response.text)
        items = root.findall(".//item")[:max_tweets]
        for item in items:
            tweet_link = item.find("link").text
            tweet_id = tweet_link.split("/")[-1]
            tweet_description = item.find("description").text
            # Pass both description and tweet_link to extract media
            tweet_image = extract_image_from_description(tweet_description, tweet_link)
            tweet_timestamp = item.find("pubDate").text if item.find("pubDate") is not None else None
            tweets.append((tweet_id, tweet_link, tweet_description, tweet_image, tweet_timestamp))
        print(f"✅ Successfully fetched tweets from {working_instance} for @{username}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching tweets for @{username} using {working_instance}: {e}")
    except ElementTree.ParseError as e:
        print(f"❌ XML Parse Error for @{username}: {e}")
    return tweets


def send_to_discord(webhook_url, username, tweet_link, tweet_description, tweet_image, tweet_timestamp):
    """Send new tweet to Discord webhook with correct timestamp."""
    if not webhook_url:
        print(f"⚠️ Skipping @{username}: Webhook URL is missing.")
        return
    clean_description = clean_tweet_description(tweet_description)
    embed = {
        "title": f"📢 New Tweet from @{username}",
        "url": tweet_link,
        "description": clean_description if clean_description else "Click the link to view the tweet!",
        "color": 1942002,
        "footer": {
            "text": f"Follow @{username} for more updates!",
            "icon_url": "https://abs.twimg.com/icons/apple-touch-icon-192x192.png"
        }
    }
    if tweet_image:
        try:
            img_response = requests.get(tweet_image, timeout=5)
            if img_response.status_code == 200 and tweet_image.startswith("http"):
                embed["image"] = {"url": tweet_image}
            else:
                print(f"⚠️ Image URL is invalid or blocked: {tweet_image}")
        except requests.exceptions.RequestException:
            print(f"⚠️ Image could not be loaded: {tweet_image}")
    if tweet_timestamp:
        parsed_time = parsedate_to_datetime(tweet_timestamp)
        embed["timestamp"] = parsed_time.isoformat()
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
                tweets = get_latest_tweets(username, max_tweets=3)
                for tweet_id, tweet_link, tweet_description, tweet_image, tweet_timestamp in reversed(tweets):
                    if tweet_id and tweet_id in last_tweet_ids:
                        print(f"⚠️ Skipping duplicate tweet for @{username}: {tweet_link}")
                        continue
                    print(f"✅ New tweet found for @{username}: {tweet_link}")
                    status = send_to_discord(webhook_url, username, tweet_link, tweet_description, tweet_image, tweet_timestamp)
                    if status == 204:
                        last_tweet_ids.add(tweet_id)
                        save_last_tweets(username, last_tweet_ids)
                        print(f"📢 Tweet posted to Discord webhook {webhook_url} for @{username}!")
                    else:
                        print(f"⚠️ Failed to post tweet for @{username}. Status Code: {status}")
        time.sleep(60)


if __name__ == "__main__":
    main()
