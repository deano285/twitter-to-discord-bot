import requests
import json
import time
import os
import re

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
    """Extract the first image URL from the tweet description, ignoring placeholders."""
    if description:
        soup = BeautifulSoup(description, "html.parser")
        img_tag = soup.find("img")
        if img_tag:
            img_url = img_tag.get("src")
            if img_url and "nitter" not in img_url:  # Ignore Nitter placeholders
                return img_url
    return None  # No valid image found


def get_latest_tweets(username, max_tweets=3):
    """Fetch the latest tweets from Nitter RSS (up to max_tweets)."""
    url = f"{NITTER_INSTANCE}/{username}/rss"
    headers = {"User-Agent": "Mozilla/5.0"}

    tweets = []
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raise error if response is bad

        from xml.etree import ElementTree as ET
        root = ET.fromstring(response.text)
        items = root.findall(".//item")[:max_tweets]  # Get the latest max_tweets

        for item in items:
            tweet_link = item.find("link").text
            tweet_id = tweet_link.split("/")[-1]  # Extract tweet ID
            tweet_description = item.find("description").text

            # Extract first image if available
            tweet_image = extract_image_from_description(tweet_description)

            tweets.append((tweet_id, tweet_link, tweet_description, tweet_image))
    
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching tweets for @{username}: {e}")

    return tweets  # Return multiple tweets


from bs4 import BeautifulSoup

def clean_tweet_description(description):
    """Remove HTML tags from the tweet description."""
    if description:
        soup = BeautifulSoup(description, "html.parser")
        return soup.get_text().strip()  # Extract text only
    return None


def send_to_discord(webhook_url, username, tweet_link, tweet_description, tweet_image):
    """Send new tweet to Discord webhook with improved embed formatting."""
    if not webhook_url:  # Skip if webhook is missing
        print(f"⚠️ Skipping @{username}: Webhook URL is missing.")
        return

    # Clean tweet description
    clean_description = clean_tweet_description(tweet_description)

    embed = {
        "title": f"📢 New Tweet from @{username}",
        "url": tweet_link,
        "description": clean_description if clean_description else "Click the link to view the tweet!",
        "color": 1942002,  # Blue color for embed
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),  # Adds a timestamp
        "footer": {
            "text": f"Follow @{username} for more updates!",
            "icon_url": "https://abs.twimg.com/icons/apple-touch-icon-192x192.png"
        }
    }

    # 🛠 Ensure image is valid before adding it
    if tweet_image:
        if "nitter" not in tweet_image and tweet_image.startswith("http"):
            embed["image"] = {"url": tweet_image}
        else:
            print(f"⚠️ Skipping invalid image: {tweet_image}")

    # Add author field for better formatting
    embed["author"] = {
        "name": f"@{username}",
        "url": f"https://twitter.com/{username}",
        "icon_url": "https://abs.twimg.com/icons/apple-touch-icon-192x192.png"
    }

    payload = {"embeds": [embed]}
    headers = {"Content-Type": "application/json"}

    response = requests.post(webhook_url, data=json.dumps(payload), headers=headers)
    return response.status_code




def load_last_tweets(username, count=5):
    """Load the last N tweet IDs for a specific Twitter user to prevent duplicates."""
    file_path = os.path.join(LAST_TWEETS_DIR, f"{username}.txt")

    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return f.read().strip().split("\n")[:count]  # Return up to last N tweet IDs

    return []  # Return an empty list if no history exists


def save_last_tweets(username, tweet_ids, count=5):
    """Save the last N tweet IDs for a specific Twitter user."""
    file_path = os.path.join(LAST_TWEETS_DIR, f"{username}.txt")

    with open(file_path, "w") as f:
        f.write("\n".join(tweet_ids[:count]))  # Keep only the last N tweet IDs


def main():
    """Main loop to check multiple Twitter accounts and post tweets to grouped webhooks."""
    while True:
        for webhook_url, usernames in WEBHOOKS.items():
            if not webhook_url:  # Skip if webhook is empty
                continue

            for username in usernames:
                last_tweet_ids = load_last_tweets(username)  # Load last few tweets
                tweets = get_latest_tweets(username, max_tweets=3)  # Fetch latest 3 tweets

                new_tweet_ids = []  # Track new tweets posted
                
                for tweet_id, tweet_link, tweet_description, tweet_image in reversed(tweets):
                    if tweet_id and tweet_id not in last_tweet_ids:
                        print(f"✅ New tweet found for @{username}: {tweet_link}")
                        status = send_to_discord(webhook_url, username, tweet_link, tweet_description, tweet_image)

                        if status == 204:  # Discord success code
                            new_tweet_ids.append(tweet_id)
                            print(f"📢 Tweet posted to Discord webhook {webhook_url} for @{username}!")
                        else:
                            print(f"⚠️ Failed to post tweet for @{username}. Status Code: {status}")

                # Save the new last tweets while keeping history
                if new_tweet_ids:
                    save_last_tweets(username, new_tweet_ids + last_tweet_ids)  # Keep newest + old ones

        time.sleep(60)  # Check every 60 seconds instead of 300


if __name__ == "__main__":
    main()
