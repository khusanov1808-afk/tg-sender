"""
TG Kino Panel: userbot yuboruvchi (sizning akkauntingiz nomidan).
GitHub Actions'da ishlaydi. Vazifalarni Apps Script API orqali oladi.
"""
import asyncio
import os
import random
import time

import requests
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.sessions import StringSession

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SESSION = os.environ["TG_SESSION"]
GAS_URL = os.environ["GAS_URL"]  # .../exec?s=MAXFIY_KALIT

DELAY = float(os.environ.get("DELAY_SEC", "4"))              # xabarlar orasidagi kutish
MAX_RUN = int(os.environ.get("MAX_RUN_SEC", str(5 * 3600 + 30 * 60)))  # bitta ishga tushish limiti
STARTED = time.time()


def gas(**params):
    last = None
    for _ in range(6):
        try:
            r = requests.get(GAS_URL, params=params, timeout=60)
            data = r.json()
            if "error" in data:
                raise RuntimeError(data["error"])
            return data
        except Exception as e:  # tarmoq yoki Apps Script vaqtincha xatosi
            last = e
            time.sleep(5)
    raise RuntimeError(f"Apps Script bilan aloqa yo'q: {last}")


def make_text(fmt, n, kino):
    if fmt != "/start":
        return str(n)
    kino = (kino or "").lstrip("@")
    return f"/start@{kino} {n}" if kino else f"/start {n}"


def time_left():
    return MAX_RUN - (time.time() - STARTED)


async def run_task(client, t):
    task_id = t["id"]
    end = int(t["end"])
    n = int(t["next"])
    fmt = t["fmt"]
    kino = t.get("kino", "")

    await client.get_dialogs()  # guruhni akkaunt keshiga yuklash
    entity = await client.get_entity(int(t["chat"]))
    print(f"[{t['title']}] {n} -> {end}", flush=True)

    sent = 0
    while n <= end and time_left() > 60:
        text = make_text(fmt, n, kino)
        try:
            await client.send_message(entity, text)
        except FloodWaitError as e:
            wait = e.seconds + 5
            print(f"FloodWait {wait}s", flush=True)
            if wait > time_left() - 60:
                gas(a="progress", id=task_id, next=n)
                return "wait"
            await asyncio.sleep(wait)
            continue
        except Exception as e:
            gas(a="fail", id=task_id, next=n, msg=f"{type(e).__name__}: {e}")
            return "error"

        n += 1
        sent += 1

        if sent % 10 == 0:
            status = gas(a="progress", id=task_id, next=n).get("status")
            if status != "Running":  # pauza yoki to'xtatilgan
                print(f"Status: {status}, to'xtadim (keyingi: {n})", flush=True)
                return "stopped"

        await asyncio.sleep(DELAY + random.uniform(0, 1.5))

    if n > end:
        gas(a="finish", id=task_id)
        print("Tugadi", flush=True)
        return "done"

    gas(a="progress", id=task_id, next=n)  # vaqt tugadi, keyingi ishga tushishda davom etadi
    return "time"


async def main():
    first = gas(a="next").get("task")
    if not first:
        print("Faol vazifa yo'q.")
        return

    client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            gas(a="fail", id=first["id"], next=first["next"], msg="Userbot sessiyasi eskirgan, qayta yarating")
            return
        while time_left() > 120:
            t = gas(a="next").get("task")
            if not t:
                break
            result = await run_task(client, t)
            if result in ("time", "wait", "stopped", "error"):
                if result in ("time", "wait"):
                    break
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
