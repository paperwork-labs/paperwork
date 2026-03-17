from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    db_connected: bool
    version: str
