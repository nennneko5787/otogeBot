from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from httpx import AsyncClient

router = APIRouter()


@router.get("/imageProxy")
async def imageProxy(url: str):
    """単に画像をプロキシします。"""
    http = AsyncClient(verify=False)
    response = await http.get(url)
    return StreamingResponse(response.aiter_bytes(), media_type="image/png")
