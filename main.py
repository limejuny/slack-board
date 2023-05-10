import json
import logging
import os
from multiprocessing import Process

import redis
import uvicorn
from fastapi import FastAPI, Request
from PIL import Image, ImageDraw, ImageFont
from slack import WebClient

log = logging.getLogger()
log.setLevel(logging.INFO)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
handler.setFormatter(formatter)
log.addHandler(handler)

app = FastAPI()

# Create a Redis client and subscriber instance
redis_client = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"),
                           port=6379,
                           db=0,
                           password=os.getenv("REDIS_PASSWORD", ""),
                           username=os.getenv("REDIS_USERNAME", ""))
channel = os.getenv("REDIS_CHANNEL", "channel")
# Subscribe to the channel(s) you're interested in
slack_client = WebClient(token=os.getenv("SLACK_BOT_TOKEN", ""))

fontsize = 48
font = ImageFont.truetype("/app/font.ttf", fontsize)


def create_image_with_text(wh, text):
    width, height = wh
    img = Image.new('RGB', (520, fontsize + 4), "black")
    draw = ImageDraw.Draw(img)
    draw.text((width, height), text, font=font, fill=(0xB0, 0xFF, 0x2A))
    return img


def save_gif(file_id, text):
    frames = []
    x, y = 0, 0
    start_x = 20
    diff = 14
    text = text + "　" * 2
    for i in range((font.font.getsize(text)[0][0] + start_x) // diff - 1):
        new_frame = create_image_with_text((x + start_x, y), text * 10)
        frames.append(new_frame)
        x -= diff
    frames[0].save(f'{file_id}.gif',
                   format="GIF",
                   append_images=frames[1:],
                   save_all=True,
                   duration=10,
                   loop=0)


# Define a callback function
# that will be called each time a message is received
def handle_message(message):
    log.info(message)
    if message['type'] == 'message':
        data = json.loads(message['data'].decode('utf-8'))
        log.info(data)
        save_gif(data['trigger_id'], data['text'])
        try:
            slack_client.files_upload(
                channels=data['channel_id'],
                file=f'{data["trigger_id"]}.gif',
                initial_comment=f'보낸 사람: <@{data["user_id"]}>',
                title=data['text'],
            )
        except Exception as e:
            log.error(e)
        with open('data.json', 'a') as f:
            f.write(json.dumps(data, indent=4, sort_keys=True) + '\n')
    else:
        return


# Start listening for messages on the subscribed channels
def start_subscriber():
    redis_subscriber = redis_client.pubsub()
    redis_subscriber.subscribe(**{channel: handle_message})
    redis_subscriber.subscribe(**{"ping": lambda m: log.debug(m)})
    redis_subscriber.run_in_thread(sleep_time=2)


# Define a FastAPI route that publishes JSON data
# to Redis and returns a 200 response
@app.post("/")
async def publish_data(request: Request):
    data = dict(await request.form())
    redis_client.publish(channel, json.dumps(data))
    return {"message": "Data published successfully."}

@app.get("/up")
async def up():
    redis_client.publish("ping", "pong")
    return {"message": "ping"}


# Start the subscriber and the FastAPI app using Uvicorn
if __name__ == "__main__":
    Process(target=start_subscriber).start()
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
