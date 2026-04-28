import pymongo


def clean_before_itad(col):
    print("--- Cleaning before ITAD ---")

    # 1. Remove games without a name
    result = col.delete_many({"name": {"$in": [None, ""]}})
    print(f"{result.deleted_count} games without a name removed.")

    # 2. Clean game names (trailing spaces, ™, ®)
    games = col.find({}, {"name": 1})
    cleaned_count = 0
    for game in games:
        original = game.get("name", "")
        cleaned = original.strip()
        cleaned = cleaned.replace("™", "").replace("®", "").strip()
        if cleaned != original:
            col.update_one(
                {"_id": game["_id"]},
                {"$set": {"name": cleaned}}
            )
            cleaned_count += 1
    print(f"{cleaned_count} game names cleaned (spaces, ™, ®).")
    print(f"Total games remaining: {col.count_documents({})}")
    print("--- Cleaning before ITAD done ---\n")


def clean_after_itad(col):
    print("--- Cleaning after ITAD ---")

    # 1. Remove games not matched on ITAD
    result = col.delete_many({"itad_id": {"$exists": False}})
    print(f"{result.deleted_count} games without itad_id removed.")

    # 2. Simplify current_price, keep only useful fields
    games_with_price = col.find({"current_price": {"$exists": True}})
    for game in games_with_price:
        cleaned_deals = []
        for deal in game.get("current_price", []):
            price = deal.get("price", {})
            cleaned_deals.append({
                "shop": deal.get("shop"),
                "price_usd": price.get("amount"),
                "currency": price.get("currency", "USD"),
                "url": deal.get("url"),
            })
        col.update_one(
            {"_id": game["_id"]},
            {"$set": {"current_price": cleaned_deals}}
        )
    print("current_price simplified.")

    # 3. Rename hist_low to historical_low and simplify
    games_with_hist = col.find({"hist_low": {"$exists": True, "$ne": None}})
    for game in games_with_hist:
        hist = game.get("hist_low") or {}
        price = hist.get("price") or {}
        cleaned_hist = {
            "shop": hist.get("shop", {}).get("name"),
            "price_usd": price.get("amount"),
            "currency": price.get("currency", "USD"),
            "cut": hist.get("cut"),
            "date": hist.get("timestamp"),
        }
        col.update_one(
            {"_id": game["_id"]},
            {
                "$set": {"historical_low": cleaned_hist},
                "$unset": {"hist_low": ""}
            }
        )
    print("hist_low renamed to historical_low and simplified.")

    # 4. Remove useless fields
    col.update_many({}, {"$unset": {
        "price_change_number": "",
        "best_price": "",
    }})
    print("Useless fields removed (price_change_number, best_price).")

    print(f"\nTotal games remaining: {col.count_documents({})}")
    print(f"With current_price: {col.count_documents({'current_price': {'$exists': True}})}")
    print(f"With historical_low: {col.count_documents({'historical_low': {'$exists': True}})}")
    print("--- Cleaning after ITAD done ---\n")

    # 5. Convertir les dates de log_price en objets datetime
    print("Conversion des dates de log_price...")
    games_with_logs = col.find({"log_price": {"$exists": True, "$ne": []}})
    converted_count = 0
    
    for game in games_with_logs:
        updated_logs = []
        needs_update = False
        
        for log in game.get("log_price", []):
            if isinstance(log.get("date"), str):
                try:
                    # Convertit le format ISO '2025-10-06T19:18:10+02:00' en datetime
                    log["date"] = datetime.fromisoformat(log["date"])
                    needs_update = True
                except ValueError:
                    pass # Si la date est mal formatée, on la laisse tranquille
            updated_logs.append(log)
            
        if needs_update:
            col.update_one(
                {"_id": game["_id"]},
                {"$set": {"log_price": updated_logs}}
            )
            converted_count += 1
            
    print(f"{converted_count} historiques de prix ont eu leurs dates converties.")


if __name__ == "__main__":
    client = pymongo.MongoClient("mongodb://root:example@localhost:27017/")
    col = client["stea_prediction"]["games"]
    clean_before_itad(col)
    clean_after_itad(col)