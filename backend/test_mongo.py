from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client["nba_pairs"]

db.test.insert_one({"hello": "world"})
doc = db.test.find_one({"hello": "world"})

print("Mongo test document:", doc)
