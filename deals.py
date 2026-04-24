#!/usr/bin/env python
from symtable import Class

import requests
import os
import sys
from dotenv import load_dotenv
from pymongo import UpdateOne


class IsThereAnyDeal(object):

    def __init__(self, db_name):
        load_dotenv()
        self.db = db_name
        self.api_key = os.getenv('API_KEY')
        self.base_url = 'https://api.isthereanydeal.com'
        self.since_year = 2016
        self.get_games_info()

    @staticmethod
    def get_headers() -> dict:
        return {'Content-Type': 'application/json'}

    def build_params(self, extra: dict = None) -> dict:
        params = {'key': self.api_key}
        if extra:
            params.update(extra)
        return params

    def get_games_info(self):
        titles_to_search = list(self.db.find(
            { 'name': { '$ne': None } },
            {'name':1, '_id':0}))
        operations = []
        all_game_ids = []
        games = None
        for title in titles_to_search:
            title_name = title.get('name')
            games = self.search_games(title_name)
            for game in games:
                if game['title'] == title_name and game['id']:
                    operations.append(
                        UpdateOne(
                        {"name": title_name},
                        {"$set": {"itad_id": game['id']}}
                        ))
                    all_game_ids.append(game['id'])

        if not all_game_ids:
            raise Exception(f'No game found in IsThereAnyDeal: {games}')

        self.db.bulk_write(operations)
        overview = self.get_price_overview(all_game_ids)
        if overview:
            self.db.bulk_write(overview)

        current = self.get_current_prices(all_game_ids)
        if current:
            self.db.bulk_write(current)

        hist_low = self.get_history_low(all_game_ids)
        if hist_low:
            self.db.bulk_write(hist_low)

        log_price = self.get_price_history_log(all_game_ids)
        if log_price:
            self.db.bulk_write(log_price)

    def get_price_overview(self, game_ids: list, country: str = 'US') -> list:
        url = f'{self.base_url}/games/overview/v2'
        params = self.build_params({'country': country})

        response = requests.post(url, params=params, json=game_ids)
        response.raise_for_status()
        data = response.json()

        operations = []
        for game_data in data.get('prices', []):
            game_id = game_data.get('id')
            best_price = game_data.get('current')
            hist_low = game_data.get('lowest')
            operations.append(
                UpdateOne(
                    {"itad_id": game_id},
                    {"$set": {"best_price": best_price, "hist_low": hist_low}}
                ))
        return operations

    def search_games(self, title: str, limit: int = 20) -> list[dict]:
        url = f'{self.base_url}/games/search/v1'
        params = self.build_params({'title': title, 'results': limit})

        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        games = []
        for game in data:
            games.append({
                'id': game.get('id'),
                'title': game.get('title'),
                'type': game.get('type'),
                'mature': game.get('mature', False),
            })
        return games

    def get_current_prices(self, game_ids: list, country: str = 'US') -> list:
        url = f'{self.base_url}/games/prices/v3'
        params = self.build_params({'country': country})

        response = requests.post(url, params=params, json=game_ids)
        response.raise_for_status()
        data = response.json()
        operations = []
        for item in data:

            game_id = item.get('id')
            deals = item.get('deals', [])

            active_deals = []

            for deal in deals:
                price_new = deal.get('price')
                price_old = deal.get('regular')
                shop = deal.get('shop', {}).get('name', '?')
                url_deal = deal.get('url', '')

                active_deals.append({
                    'shop': shop,
                    'price': price_new,
                    'regular_price': price_old,
                    'url': url_deal,
                })
            operations.append(
                UpdateOne(
                    {"itad_id": game_id},
                    {"$set": {"current_price": active_deals}}
                ))

        return operations

    def get_history_low(self, game_ids: list[str], country: str = 'US') -> list:

        url = f'{self.base_url}/games/historylow/v1'
        params = self.build_params({'country': country})

        response = requests.post(url, params=params, json=game_ids)
        response.raise_for_status()
        data = response.json()

        operations = []
        for item in data:
            game_id = item.get('id')
            lows = item.get('historyLow', None)
            if lows:
                operations.append(
                    UpdateOne(
                        {"itad_id": game_id},
                        {"$set": {"historical_low": lows}}
                    ))
        return operations

    def get_price_history_log(self,
                              game_ids: list[str],
                              shop_id: str | None = None,
                              country: str = 'US',
                              since: str = '2016-01-01T00:00:00Z'
                              ) -> list:
        url = f'{self.base_url}/games/history/v2'
        operations = []
        for game_id in game_ids:
            params = self.build_params({
                'id': game_id,
                'country': country,
                'since': since,
            })

            if shop_id:
                params['shop'] = shop_id

            response = requests.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            entries_since = []

            for item in data:
                shop_name = item.get('shop', {}).get('name', None)
                deal = item.get('deal', {})
                ts = item.get('timestamp', '')

                entries_since.append({
                    'shop': shop_name,
                    'date': ts,
                    'price': deal.get('price', {}).get('amount', None),
                })

            entries_since.sort(
                key=lambda x: x['date'],
                reverse=True
            )

            if entries_since:
                operations.append(
                    UpdateOne(
                        {"itad_id": game_id},
                        {"$set": {"log_price": entries_since}}
                    ))
        return operations
