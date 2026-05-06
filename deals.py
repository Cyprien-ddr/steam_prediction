#!/usr/bin/env python
import os
import re
import sys
import subprocess
import unicodedata
import requests

from dotenv import load_dotenv
from pymongo import UpdateOne

from utils import dump_backup
from steam import get_games_info

CP1252_REPLACEMENTS = {
    "\x80": " euro ",
    "\x81": " ",
    "\x82": "'",
    "\x83": "f",
    "\x84": '"',
    "\x85": "...",
    "\x86": " ",
    "\x87": " ",
    "\x88": "^",
    "\x89": " ",
    "\x8A": "S",
    "\x8B": "<",
    "\x8C": "OE",
    "\x8D": " ",
    "\x8E": "Z",
    "\x8F": " ",
    "\x90": " ",
    "\x91": "'",
    "\x92": "'",
    "\x93": '"',
    "\x94": '"',
    "\x95": " ",
    "\x96": "-",
    "\x97": "-",
    "\x98": "~",
    "\x99": " ",
    "\x9A": "s",
    "\x9B": ">",
    "\x9C": "oe",
    "\x9D": " ",
    "\x9E": "z",
    "\x9F": "Y",

    "€": " euro ",
    "‚": "'",
    "ƒ": "f",
    "„": '"',
    "…": "...",
    "†": " ",
    "‡": " ",
    "ˆ": "^",
    "‰": " ",
    "Š": "S",
    "‹": "<",
    "Œ": "OE",
    "Ž": "Z",
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "•": " ",
    "–": "-",
    "—": "-",
    "˜": "~",
    "™": " ",
    "š": "s",
    "›": ">",
    "œ": "oe",
    "ž": "z",
    "Ÿ": "Y",
    "&": "and",

    "©": " ",
    "®": " ",
    "º": " ",
    "ª": " ",
    "°": " ",
}


def sanitize_title(s: str) -> str:
    if not s:
        return ""

    s = str(s)

    for old, new in CP1252_REPLACEMENTS.items():
        s = s.replace(old, new)

    s = unicodedata.normalize("NFKC", s)
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower()

    s = re.sub(r"\b(tm|r|c)\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    return s


def normalize_str(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def norm_people(items):
    out = set()
    for item in items or []:
        if isinstance(item, str):
            v = normalize_str(item)
            if v:
                out.add(v)
        elif isinstance(item, dict):
            v = normalize_str(item.get("name", ""))
            if v:
                out.add(v)
    return out


class IsThereAnyDeal:
    def __init__(self, db_name):
        load_dotenv()
        self.db = db_name
        self.api_key = os.getenv("API_KEY")
        self.base_url = "https://api.isthereanydeal.com"
        self.since_year = 2016
        print(f"db len: {self.db.count_documents({})}")
        print(f"fields: {self.db.find_one()}")
        self.get_games_info()

    def build_params(self, extra: dict | None = None) -> dict:
        params = {"key": self.api_key}
        if extra:
            params.update(extra)
        return params


    def flush_batch(self, operations: list, all_game_ids: list[str]):
        if not operations and not all_game_ids:
            return [], []

        if operations:
            print(f"[FLUSH] saving {len(operations)} id/type operations", flush=True)
            self.db.bulk_write(operations, ordered=False)

        if all_game_ids:
            print(f"[FLUSH] enriching {len(all_game_ids)} itad ids", flush=True)

            overview = self.get_price_overview(all_game_ids)
            if overview:
                self.db.bulk_write(overview, ordered=False)
            print('bulk overview', flush=True)
            current = self.get_current_prices(all_game_ids)
            if current:
                self.db.bulk_write(current, ordered=False)
            print('bulk current', flush=True)
            hist_low = self.get_history_low(all_game_ids)
            if hist_low:
                self.db.bulk_write(hist_low, ordered=False)
            print('bulk hist_low', flush=True)
            log_price = self.get_price_history_log(all_game_ids)
            if log_price:
                self.db.bulk_write(log_price, ordered=False)
            print("[FLUSH] flushing batch finished", flush=True)
            dump_backup("base_3_tmp")

        return [], []

    def get_games_info(self):
        titles_to_search = list(self.db.find(
            {
                "name": {"$ne": None},
                "$or": [
                    {"itad_id": {"$exists": False}},
                    {"itad_id": None},
                    {"itad_id": ""}
                ]
            },
            {"name": 1, "appid": 1, "_id": 0}
        ))

        print(f"[ITAD] len to process: {len(titles_to_search)}", flush=True)

        operations = []
        all_game_ids = []

        for idx, title in enumerate(titles_to_search, start=1):
            raw_title_name = title.get("name")
            title_name = sanitize_title(raw_title_name)
            if not title_name:
                continue

            games = self.search_games(raw_title_name)
            print(
                f"[{idx}/{len(titles_to_search)}] "
                f"name: {raw_title_name}, sanitize: {title_name}, games: {games}",
                flush=True
            )

            games_buf = [
                game for game in games
                if sanitize_title(game.get("title", "")) == title_name and game.get("id")
            ]
            games_buf_id = [game["id"] for game in games_buf]
            print(f"[DEBUG][BUF] {games_buf}, {games_buf_id}", flush=True)

            if len(games_buf) == 1:
                operations.append(
                    UpdateOne(
                        {
                            "name": raw_title_name,
                            "$or": [
                                {"itad_id": {"$exists": False}},
                                {"itad_id": None},
                                {"itad_id": ""}
                            ]
                        },
                        {"$set": {
                            "itad_id": games_buf[0]["id"],
                            "type": games_buf[0]["type"]
                        }}
                    )
                )
                all_game_ids.append(games_buf[0]["id"])

            elif len(games_buf) > 1:
                steam_docs = list(self.db.find(
                    {
                        "name": raw_title_name,
                        "$or": [
                            {"itad_id": {"$exists": False}},
                            {"itad_id": None},
                            {"itad_id": ""}
                        ]
                    },
                    {"_id": 0, "appid": 1}
                ))

                steam_infos = get_games_info(steam_docs)
                itad_infos = self.get_itad_games_info(games_buf_id)

                for steam_info in steam_infos:
                    steam_devs = norm_people(steam_info.get("developers", []))
                    appid = steam_info.get("appid") or steam_info.get("steam_appid")
                    if not steam_devs or not appid:
                        continue

                    for itad_info in itad_infos:
                        itad_devs = norm_people(itad_info.get("developers", []))
                        itad_id = itad_info.get("id")
                        if not itad_devs or not itad_id:
                            continue

                        if steam_devs & itad_devs:
                            operations.append(
                                UpdateOne(
                                    {
                                        "name": raw_title_name,
                                        "appid": appid,
                                        "$or": [
                                            {"itad_id": {"$exists": False}},
                                            {"itad_id": None},
                                            {"itad_id": ""}
                                        ]
                                    },
                                    {"$set": {
                                        "itad_id": itad_id,
                                        "type": itad_info.get("type")
                                    }}
                                )
                            )
                            all_game_ids.append(itad_id)
                            print(
                                f"[DEBUG][MATCH] {raw_title_name} | "
                                f"appid={appid} <-> itad_id={itad_id}",
                                flush=True
                            )
                            break

            if len(all_game_ids) >= 200:
                operations, all_game_ids = self.flush_batch(operations, all_game_ids)


        operations, all_game_ids = self.flush_batch(operations, all_game_ids)


    def get_itad_games_info(self, game_ids: list):
        itad_infos = []
        url = f"{self.base_url}/games/info/v2"

        for game_id in game_ids:
            try:
                params = self.build_params({"id": game_id})
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                itad_infos.append(data)
            except Exception as e:
                print(f"[games/info/v2][ITAD] FAILED {game_id}: {e}", flush=True)
                continue

        return itad_infos

    def get_price_overview(self, game_ids: list, country: str = "US") -> list:
        url = f"{self.base_url}/games/overview/v2"
        params = self.build_params({"country": country})
        operations = []

        try:
            response = self.http.post(url, params=params, json=game_ids, timeout=(10, 60))
            response.raise_for_status()
            data = response.json()

            for game_data in data.get("prices", []):
                game_id = game_data.get("id")
                best_price = game_data.get("current")
                hist_low = game_data.get("lowest")

                operations.append(
                    UpdateOne(
                        {"itad_id": game_id},
                        {"$set": {"best_price": best_price, "hist_low": hist_low}}
                    )
                )

        except requests.exceptions.Timeout as e:
            print(f"[overview v2][TIMEOUT] game_ids={len(game_ids)} err={e}", flush=True)
            return []
        except requests.exceptions.ConnectionError as e:
            print(f"[overview v2][CONNECTION] game_ids={len(game_ids)} err={e}", flush=True)
            return []
        except requests.exceptions.RequestException as e:
            print(f"[overview v2][REQUEST] game_ids={len(game_ids)} err={e}", flush=True)
            return []
        except ValueError as e:
            print(f"[overview v2][JSON] game_ids={len(game_ids)} err={e}", flush=True)
            return []
        except Exception as e:
            print(f"[overview v2][UNKNOWN] game_ids={len(game_ids)} err={e}", flush=True)
            return []

        return operations

    def get_current_prices(self, game_ids: list, country: str = "US") -> list:
        url = f"{self.base_url}/games/prices/v3"
        params = self.build_params({"country": country})
        operations = []

        try:
            response = requests.post(url, params=params, json=game_ids, timeout=60)
            response.raise_for_status()
            data = response.json()

            for item in data:
                game_id = item.get("id")
                deals = item.get("deals", [])
                active_deals = []

                for deal in deals:
                    active_deals.append({
                        "shop": deal.get("shop", {}).get("name", "?"),
                        "price": deal.get("price"),
                        "regular_price": deal.get("regular"),
                        "url": deal.get("url", ""),
                    })

                operations.append(
                    UpdateOne(
                        {"itad_id": game_id},
                        {"$set": {"current_price": active_deals}}
                    )
                )

        except requests.exceptions.Timeout as e:
            print(f"[prices v3][TIMEOUT] game_ids={len(game_ids)} err={e}", flush=True)
            return []

        except requests.exceptions.ConnectionError as e:
            print(f"[prices v3][CONNECTION] game_ids={len(game_ids)} err={e}", flush=True)
            return []

        except requests.exceptions.RequestException as e:
            print(f"[prices v3][REQUEST] game_ids={len(game_ids)} err={e}", flush=True)
            return []

        except Exception as e:
            print(f"[prices v3][UNKNOWN] game_ids={len(game_ids)} err={e}", flush=True)
            return []

        return operations

    def get_history_low(self, game_ids: list[str], country: str = "US") -> list:
        url = f"{self.base_url}/games/historylow/v1"
        params = self.build_params({"country": country})
        operations = []

        try:
            response = requests.post(url, params=params, json=game_ids, timeout=60)
            response.raise_for_status()
            data = response.json()

            for item in data:
                game_id = item.get("id")
                lows = item.get("historyLow")
                if lows:
                    operations.append(
                        UpdateOne(
                            {"itad_id": game_id},
                            {"$set": {"historical_low": lows}}
                        )
                    )

        except requests.exceptions.Timeout as e:
            print(f"[historylow v1][TIMEOUT] game_ids={len(game_ids)} err={e}", flush=True)
            return []

        except requests.exceptions.ConnectionError as e:
            print(f"[historylow v1][CONNECTION] game_ids={len(game_ids)} err={e}", flush=True)
            return []

        except requests.exceptions.RequestException as e:
            print(f"[historylow v1][REQUEST] game_ids={len(game_ids)} err={e}", flush=True)
            return []

        except Exception as e:
            print(f"[historylow v1][UNKNOWN] game_ids={len(game_ids)} err={e}", flush=True)
            return []

        return operations

    def get_price_history_log(
        self,
        game_ids: list[str],
        shop_id: str | None = None,
        country: str = "US",
        since: str = "2016-01-01T00:00:00Z",
    ) -> list:
        url = f"{self.base_url}/games/history/v2"
        operations = []

        for game_id in game_ids:
            try:
                params = self.build_params({
                    "id": game_id,
                    "country": country,
                    "since": since,
                })
                if shop_id:
                    params["shop"] = shop_id

                response = requests.get(url, params=params, timeout=60)
                response.raise_for_status()
                data = response.json()

                entries_since = []

                for item in data:
                    shop_name = item.get("shop", {}).get("name", None)
                    deal = item.get("deal", {})
                    ts = item.get("timestamp", "")

                    entries_since.append({
                        "shop": shop_name,
                        "date": ts,
                        "price": deal.get("price", {}).get("amount", None),
                    })

                entries_since.sort(key=lambda x: x["date"], reverse=True)

                if entries_since:
                    operations.append(
                        UpdateOne(
                            {"itad_id": game_id},
                            {"$set": {"log_price": entries_since}}
                        )
                    )

            except requests.exceptions.Timeout as e:
                print(f"[history v2][TIMEOUT] game_id={game_id} err={e}", flush=True)
                continue

            except requests.exceptions.ConnectionError as e:
                print(f"[history v2][CONNECTION] game_id={game_id} err={e}", flush=True)
                continue

            except requests.exceptions.RequestException as e:
                print(f"[history v2][REQUEST] game_id={game_id} err={e}", flush=True)
                continue

            except Exception as e:
                print(f"[history v2][UNKNOWN] game_id={game_id} err={e}", flush=True)
                continue

        return operations

    def backup_db(self, name: str):
        mongo_uri = os.getenv("MONGO_URI", "mongodb://root:example@mongodb:27017/")
        backup_name = f"itad_data_{name}"
        out_path = f"./db/{backup_name}"

        print(f"[BACKUP] dump MongoDB -> {out_path}", flush=True)

        result = subprocess.run(
            [
                "mongodump",
                "--uri", mongo_uri,
                "--authenticationDatabase", "admin",
                "--db", "steam_prediction",
                "--out", out_path,
            ],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"[BACKUP] ERROR: {result.stderr}", flush=True)
            raise RuntimeError(result.stderr)

        print(f"[BACKUP] SUCCEED: {backup_name}", flush=True)

    def search_games(self, title: str, limit: int = 20) -> list[dict]:
        url = f"{self.base_url}/games/search/v1"
        params = self.build_params({"title": title, "results": limit})

        try:
            response = requests.get(url, params=params, timeout=(10, 60))
            response.raise_for_status()
            data = response.json()
            return [
                {
                    "id": game.get("id"),
                    "title": game.get("title"),
                    "type": game.get("type"),
                    "mature": game.get("mature", False),
                }
                for game in data
            ]
        except requests.exceptions.Timeout as e:
            print(f"[TIMEOUT] search_games {title}: {e}", flush=True)
            return []
        except requests.exceptions.RequestException as e:
            print(f"[FAILED] search_games {title}: {e}", flush=True)
            return []