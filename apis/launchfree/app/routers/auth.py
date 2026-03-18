from fastapi import APIRouter, Depends

from app.dependencies import require_session

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def get_current_user(_session: str = Depends(require_session)) -> dict[str, object]:
    return {
        "success": True,
        "data": {"is_authenticated": True, "message": "LaunchFree auth scaffold active"},
    }
