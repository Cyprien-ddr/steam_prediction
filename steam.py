import os
import time

import requests
from dotenv import load_dotenv

def is_real_game(appid):
    url = "https://store.steampowered.com/api/appdetails"
    params = {
        "appids": appid
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    app_data = data.get(str(appid), {})
    if not app_data.get("success"):
        return False

    game_data = app_data.get("data", {})
    return game_data.get("type") == "game"

def get_all_steam_apps(api_key = None):
    load_dotenv()
    if not api_key:
        api_key = os.getenv('STEAM_API_KEY')
    if not api_key:
        raise ValueError("STEAM API key is missing")

    url = 'https://api.steampowered.com/IStoreService/GetAppList/v1/'
    all_apps = []
    all_apps_bis = []
    filtered_apps = []
    last_appid = 0

    while True:
        # TODO - Update the params to get only games
        params = {
            'key': api_key,
            'max_results': 4,
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
        print(apps)
        final_list = [{'appid': item['appid'], 'name': item['name']} for item in apps]
        all_apps.extend(final_list)
        if data['response'].get('have_more_results'):
            last_appid = data['response']['last_appid']
            time.sleep(0.5)
        else:
            break
        for item in apps:
            if is_real_game(item["appid"]):
                filtered_apps.append({
                    "appid": item["appid"],
                    "name": item["name"]
                })
        all_apps_bis.extend(final_list)
        break

    return all_apps_bis
    # return all_apps
