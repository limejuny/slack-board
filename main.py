import os
import json
import redis
import uvicorn
from fastapi import FastAPI

app = FastAPI()

# Create a Redis client and subscriber instance
redis_client = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"),
                           port=6379,
                           db=0,
                           password=os.getenv("REDIS_PASSWORD", ""),
                           username=os.getenv("REDIS_USERNAME", ""))
redis_subscriber = redis_client.pubsub()

channel = os.getenv("REDIS_CHANNEL", "channel")
# Subscribe to the channel(s) you're interested in
redis_subscriber.subscribe(channel)


# Define a callback function
# that will be called each time a message is received
def handle_message(message):
    data = message['data']
    # if data is initial message, ignore it
    if data == 1:
        return
    if data == b'quit':
        redis_subscriber.unsubscribe()
    else:
        with open('data.json', 'w') as f:
            print(data)
            f.write(data.decode('utf-8'))


# Start listening for messages on the subscribed channels
def start_subscriber():
    while True:
        message = redis_subscriber.get_message()
        if message:
            handle_message(message)


# Define a FastAPI route that publishes JSON data
# to Redis and returns a 200 response
@app.post("/")
async def publish_data(data: dict):
    json_data = json.dumps(data)
    redis_client.publish(channel, json_data)
    return {"message": "Data published successfully."}


# Start the subscriber and the FastAPI app using Uvicorn
if __name__ == "__main__":
    import multiprocessing
    p = multiprocessing.Process(target=start_subscriber)
    p.start()
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
