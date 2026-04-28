import requests
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from pymongo import UpdateOne


class IsThereAnyDeal(object):

    def __init__(self, db_name):
        load_dotenv()
        self.db = db_name
        self.api_key = os.getenv('API_KEY')
        self.base_url = 'https://api.isthereanydeal.com'
        self.get_games_info()

    @staticmethod
    def get_headers() -> dict:
        return {'Content-Type': 'application/json'}

    def build_params(self, extra: dict = None) -> dict:
        params = {'key': self.api_key}
        if extra:
            params.update(extra)
        return params

    def chunk_list(self, lst, size=50): # J'ai réduit la taille des paquets à 50 pour soulager l'API
        """Split a list into chunks of max `size`"""
        for i in range(0, len(lst), size):
            yield lst[i:i + size]

    def _safe_request(self, method: str, url: str, **kwargs):
        """Helper function to handle rate limits (429) automatically with retries."""
        max_retries = 4
        for attempt in range(max_retries):
            response = requests.request(method, url, **kwargs)
            
            # Si on se fait bloquer par la limite de requêtes
            if response.status_code == 429:
                wait_time = (attempt + 1) * 3  # Va attendre 3s, puis 6s, puis 9s...
                print(f"⚠️ Erreur 429 (Trop de requêtes). Pause de {wait_time}s avant de réessayer...")
                time.sleep(wait_time)
                continue
                
            response.raise_for_status()
            return response.json()
            
        # Si ça échoue toujours après les tentatives
        response.raise_for_status()

    def search_one(self, title_name: str):
        """Search a single game on ITAD and return (title, itad_id) if found."""
        try:
            # Petite pause par défaut pour ne pas spammer
            time.sleep(0.5) 
            games = self.search_games(title_name)
            for game in games:
                if game['title'] == title_name and game['id']:
                    return title_name, game['id']
        except Exception as e:
            print(f"Error searching '{title_name}': {e}")
        return title_name, None

    def get_games_info(self):
        titles_to_search = list(self.db.find(
            {'name': {'$ne': None}, 'itad_id': {'$exists': False}}, # On cherche seulement ceux qui n'ont pas encore d'ID !
            {'name': 1, '_id': 0}
        ))
        title_names = [t.get('name') for t in titles_to_search if t.get('name')]

        all_game_ids = []
        operations = []

        if title_names:
            # On réduit les workers à 3 pour éviter de se faire bannir
            print(f"Searching {len(title_names)} new games on ITAD (with rate limit protection)...")
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(self.search_one, name): name for name in title_names}
                for future in as_completed(futures):
                    title_name, itad_id = future.result()
                    if itad_id:
                        operations.append(UpdateOne(
                            {"name": title_name},
                            {"$set": {"itad_id": itad_id}}
                        ))
                        all_game_ids.append(itad_id)

            if operations:
                self.db.bulk_write(operations)
                print(f"{len(operations)} new ITAD IDs saved.")
        else:
            print("No new games to search on ITAD.")

        # On récupère les IDs de toute la base pour mettre à jour les prix
        all_itad_docs = list(self.db.find({'itad_id': {'$exists': True}}, {'itad_id': 1, '_id': 0}))
        full_game_ids = [doc['itad_id'] for doc in all_itad_docs]

        if not full_game_ids:
            print("No games found on IsThereAnyDeal to fetch prices for.")
            return

        print(f"Fetching prices for {len(full_game_ids)} games...")
        
        overview = self.get_price_overview(full_game_ids)
        if overview:
            self.db.bulk_write(overview)
            print("Price overview retrieved.")

        current = self.get_current_prices(full_game_ids)
        if current:
            self.db.bulk_write(current)
            print("Current prices retrieved.")

        hist_low = self.get_history_low(full_game_ids)
        if hist_low:
            self.db.bulk_write(hist_low)
            print("Historical lows retrieved.")

    def search_games(self, title: str, limit: int = 5) -> list[dict]:
        url = f'{self.base_url}/games/search/v1'
        params = self.build_params({'title': title, 'results': limit})

        data = self._safe_request('GET', url, params=params)

        return [
            {
                'id': game.get('id'),
                'title': game.get('title'),
            }
            for game in data
        ]

    def get_price_overview(self, game_ids: list, country: str = 'US') -> list:
        url = f'{self.base_url}/games/overview/v2'
        params = self.build_params({'country': country})
        operations = []

        for chunk in self.chunk_list(game_ids):
            time.sleep(1) # Pause entre chaque paquet
            data = self._safe_request('POST', url, params=params, json=chunk)
            for game_data in data.get('prices', []):
                game_id = game_data.get('id')
                operations.append(UpdateOne(
                    {"itad_id": game_id},
                    {"$set": {"best_price": game_data.get('current'), "hist_low": game_data.get('lowest')}}
                ))
        return operations

    def get_current_prices(self, game_ids: list, country: str = 'US') -> list:
        url = f'{self.base_url}/games/prices/v3'
        params = self.build_params({'country': country})
        operations = []

        for chunk in self.chunk_list(game_ids):
            time.sleep(1) # Pause entre chaque paquet
            data = self._safe_request('POST', url, params=params, json=chunk)
            for item in data:
                game_id = item.get('id')
                active_deals = [
                    {
                        'shop': deal.get('shop', {}).get('name', '?'),
                        'price': deal.get('price'),
                        'regular_price': deal.get('regular'),
                        'url': deal.get('url', ''),
                    }
                    for deal in item.get('deals', [])
                ]
                operations.append(UpdateOne(
                    {"itad_id": game_id},
                    {"$set": {"current_price": active_deals}}
                ))
        return operations

    def get_history_low(self, game_ids: list, country: str = 'US') -> list:
        url = f'{self.base_url}/games/historylow/v1'
        params = self.build_params({'country': country})
        operations = []

        for chunk in self.chunk_list(game_ids):
            time.sleep(1) # Pause entre chaque paquet
            data = self._safe_request('POST', url, params=params, json=chunk)
            for item in data:
                game_id = item.get('id')
                lows = item.get('historyLow')
                if lows:
                    operations.append(UpdateOne(
                        {"itad_id": game_id},
                        {"$set": {"historical_low": lows}}
                    ))
        return operations