import os
import subprocess
from pathlib import Path

from pymongo import MongoClient

from deals import IsThereAnyDeal
from utils import dump_backup


DB_NAME = "steam_prediction"
COLLECTION_NAME = "games"
RESTORE_PATH = "./backups/base_2_tmp_246"


def get_mongo_collection(collection_name=COLLECTION_NAME, db_name=DB_NAME):
    mongo_uri = os.getenv("MONGO_URI", "mongodb://root:example@mongodb:27017/")
    client = MongoClient(
        mongo_uri,
        authSource="admin",
        serverSelectionTimeoutMS=5000,
    )
    db = client[db_name]
    return db[collection_name]


def restore_backup():
    mongo_uri = os.getenv("MONGO_URI", "mongodb://root:example@mongodb:27017/")
    print(f"[RESTORE] depuis {RESTORE_PATH}")

    result = subprocess.run(
        [
            "mongorestore",
            "--uri", mongo_uri,
            "--authenticationDatabase", "admin",
            "--drop",
            "--nsInclude=steam_prediction.*",
            RESTORE_PATH,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"[RESTORE] ERROR: {result.stderr}")
        raise RuntimeError(result.stderr)

    print("[RESTORE] OK")


def main():
    print("[MAIN] restore backup steam_data_1")
    restore_backup()

    games_col = get_mongo_collection()
    print(f"[MAIN] total docs: {games_col.count_documents({})}", flush=True)
    IsThereAnyDeal(games_col)


    dump_backup('end')
    print("[MAIN] done")


if __name__ == "__main__":
    main()