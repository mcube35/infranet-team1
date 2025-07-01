from pymongo import MongoClient

mongo_client = MongoClient("mongodb://localhost:27017")
mongo_db = mongo_client["intranet"]