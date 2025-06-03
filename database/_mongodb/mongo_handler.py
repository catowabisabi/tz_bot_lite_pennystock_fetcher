import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))



import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv
from bson import json_util

load_dotenv(override=True)


from datetime import datetime, timezone
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")
ny_time = datetime.now(NY_TZ)
today_str = ny_time.strftime('%Y-%m-%d')

from program_starter.class_zeropro_starter import logger


class MongoHandler:
    def __init__(self, mongodb_connection_string = None):
        try:
            mongo_uri = os.getenv("MONGODB_CONNECTION_STRING")
            if mongodb_connection_string:
                mongo_uri = mongodb_connection_string
            self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
            self.db = self.client[os.getenv("MONGO_DBNAME", "TradeZero_Bot")]
        except Exception as e:
            print(f"Connection error: {e}")
            self.client = None
            self.db = None

    def is_connected(self):
        if not self.client:
            return False
        try:
            self.client.admin.command('ping')
            return True
        except ConnectionFailure:
            return False

    def find_collection(self, name):
        if not self.is_connected():
            return False
        collections = self.db.list_collection_names()
        return True if name in collections else []

    def create_collection(self, name):
        if not self.is_connected():
            logger.warning("Not connected to MongoDB")
            return False
        if name not in self.db.list_collection_names():
            logger.info(f"Collection not found. Creating collection: {name}")
            self.db.create_collection(name)
            return True
        logger.warning(f"Collection already exists: {name}")
        return False

    def create_doc(self, collection_name, doc):
        if not self.is_connected():
            return None
        if collection_name not in self.db.list_collection_names():
            return None
        try:
            # 使用带时区的日期时间
            doc["today_date"] = datetime.now(NY_TZ).strftime('%Y-%m-%d')
            doc["created_at"] = datetime.now(timezone.utc)
            result = self.db[collection_name].insert_one(doc)
            return result.inserted_id
        except Exception as e:
            print(f"Insert error: {e}")
            return None

    def find_doc(self, collection_name, query):
        if not self.is_connected():
            return []
        if collection_name not in self.db.list_collection_names():
            return []
        try:
            return list(self.db[collection_name].find(query))
        except Exception as e:
            print(f"Find error: {e}")
            return []

    def update_doc(self, collection_name, query, update):
        if not self.is_connected():
            return None
        if collection_name not in self.db.list_collection_names():
            return None
        try:
            result = self.db[collection_name].update_many(query, {'$set': update})
            return result.modified_count  # 回傳更新的筆數
        except Exception as e:
            print(f"Update error: {e}")
            return None

    def upsert_doc(self, collection_name, query_keys: dict, new_data: dict):
        if not self.is_connected():
            return None
        if collection_name not in self.db.list_collection_names():
            return None

        try:
            # 使用带时区的日期时间
            new_data["today_date"] = datetime.now(NY_TZ).strftime('%Y-%m-%d')
            new_data["updated_at"] = datetime.now(timezone.utc)

            result = self.db[collection_name].update_one(
                filter=query_keys,
                update={"$set": new_data},
                upsert=True
            )
            return {
                "matched_count": result.matched_count,
                "modified_count": result.modified_count,
                "upserted_id": str(result.upserted_id) if result.upserted_id else None
            }
        except Exception as e:
            print(f"Upsert error: {e}")
            return None
        
    
    def upsert_top_list(self, collection_name: str, new_symbols: list):
        if not self.is_connected():
            return None
        if collection_name not in self.db.list_collection_names():
            return None

        try:
            # 使用带时区的日期时间
            today_str = datetime.now(NY_TZ).strftime('%Y-%m-%d')
            query = {"today_date": today_str}

            existing_doc = self.db[collection_name].find_one(query)

            if existing_doc and "top_list" in existing_doc:
                combined_list = list(set(existing_doc["top_list"] + new_symbols))
            else:
                combined_list = new_symbols

            result = self.db[collection_name].update_one(
                filter=query,
                update={"$set": {
                    "today_date": today_str,
                    "top_list": combined_list,
                    "updated_at": datetime.now(timezone.utc)
                }},
                upsert=True
            )

            return {
                "matched_count": result.matched_count,
                "modified_count": result.modified_count,
                "upserted_id": str(result.upserted_id) if result.upserted_id else None
            }

        except Exception as e:
            print(f"Upsert error: {e}")
            return None
    
    def delete_doc(self, collection_name, query):
        if not self.is_connected():
            return None
        if collection_name not in self.db.list_collection_names():
            return None
        try:
            result = self.db[collection_name].delete_many(query)
            return result.deleted_count
        except Exception as e:
            print(f"Delete error: {e}")
            return None
        

if __name__ == "__main__":
    mongo_handler = MongoHandler()
    print(f"Connected: {mongo_handler.is_connected()}")
    print(f"Collection is created: {mongo_handler.create_collection("test_collection")}")
    print(f"Collection is found: {mongo_handler.find_collection('test_collection')}")

    print(f"Document is created: {mongo_handler.create_doc('test_collection', {'name': 'John', 'age': 30})}")
    print(f"Document is found: {mongo_handler.find_doc('test_collection', {'name': 'John'})}")

    print(f"Document is updated: {mongo_handler.update_doc('test_collection', {'name': 'John'}, {'age': 31})}")
    print(f"Document is found: {mongo_handler.find_doc('test_collection', {'name': 'John'})}")
    print(f"Document is deleted: {mongo_handler.delete_doc('test_collection', {'name': 'John'})}")

    print(f"Document is upserted: {mongo_handler.upsert_doc('test_collection', {'name': 'John'}, {'age': 31})}")
    print(f"Document is found: {mongo_handler.find_doc('test_collection', {'name': 'John'})}")
    
