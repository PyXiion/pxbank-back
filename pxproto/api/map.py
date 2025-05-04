import asyncio
import base64
import os
import time
from pathlib import Path

import aiofiles
import aiohttp

from pxws.connection_ctx import ConnectionContext
from pxws.route import Route

route = Route()

STORAGE_DIR = Path(os.getenv("STORAGE_PATH", "./storage"))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
TTL_SECONDS = 60 * 60  # 1 час

write_locks = {}


async def fetch_chunk_from_source(x: int, y: int) -> bytes:
  url = f"https://map.pivoland.ru/tiles/minecraft_overworld/3/{x}_{y}.png"
  async with aiohttp.ClientSession() as session:
    async with session.get(url) as resp:
      resp.raise_for_status()
      return await resp.read()


def is_expired(path: Path) -> bool:
  try:
    mtime = path.stat().st_mtime
    return (time.time() - mtime) > TTL_SECONDS
  except FileNotFoundError:
    return True


def get_write_lock(path: Path) -> asyncio.Lock:
    return write_locks.setdefault(str(path), asyncio.Lock())


@route.on("map/chunk", require_auth=False)
async def map_chunk(ctx: ConnectionContext, x: int, y: int):
  chunk_path = STORAGE_DIR / f"chunk_{x}_{y}.png"

  if not chunk_path.exists() or is_expired(chunk_path):
    lock = get_write_lock(chunk_path)
    async with lock:
      if chunk_path.exists() and not is_expired(chunk_path):
        async with aiofiles.open(chunk_path, "rb") as f:
          return await f.read()

      data = await fetch_chunk_from_source(x, y)
      async with aiofiles.open(chunk_path, "wb") as f:
        await f.write(data)
  else:
    async with aiofiles.open(chunk_path, "rb") as f:
      data = await f.read()

  ctx.set_metadata('ttl', TTL_SECONDS / 2)
  return base64.b64encode(data).decode('ascii')
