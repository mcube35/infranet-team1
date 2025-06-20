class TaskRepository:
    def __init__(self, collection):
        self.collection = collection

    def get_filtered_tasks(self, team=None, status=None, start_date=None, end_date=None):
        query = {}

        if team and team != '전체':
            query['team'] = team
        if status and status != '전체':
            query['status'] = status
        if start_date and end_date:
            query['due_date'] = {
                "$gte": start_date,
                "$lte": end_date
            }
        return self.collection.find(query).sort("due_date", -1)
    
    def daily_status_counts(self):
        result = self.collection.aggregate([
            {"$group": {
                "_id": {
                    "date": "$due_date",
                    "status": "$status"
                },
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id.date": 1}}
        ])
        return list(result)