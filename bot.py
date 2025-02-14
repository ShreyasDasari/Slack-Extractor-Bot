import logging
import os
import re
import time
import csv
from pathlib import Path
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

# Tokens
SLACK_USER_TOKEN = os.environ["SLACK_USER_TOKEN"]

# Client
user_client = WebClient(token=SLACK_USER_TOKEN)

logger = logging.getLogger(__name__)

def get_im_channels():
    """Fetches a list of direct message (IM) channels with pagination."""
    channels = []
    cursor = None
    try:
        while True:
            response = user_client.users_conversations(types="im", limit=200, cursor=cursor)
            channels.extend([(conv["id"], conv["user"]) for conv in response["channels"]])
            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break  # Exit loop if there's no more data
            time.sleep(1)  # Avoid hitting API rate limits
    except SlackApiError as e:
        logger.error(f"Error fetching conversation list: {e}")
    return channels

def get_all_user_names():
    """Fetches all users' real names with pagination."""
    user_dict = {}
    cursor = None
    try:
        while True:
            response = user_client.users_list(limit=200, cursor=cursor)
            for user in response["members"]:
                user_dict[user["id"]] = user.get("real_name", "Unknown User")
            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break  # Exit loop if there's no more data
            time.sleep(1)  # Avoid hitting API rate limits
    except SlackApiError as e:
        logger.error(f"Error fetching user list: {e}")
    return user_dict

def get_conversation_history(channel_id):
    """Fetches conversation history for a given channel."""
    try:
        result = user_client.conversations_history(channel=channel_id, limit=200)
        return result.get("messages", [])
    except SlackApiError as e:
        logger.error(f"Error fetching history for channel {channel_id}: {e}")
        return []

def extract_google_sheets_links(messages):
    """Extracts Google Sheets links from messages."""
    sheets_pattern = re.compile(r"https://docs\.google\.com/spreadsheets/d/[\w-]+")
    sheets_links = [sheets_pattern.findall(msg.get("text", "")) for msg in messages]
    sheets_links = [link for sublist in sheets_links for link in sublist]  # Flatten list
    return sheets_links if sheets_links else ["No link"]

# Fetch user names in bulk (with pagination)
user_names = get_all_user_names()

# Fetch all direct message channels and associated user IDs (with pagination)
channel_data = get_im_channels()

# Store results in a list
results = []

# Process each user's messages in batches to avoid rate limits
batch_size = 100  # Adjust batch size based on API limits

for i in range(0, len(channel_data), batch_size):
    batch = channel_data[i:i+batch_size]
    
    for channel_id, user_id in batch:
        user_name = user_names.get(user_id, "Unknown User")  # Get name from dictionary
        messages = get_conversation_history(channel_id)  # Get conversation history
        google_sheets_links = extract_google_sheets_links(messages)  # Extract links
        
        # Append results to list instead of printing immediately
        results.append((user_name.title(), ', '.join(google_sheets_links)))  # Convert list to string
    
    time.sleep(5)  # Sleep between batches to avoid rate limits

# Sort results alphabetically by user name
results.sort(key=lambda x: x[0])

# **Save results to CSV**
csv_filename = "extracted-links.csv"

with open(csv_filename, mode="w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerow(["User Name", "Google Sheets Links"])  # Write header
    writer.writerows(results)  # Write data rows

print(f"Data successfully saved to {csv_filename}")
