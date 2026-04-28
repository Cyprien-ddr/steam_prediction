import pymongo

from deals import IsThereAnyDeal
from steam import get_all_steam_apps
from visualize import plot_last_modified_by_year, plot_release_years, plot_current_price_distribution, plot_top_discounts, plot_historical_low_vs_current
from clean import clean_before_itad, clean_after_itad
from steam import get_all_steam_apps, enrich_release_dates


def main():
    myclient = pymongo.MongoClient("mongodb://root:example@localhost:27017/")
    steam_namedb = myclient["stea_prediction"]
    steam_namecol = steam_namedb["games"]
    print("Connected to MongoDB!")

    steam_namecol.drop()  # remet la collection à zéro pour éviter les doublons
    
    all_apps = get_all_steam_apps()
    limited_apps = all_apps[:200]
    
    steam_namecol.insert_many(limited_apps)
    print(f"{len(limited_apps)} jeux insérés!")
    clean_before_itad(steam_namecol)
    print("Inserted documents!")
    #for steam_name in steam_namecol.find():
       #print(steam_name)
    print("Get More Data")
    IsThereAnyDeal(steam_namecol)
    print("Done!")
    clean_after_itad(steam_namecol)
    enrich_release_dates(steam_namecol)

    plot_last_modified_by_year(steam_namecol)
    plot_release_years(steam_namecol)
    plot_current_price_distribution(steam_namecol)
    plot_top_discounts(steam_namecol, top_n=10)
    plot_historical_low_vs_current(steam_namecol, top_n=10)

if __name__ == "__main__":
    main()