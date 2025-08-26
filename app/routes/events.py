from fastapi import APIRouter, HTTPException, status, Depends
from app.models.schemas import EventCreate, EventUpdate
from app.config.settings import supabase_admin
from app.utils.auth import verify_token, get_admin_user
from datetime import datetime
import uuid

router = APIRouter()

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_event(event: EventCreate, admin: str = Depends(get_admin_user)):
    event_data = {
        "id": str(uuid.uuid4()),
        "title": event.title,
        "description": event.description,
        "full_description": event.full_description,
        "date": event.date,
        "time": event.time,
        "location": event.location,
        "type": event.type,
        "status": "upcoming",
        "attendees": 0,
        "max_attendees": event.max_attendees,
        "speaker_name": event.speaker_name,
        "speaker_title": event.speaker_title,
        "speaker_bio": event.speaker_bio,
        "speaker_avatar": event.speaker_avatar,
        "image": event.image,
        "agenda": event.agenda,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
    
    try:
        result = supabase_admin.table("events").insert(event_data).execute()
        return result.data[0]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/")
async def get_events(status: str | None = None, type: str | None = None, limit: int | None = None):
    try:
        query = supabase_admin.table("events").select("*")
        
        if status:
            query = query.eq("status", status)
        if type:
            query = query.eq("type", type)
        
        query = query.order("date", desc=False)
        
        if limit:
            query = query.limit(limit)
        
        result = query.execute()
        return result.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{event_id}")
async def get_event(event_id: str):
    try:
        result = supabase_admin.table("events").select("*").eq("id", event_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Event not found")
        return result.data[0]
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{event_id}")
async def update_event(event_id: str, event: EventUpdate, admin: str = Depends(get_admin_user)):
    update_data = {k: v for k, v in event.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow().isoformat()
    
    try:
        result = supabase_admin.table("events").update(update_data).eq("id", event_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Event not found")
        return result.data[0]
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{event_id}")
async def delete_event(event_id: str, admin: str = Depends(get_admin_user)):
    try:
        result = supabase_admin.table("events").delete().eq("id", event_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Event not found")
        return {"message": "Event deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))