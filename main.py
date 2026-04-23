import pymongo

from steam import get_all_steam_apps

def main():
    myclient = pymongo.MongoClient("mongodb://root:example@mongodb:27017/")
    mydb = myclient["mydatabase"]
    mycol = mydb["customers"]
    for user in mycol.find():
        print(user)

    steam_namedb = mydb["stea_prediction"]
    steam_namecol = steam_namedb["games"]
    steam_namecol.insert_many(get_all_steam_apps())
    for steam_name in steam_namecol.find():
        print(steam_name)

if __name__ == "__main__":
    main()