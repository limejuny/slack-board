import json
import logging
import os

import uvicorn
from fastapi import BackgroundTasks, FastAPI, Request
from PIL import Image, ImageDraw, ImageFont
from slack import WebClient

app = FastAPI()

log = logging.getLogger()
log.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
handler.setFormatter(formatter)
filehandler = logging.FileHandler('debug.log')
filehandler.setLevel(logging.DEBUG)
filehandler.setFormatter(formatter)

log.addHandler(handler)
log.addHandler(filehandler)

logging.getLogger("uvicorn.access").addFilter(
    lambda record: ((record.args is not None) and (len(record.args) > 2) and
                    (record.args[2] != '/up')))

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
    for _ in range((font.font.getsize(text)[0][0] + start_x) // diff - 1):
        new_frame = create_image_with_text((x + start_x, y), text * 10)
        frames.append(new_frame)
        x -= diff
    frames[0].save(f'{file_id}.gif',
                   format="GIF",
                   append_images=frames[1:],
                   save_all=True,
                   duration=10,
                   loop=0)


def save_and_send(data):
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
        f.write(
            json.dumps(data, indent=4, sort_keys=True, ensure_ascii=False) +
            '\n')


@app.post("/")
async def publish_data(request: Request, background_tasks: BackgroundTasks):
    data = dict(await request.form())
    background_tasks.add_task(save_and_send, data)
    return {"message": "Data published successfully."}


@app.get("/up")
async def up():
    return {"message": "ping"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
