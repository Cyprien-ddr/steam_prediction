import pymongo

from deals import IsThereAnyDeal
from steam import get_all_steam_apps

def main():
    myclient = pymongo.MongoClient("mongodb://root:example@localhost:27017/")
    steam_namedb = myclient["stea_prediction"]
    steam_namecol = steam_namedb["games"]
    print("Connected to MongoDB!")
    steam_namecol.insert_many(get_all_steam_apps())
    print("Inserted documents!")
    for steam_name in steam_namecol.find():
        print(steam_name)
    print("Get More Data")
    IsThereAnyDeal(steam_namecol)
    print("Done!")

if __name__ == "__main__":
    main()