import os

import dotenv
import orjson
from cryptography.fernet import Fernet
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from httpx import AsyncClient
from otoge import MaiMaiClient, POPNClient
from otoge.maimai import MaiMaiAime

from services.database import Database

dotenv.load_dotenv()

cipherSuite = Fernet(os.getenv("fernet_key").encode())
router = APIRouter()


@router.get("/api/iconproxy/maimai")
async def maimaiIconProxy(userId: int):
    row = await Database.pool.fetchrow("SELECT * FROM aime WHERE id = $1", userId)
    if not row:
        raise HTTPException(404)
    client = MaiMaiClient()
    try:
        aimeList = await client.login(
            cipherSuite.decrypt(row["segaid"].encode()).decode(),
            cipherSuite.decrypt(row["password"].encode()).decode(),
        )
        aime: MaiMaiAime = aimeList[row["aime"]]
    except Exception as e:
        raise e

    async with AsyncClient(verify=False) as client:
        response = await client.get(aime.iconUrl)
    return StreamingResponse(response.aiter_bytes(), media_type="image/png")


@router.get("/api/iconproxy/popn")
async def popnIconProxy(userId: int):
    row = await Database.pool.fetchrow("SELECT * FROM konami WHERE id = $1", userId)
    if not row:
        raise HTTPException(404)
    client = POPNClient(skipKonami=True)
    try:
        await client.loginWithCookie(
            orjson.loads(cipherSuite.decrypt(row["cookies"].encode()).decode())
        )
        profile = await client.fetchProfile()
    except Exception as e:
        raise e

    async with AsyncClient(cookies=client.http.cookies, verify=False) as client:
        response = await client.get(profile.bannerUrl)
    return StreamingResponse(response.aiter_bytes(), media_type="image/png")
