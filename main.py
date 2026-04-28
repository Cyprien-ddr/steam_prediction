import pymongo

from deals import IsThereAnyDeal
from steam import get_all_steam_apps, enrich_release_dates
from clean import clean_before_itad, clean_after_itad
from visualize import (plot_last_modified_by_year, plot_release_years,
                       plot_current_price_distribution, plot_top_discounts,
                       plot_historical_low_vs_current)

BATCH_SIZE = 50  # number of new games to process per run


def get_last_appid(meta_col):
    """Retrieve the last processed appid from the metadata collection."""
    doc = meta_col.find_one({"_id": "progress"})
    return doc.get("last_appid", 0) if doc else 0


def save_last_appid(meta_col, last_appid):
    """Save the last processed appid to the metadata collection."""
    meta_col.update_one(
        {"_id": "progress"},
        {"$set": {"last_appid": last_appid}},
        upsert=True
    )

def reset_database(client, reset=False):
    """Drop all game data and progress. Set reset=True to confirm."""
    if not reset:
        return
    db = client["stea_prediction"]
    db["games"].drop()
    db["meta"].drop()
    print("Database reset complete.")

def main():
    client = pymongo.MongoClient("mongodb://root:example@localhost:27017/")

    reset_database(client, reset=True) 

    db = client["stea_prediction"]
    steam_namecol = db["games"]
    meta_col = db["meta"]  # separate collection to store progress

    print("Connected to MongoDB!")

    # Retrieve all apps from Steam
    all_apps = get_all_steam_apps()

    # Find where we left off
    last_appid = get_last_appid(meta_col)
    if last_appid > 0:
        print(f"Resuming from appid {last_appid}...")
        remaining = [a for a in all_apps if a["appid"] > last_appid]
    else:
        print("Starting fresh...")
        remaining = all_apps

    if not remaining:
        print("No new games to process, jumping straight to visualizations.")
    else:
        # Take next batch
        batch = remaining[:BATCH_SIZE]
        print(f"{len(remaining)} games remaining — processing next {len(batch)}.")

        steam_namecol.insert_many(batch)
        print(f"{len(batch)} games inserted!")

        clean_before_itad(steam_namecol)
        IsThereAnyDeal(steam_namecol)
        clean_after_itad(steam_namecol)
        enrich_release_dates(steam_namecol)

        # Save progress
        save_last_appid(meta_col, batch[-1]["appid"])
        print(f"Progress saved at appid {batch[-1]['appid']}.")

    print(f"Total games in database: {steam_namecol.count_documents({})}")

    plot_last_modified_by_year(steam_namecol)
    plot_release_years(steam_namecol)
    plot_current_price_distribution(steam_namecol)
    plot_top_discounts(steam_namecol, top_n=10)
    plot_historical_low_vs_current(steam_namecol, top_n=10)

    print("Done!")


if __name__ == "__main__":
    main()


