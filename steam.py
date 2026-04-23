import os
import time

import requests
from dotenv import load_dotenv

def get_all_steam_apps(api_key = None):
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
        print(apps)
        final_list = [{'appid': item['appid'], 'name': item['name']} for item in apps]
        all_apps.extend(final_list)
        print(f'{len(all_apps)} apps récupérées...')
        if data['response'].get('have_more_results'):
            last_appid = data['response']['last_appid']
            time.sleep(0.5)
        else:
            break

    return all_apps
