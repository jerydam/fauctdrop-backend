from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.models.schemas import AdminLogin
from app.config.settings import ADMIN_USERNAME, ADMIN_PASSWORD
from app.utils.auth import create_access_token, verify_token
from datetime import datetime

router = APIRouter()

security = HTTPBearer()

@router.post("/login")
async def login(credentials: AdminLogin):
    if credentials.username == ADMIN_USERNAME and credentials.password == ADMIN_PASSWORD:
        access_token = create_access_token(data={"sub": credentials.username})
        return {"access_token": access_token, "token_type": "bearer"}
    raise HTTPException(status_code=401, detail="Invalid credentials")