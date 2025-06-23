from db import mongo_db

def get_fs():
    from gridfs import GridFS
    return GridFS(mongo_db)