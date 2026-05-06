import os
import sys
import time
import requests
import subprocess
from dotenv import load_dotenv
from pymongo import MongoClient

import time

MAX_RETRIES = 3
RETRY_DELAY = 2


def get_mongo_collection(collection_name="games"):
    mongo_uri = os.getenv("MONGO_URI", "mongodb://root:example@mongodb:27017/")
    client = MongoClient(mongo_uri, authSource="admin")
    db = client["steam_prediction"]
    return db[collection_name]

def backup_db(before_appid, filtered_apps=None, steam_namecol="games"):
    mongo_uri = os.getenv("MONGO_URI", "mongodb://root:example@mongodb:27017/")
    if filtered_apps:
        collection = get_mongo_collection(steam_namecol)
        for doc in filtered_apps:
            collection.update_one(
                {"appid": doc["appid"]},
                {"$set": doc},
                upsert=True
            )
    backup_name = f"steam_data_before_{before_appid}"
    out_path = f"./db/{backup_name}"
    print(f"[BACKUP] SAVED BEFOR appid {before_appid} → {out_path}")

    result = subprocess.run(
        [
            "mongodump",
            "--uri", mongo_uri,
            "--authenticationDatabase", "admin",
            "--db", "steam_prediction",
            "--out", out_path
        ],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"[BACKUP] FAILED : {result.stderr}")
    else:
        print(f"[BACKUP] SUCCEED : {backup_name}")


def is_real_game(appid, filtered_apps=None, steam_namecol="games"):
    url = "https://store.steampowered.com/api/appdetails"
    params = {"appids": appid}

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        app_data = data.get(str(appid), {})
        if not app_data.get("success"):
            return False, "ERROR"

        game_data = app_data.get("data", {})
        return game_data.get("type") == "game", game_data.get("type")

    except Exception as e:
        print(f"[is_real_game][STEAM] FAILED FOR appid {appid} : {e}")
        backup_db(before_appid=appid, filtered_apps=filtered_apps, steam_namecol=steam_namecol)
        sys.exit(69)

def get_all_steam_apps(steam_namecol, api_key=None):
    load_dotenv()
    if not api_key:
        api_key = os.getenv('STEAM_API_KEY')
    if not api_key:
        raise ValueError("STEAM API key is missing")

    url = 'https://api.steampowered.com/IStoreService/GetAppList/v1/'
    all_apps = []
    filtered_apps = []
    last_appid = 0

    while True:
        params = {
            'key': api_key,
            'max_results': 50_000,
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
        all_apps.extend([{'appid': item['appid'], 'name': item['name']} for item in apps])

        if data['response'].get('have_more_results'):
            last_appid = data['response']['last_appid']
        else:
            break

    for idx, item in enumerate(all_apps):
        if idx != 0 and idx % 80_000 == 0:
            print(f"Processed {idx} items")
            break
        state, category = is_real_game(item["appid"], filtered_apps, steam_namecol="games")
        filtered_apps.append({
            "appid": item["appid"],
            "name": item["name"],
            "type": category,
        })

    collection = get_mongo_collection(steam_namecol)
    for doc in filtered_apps:
        collection.update_one(
            {"appid": doc["appid"]},
            {"$set": doc},
            upsert=True
        )
    print(f"[DB] {len(filtered_apps)} documents add")

    print(len(filtered_apps))
    return filtered_apps


def get_games_info(game_ids: list) -> list:
    url = "https://store.steampowered.com/api/appdetails"
    games_details = []
    failed_appids = []

    for game_id in game_ids:
        appid = game_id.get("appid")
        if not appid:
            print(f"[STEAM] game_id sans appid ignoré: {game_id}")
            continue

        params = {"appids": appid}
        data = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = requests.get(url, params=params, timeout=30)

                if response.status_code == 429:
                    wait = RETRY_DELAY * attempt
                    print(f"[STEAM] Rate limit appid={appid}, attente {wait}s (tentative {attempt}/{MAX_RETRIES})")
                    time.sleep(wait)
                    continue

                response.raise_for_status()
                data = response.json()
                break  # succès

            except requests.exceptions.Timeout:
                print(f"[STEAM] Timeout appid={appid} (tentative {attempt}/{MAX_RETRIES})")
            except requests.exceptions.ConnectionError:
                print(f"[STEAM] Connexion perdue appid={appid} (tentative {attempt}/{MAX_RETRIES})")
            except requests.exceptions.HTTPError as e:
                print(f"[STEAM] HTTP {e.response.status_code} appid={appid} (tentative {attempt}/{MAX_RETRIES})")
            except ValueError:
                print(f"[STEAM] JSON invalide appid={appid} (tentative {attempt}/{MAX_RETRIES})")

            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)

        if data is None:
            print(f"[STEAM] Abandon appid={appid} après {MAX_RETRIES} tentatives")
            failed_appids.append(appid)
            continue

        app_data = data.get(str(appid), {})
        if not app_data.get("success"):
            print(f"[STEAM] API success=false appid={appid}: {data}")
            failed_appids.append(appid)
            continue

        game_data = app_data.get("data")
        if not game_data:
            print(f"[STEAM] Pas de data pour appid={appid}")
            failed_appids.append(appid)
            continue

        games_details.append(game_data)

    if failed_appids:
        print(f"[STEAM] {len(failed_appids)} appids en échec: {failed_appids}")

    print(f"[STEAM] {len(games_details)}/{len(game_ids)} jeux récupérés")
    return games_details