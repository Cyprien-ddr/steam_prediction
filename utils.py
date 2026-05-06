import os
import subprocess
from pathlib import Path


DB_NAME = "steam_prediction"
COLLECTION_NAME = "games"
RESTORE_PATH = "./backups/base_tmp_10"

def dump_backup(tag="steam_data_2"):
    mongo_uri = os.getenv("MONGO_URI", "mongodb://root:example@mongodb:27017/")

    base_path = Path("./backups")
    out_path = base_path / tag

    counter = 1
    while out_path.exists():
        out_path = base_path / f"{tag}_{counter}"
        counter += 1

    result = subprocess.run(
        [
            "mongodump",
            "--uri", mongo_uri,
            "--authenticationDatabase", "admin",
            "--db", DB_NAME,
            "--out", str(out_path),
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"[BACKUP] ERROR: {result.stderr}")
        raise RuntimeError(result.stderr)

    print(f"[BACKUP] OK -> {out_path}")