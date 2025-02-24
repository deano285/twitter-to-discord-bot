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

NITTER_INSTANCES = [
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://nitter.42l.fr",
    "https://nitter.cz"
]

def get_working_nitter_instance():
    """Try different Nitter instances until one works."""
    for instance in NITTER_INSTANCES:
        try:
            test_url = f"{instance}/twitter/rss"
            response = requests.get(test_url, timeout=5)
            if response.status_code == 200:
                print(f"✅ Using Nitter instance: {instance}")
                return instance
        except requests.RequestException:
            continue
    print("❌ No working Nitter instances found!")
    return None  # No instance is available

# 📁 Directory to store last tweet IDs
LAST_TWEETS_DIR = "last_tweets"
os.makedirs(LAST_TWEETS_DIR, exist_ok=True)


def extract_image_from_description(description):
    """Extract a valid image URL from the tweet description using Nitter RSS."""
    if description:
        soup = BeautifulSoup(description, "html.parser")

        # ✅ Try to find an image inside the description (from Nitter RSS)
        img_tag = soup.find("img")
        if img_tag:
            img_url = img_tag.get("src")
            if img_url and img_url.startswith("http") and "nitter" not in img_url:
                print(f"✅ Extracted Nitter RSS image: {img_url}")
                return img_url  # Return valid image URL from Nitter

    # ❌ No image found in RSS
    print("⚠️ No image found in Nitter RSS.")
    return None  # No valid image found


def get_latest_tweets(username, max_tweets=3):
    """Fetch the latest tweets from a working Nitter instance and retry if needed."""
    for nitter_instance in NITTER_INSTANCES:
        url = f"{nitter_instance}/{username}/rss"
        headers = {"User-Agent": "Mozilla/5.0"}

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            # ✅ Check if the response is actually XML (not an error page)
            if not response.text.strip().startswith("<?xml"):
                print(f"❌ Nitter instance {nitter_instance} returned non-XML content for @{username}. Trying next instance...")
                continue  # Skip this instance and try the next one

            from xml.etree import ElementTree as ET
            root = ET.fromstring(response.text)
            items = root.findall(".//item")[:max_tweets]  # Get latest max_tweets

            tweets = []
            for item in items:
                tweet_link = item.find("link").text
                tweet_id = tweet_link.split("/")[-1]
                tweet_description = item.find("description").text
                tweet_image = extract_image_from_description(tweet_description, tweet_link)

                # Extract actual tweet timestamp
                tweet_timestamp = item.find("pubDate").text if item.find("pubDate") is not None else None

                tweets.append((tweet_id, tweet_link, tweet_description, tweet_image, tweet_timestamp))

            print(f"✅ Successfully fetched tweets from {nitter_instance} for @{username}")
            return tweets  # Return tweets if we found a working instance

        except requests.exceptions.RequestException as e:
            print(f"❌ Error with Nitter instance {nitter_instance} for @{username}: {e}. Trying next instance...")
        
        except ElementTree.ParseError as e:
            print(f"❌ XML Parse Error for @{username} on {nitter_instance}: {e}. Trying next instance...")

    print(f"🚨 All Nitter instances failed for @{username}. Skipping...")
    return []  # Return empty if all instances fail


def clean_tweet_description(description):
    """Remove HTML tags and unwanted characters from the tweet description."""
    if description:
        soup = BeautifulSoup(description, "html.parser")
        return soup.get_text().strip()  # Extract text only
    return None



def send_to_discord(webhook_url, username, tweet_link, tweet_description, tweet_image, tweet_timestamp):
    """Send new tweet to Discord webhook with correct timestamp."""
    if not webhook_url:
        print(f"⚠️ Skipping @{username}: Webhook URL is missing.")
        return

    # ✅ Ensure clean description processing
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
        try:
            # Check if the image URL is accessible
            img_response = requests.get(tweet_image, timeout=5)
            if img_response.status_code == 200 and tweet_image.startswith("http"):
                embed["image"] = {"url": tweet_image}
            else:
                print(f"⚠️ Image URL is invalid or blocked: {tweet_image}")
        except requests.exceptions.RequestException:
            print(f"⚠️ Image could not be loaded: {tweet_image}")

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

    return response.status_code  # ✅ Ensure return is inside the function



def load_last_tweets(username):
    """Load all previously posted tweet IDs to prevent duplicates."""
    file_path = os.path.join(LAST_TWEETS_DIR, f"{username}.txt")

    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            tweet_ids = f.read().strip().split("\n")
            return set(tweet_ids)  # Ensure unique tweet IDs

    return set()  # Return empty set if no history exists


def save_last_tweets(username, tweet_ids):
    """Save all tweet IDs that have been posted to prevent duplicates."""
    file_path = os.path.join(LAST_TWEETS_DIR, f"{username}.txt")

    # Ensure we only keep the latest 50 tweet IDs per user to prevent unnecessary bloat
    tweet_ids = list(tweet_ids)[-50:]

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
                    # ✅ Final check before sending to Discord
                    if tweet_id and tweet_id in last_tweet_ids:
                        print(f"⚠️ Skipping duplicate tweet for @{username}: {tweet_link}")
                        continue  # Skip already posted tweets

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
