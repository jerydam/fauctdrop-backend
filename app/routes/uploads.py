from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from app.utils.auth import get_admin_user
import uuid
import aiofiles
import os

router = APIRouter()

# Create upload directories
os.makedirs("uploads/events", exist_ok=True)
os.makedirs("uploads/blogs", exist_ok=True)
os.makedirs("uploads/avatars", exist_ok=True)

@router.post("/{category}")
async def upload_file(category: str, file: UploadFile = File(...), admin: str = Depends(get_admin_user)):
    if category not in ["events", "blogs", "avatars"]:
        raise HTTPException(status_code=400, detail="Invalid upload category")
    
    allowed_types = ["image/jpeg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type. Only JPEG, PNG, and WebP are allowed.")
    
    file_extension = file.filename.split('.')[-1]
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = f"uploads/{category}/{unique_filename}"
    
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    
    file_url = f"/static/{category}/{unique_filename}"
    
    return {"url": file_url, "filename": unique_filename}