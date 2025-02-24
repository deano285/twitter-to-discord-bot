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


def get_latest_tweet(username):
    """Fetch the latest tweet from Nitter RSS."""
    url = f"{NITTER_INSTANCE}/{username}/rss"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raise an error if response is bad

        from xml.etree import ElementTree as ET
        root = ET.fromstring(response.text)
        first_item = root.find(".//item")

        if first_item is not None:
            tweet_link = first_item.find("link").text
            tweet_id = tweet_link.split("/")[-1]  # Extract tweet ID
            tweet_description = first_item.find("description").text

            # Extract first image if available
            tweet_image = extract_image_from_description(tweet_description)

            return tweet_id, tweet_link, tweet_description, tweet_image
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching tweets for @{username}: {e}")

    return None, None, None, None  # Return empty values if there's an error


def extract_image_from_description(description):
    """Extract the first image URL from the tweet description."""
    if description:
        match = re.search(r'<img src="(.*?)"', description)
        if match:
            return match.group(1)  # Return the first image URL found
    return None  # No image found


def send_to_discord(webhook_url, username, tweet_link, tweet_description, tweet_image):
    """Send new tweet to the specified Discord webhook as an embed."""
    if not webhook_url:  # Skip if webhook is missing
        print(f"⚠️ Skipping @{username}: Webhook URL is missing.")
        return

    embed = {
        "title": f"New Tweet from @{username}",
        "url": tweet_link,
        "description": tweet_description if tweet_description else "Click to view the tweet!",
        "color": 1942002,  # Blue color for embed
        "footer": {
            "text": f"Follow @{username} on Twitter",
            "icon_url": "https://abs.twimg.com/icons/apple-touch-icon-192x192.png"
        }
    }

    # Include image in embed if available
    if tweet_image:
        embed["image"] = {"url": tweet_image}

    payload = {"embeds": [embed]}
    headers = {"Content-Type": "application/json"}

    response = requests.post(webhook_url, data=json.dumps(payload), headers=headers)
    return response.status_code


def load_last_tweet(username):
    """Load the last tweet ID for a specific Twitter user."""
    file_path = os.path.join(LAST_TWEETS_DIR, f"{username}.txt")

    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return f.read().strip()
    return None


def save_last_tweet(username, tweet_id):
    """Save the last tweet ID for a specific Twitter user."""
    file_path = os.path.join(LAST_TWEETS_DIR, f"{username}.txt")

    with open(file_path, "w") as f:
        f.write(tweet_id)


def main():
    """Main loop to check multiple Twitter accounts and post tweets to grouped webhooks."""
    while True:
        for webhook_url, usernames in WEBHOOKS.items():
            if not webhook_url:  # Skip if webhook is empty
                continue

            for username in usernames:
                last_tweet_id = load_last_tweet(username)
                tweet_id, tweet_link, tweet_description, tweet_image = get_latest_tweet(username)

                if tweet_id and tweet_id != last_tweet_id:
                    print(f"✅ New tweet found for @{username}: {tweet_link}")
                    status = send_to_discord(webhook_url, username, tweet_link, tweet_description, tweet_image)

                    if status == 204:  # Discord success code
                        save_last_tweet(username, tweet_id)
                        print(f"📢 Tweet posted to Discord webhook {webhook_url} for @{username}!")
                    else:
                        print(f"⚠️ Failed to post tweet for @{username}. Status Code: {status}")
                else:
                    print(f"🔄 No new tweets for @{username}. Checking again soon.")

        time.sleep(300)  # Wait 5 minutes before checking again


if __name__ == "__main__":
    main()
