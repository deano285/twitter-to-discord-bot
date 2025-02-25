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


from playwright.sync_api import sync_playwright
import time
from email.utils import parsedate_to_datetime
from datetime import datetime

import snscrape.modules.twitter as sntwitter

def get_tweets_from_x(username, max_tweets=3):
    """Fetch the latest tweets from Twitter/X using snscrape."""
    tweet_data = []
    for i, tweet in enumerate(sntwitter.TwitterUserScraper(username).get_items()):
        if i >= max_tweets:
            break

        tweet_data.append({
            "tweet_id": tweet.id,
            "tweet_link": f"https://twitter.com/{username}/status/{tweet.id}",
            "tweet_text": tweet.content,
            "tweet_images": [media.fullUrl for media in tweet.media if isinstance(media, sntwitter.Photo)],
            "tweet_videos": [media.variants[0].url for media in tweet.media if isinstance(media, sntwitter.Video)],
            "tweet_timestamp": tweet.date.isoformat()
        })

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
