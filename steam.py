import os
import time

import requests
from dotenv import load_dotenv

import time
from datetime import datetime

def get_all_steam_apps(api_key=None):
    load_dotenv()
    if not api_key:
        api_key = os.getenv('STEAM_API_KEY')
    if not api_key:
        raise ValueError("STEAM API key is missing")

    url = 'https://api.steampowered.com/IStoreService/GetAppList/v1/'
    all_apps = []
    last_appid = 0

    while True:
        params = {
            'key': api_key,
            'max_results': 50000,
            'include_games': 1,
            'include_dlc': 0,
            'include_software': 0,
            'include_videos': 0,
            'include_hardware': 0,
            'last_appid': last_appid,
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        apps = data.get('response', {}).get('apps', [])
        final_list = [{'appid': item['appid'], 'name': item['name'], 'last_modified': item.get('last_modified'), 'price_change_number': item.get('price_change_number')} for item in apps]
        all_apps.extend(final_list)
        print(f"{len(all_apps)} jeux récupérés...")

        if data['response'].get('have_more_results'):
            last_appid = data['response']['last_appid']
            time.sleep(0.5)
        else:
            break

    return all_apps

from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_release_date(appid):
    """Fetch release date for a single appid from Steam API."""
    try:
        url = "https://store.steampowered.com/api/appdetails"
        response = requests.get(url, params={"appids": appid}, timeout=10)
        response.raise_for_status()
        data = response.json()

        app_data = data.get(str(appid), {})
        if not app_data.get("success"):
            return appid, None, None

        game_data = app_data.get("data", {})
        release = game_data.get("release_date", {})
        date_str = release.get("date", "")

        if not date_str or release.get("coming_soon"):
            return appid, None, None

        # Parse "1 Apr, 1999" or "Apr 1999" formats
        release_year = None
        for fmt in ("%d %b, %Y", "%b %Y"):
            try:
                release_year = datetime.strptime(date_str, fmt).year
                break
            except ValueError:
                continue

        return appid, date_str, release_year

    except Exception as e:
        print(f"Error fetching appid {appid}: {e}")
        return appid, None, None


def enrich_release_dates(col):
    """Fetch release dates from Steam API in parallel and store in MongoDB."""
    # Only fetch games that don't have a release_year yet and haven't failed before
    games = list(col.find(
        {
            "release_year": {"$exists": False},
            "release_date_failed": {"$exists": False}  # skip previously failed ones
        },
        {"appid": 1, "_id": 1}
    ))

    if not games:
        print("All release dates already fetched.")
        return

    print(f"Fetching release dates for {len(games)} games...")
    appid_to_id = {g["appid"]: g["_id"] for g in games}

    with ThreadPoolExecutor(max_workers=1) as executor:
        futures = {executor.submit(fetch_release_date, g["appid"]): g["appid"] for g in games}
        for future in as_completed(futures):
            appid, date_str, release_year = future.result()
            if release_year:
                col.update_one(
                    {"_id": appid_to_id[appid]},
                    {"$set": {"release_date": date_str, "release_year": release_year}}
                )
            else:
                # Mark as failed so we don't retry it next run
                col.update_one(
                    {"_id": appid_to_id[appid]},
                    {"$set": {"release_date_failed": True}}
                )

    print("Release dates fetched.")