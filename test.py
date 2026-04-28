import pymongo
client = pymongo.MongoClient("mongodb://root:example@localhost:27017/")
col = client["stea_prediction"]["games"]
print(f"Total games: {col.count_documents({})}")
print(f"With release_year: {col.count_documents({'release_year': {'$exists': True}})}")
print(f"Without release_year: {col.count_documents({'release_year': {'$exists': False}})}")