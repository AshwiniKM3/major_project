from celery import shared_task
import json
import redis
from Queueasy.settings import redis_instance
from datetime import datetime


@shared_task(name='main.tasks.update_status_to_opened')
def change_status_to_opened(user_id):
    user_data = redis_instance.hgetall(user_id)
    if user_data:
        user_data = {k.decode('utf-8'): v.decode('utf-8') for k, v in user_data.items()}
        if user_data['status'] == 'waiting':
            # Log old status before changing
            old_status = user_data['status']
            user_data['status'] = 'opened'
            redis_instance.hset(user_id, mapping=user_data)

            # Update the queue
            queue = redis_instance.lrange('queue', 0, -1)
            updated_queue = []
            for item in queue:
                data = json.loads(item)
                if data['user_id'] == user_id:
                    data['status'] = 'opened'
                updated_queue.append(json.dumps(data))

            # Clear the queue and re-insert the updated items
            redis_instance.delete('queue')
            for item in reversed(updated_queue):  # Reversed because LPUSH adds to the front
                redis_instance.lpush('queue', item)

    

            

@shared_task(name='main.tasks.update_status_to_missed')
def change_status_to_missed(user_id):
    # Check the type of the user_id key
    key_type = redis_instance.type(user_id)
    if key_type != b'hash':
        print(f"The key '{user_id}' is of type '{key_type.decode('utf-8')}'. Cannot perform hset.")
        return  # or handle the situation as appropriate

    user_data = redis_instance.hgetall(user_id)
    if user_data:
        user_data = {k.decode('utf-8'): v.decode('utf-8') for k, v in user_data.items()}
        if user_data['status'] == 'opened':
            user_data['status'] = 'missed'
            redis_instance.hset(user_id, mapping=user_data)

            # Update the queue
            queue = redis_instance.lrange('queue', 0, -1)
            updated_queue = []
            removed = False  # Flag to check if user was removed from queue

            for item in queue:
                data = json.loads(item)
                if data['user_id'] == user_id:  # User should be removed
                    removed = True  # Mark that user was removed
                    continue  # Skip adding this user to the updated queue
                # Decrement the people_ahead count for each remaining user
                data['people_ahead'] = max(0, int(data['people_ahead']) - 1)
                updated_queue.append(json.dumps(data))

            # If the user was removed, clear the queue and reinsert remaining items
            if removed:
                redis_instance.delete('queue')  # Clear the queue
                for item in reversed(updated_queue):  # Reinsert remaining items
                    redis_instance.lpush('queue', item)

                # Prepare missed slot data
                missed_slot_entry = {
                    "user_id": user_id,
                    "name": user_data.get('name'),
                    "email": user_data.get('email'),
                    "timestamp": user_data.get('timestamp'),  # Record the time of missing
                    "time_slot_start": user_data.get('time_slot_start'),
                    "time_slot_end": user_data.get('time_slot_end'),
                    "number_of_people": user_data.get('number_of_people'),
                }

                redis_instance.rpush(f'missed_slots', json.dumps(missed_slot_entry))  # Adjust the key to not include user_id

            else:
                print(f"No user found in queue for user_id: {user_id}")





         

