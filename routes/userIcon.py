import os

import dotenv
import orjson
from cryptography.fernet import Fernet
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from httpx import AsyncClient
from otoge import MaiMaiAime, MaiMaiClient, POPNClient
from typing import Literal

from services.database import Database

router = APIRouter()

dotenv.load_dotenv()

cipherSuite = Fernet(os.getenv("fernet_key").encode())


@router.get("/icon/{userId:int}/{game:str}")
async def fetchUserIcon(userId: int, game: Literal["maimai", "popn"]):
    """ユーザーのアイコンを取得します。
    なお、アイコンはキャッシュしておくことを推奨します。
    """
    match game:
        case "maimai":
            row = await Database.pool.fetchrow(
                "SELECT * FROM aime WHERE id = $1", userId
            )
            if not row:
                raise HTTPException(404)
            client = MaiMaiClient()
            aimeList = await client.login(
                cipherSuite.decrypt(row["segaid"].encode()).decode(),
                cipherSuite.decrypt(row["password"].encode()).decode(),
            )
            aime: MaiMaiAime = aimeList[row["aime"]]
            await aime.select()

            http = AsyncClient(cookies=client.http.cookies, verify=False)
            response = await http.get(aime.iconUrl)
            return StreamingResponse(response.aiter_bytes(), media_type="image/png")
        case "popn":
            row = await Database.pool.fetchrow(
                "SELECT * FROM konami WHERE id = $1", userId
            )
            if not row:
                raise HTTPException(404)
            client = POPNClient(skipKonami=True)
            await client.loginWithCookie(
                orjson.loads(cipherSuite.decrypt(row["cookies"].encode()).decode())
            )
            profile = await client.fetchProfile()

            http = AsyncClient(cookies=client.http.cookies, verify=False)
            response = await http.get(profile.bannerUrl)
            return StreamingResponse(response.aiter_bytes(), media_type="image/png")
        case _:
            raise HTTPException(404)
