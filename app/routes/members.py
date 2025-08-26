from fastapi import APIRouter, HTTPException, status, Depends
from app.models.schemas import MemberCreate, MemberUpdate, EventRegistrationCreate
from app.config.settings import supabase, supabase_admin
from app.utils.auth import verify_token
from datetime import datetime
import uuid

router = APIRouter()

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_member(member: MemberCreate):
    if not member.terms:
        raise HTTPException(status_code=400, detail="You must agree to the terms and conditions")

    member_data = {
        "id": str(uuid.uuid4()),
        "first_name": member.first_name,
        "last_name": member.last_name,
        "email": member.email,
        "student_id": member.student_id,
        "department": member.department,
        "level": member.level,
        "phone": member.phone,
        "interests": member.interests,
        "experience": member.experience,
        "goals": member.goals,
        "newsletter": member.newsletter,
        "terms": member.terms,
        "role": member.role,
        "avatar": member.avatar,
        "projects": member.projects or 0,
        "events_attended": member.events_attended or 0,
        "achievements": member.achievements or [],
        "featured": member.featured or False,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }

    try:
        result = supabase.table("members").insert(member_data).execute()
        return result.data[0]
    except Exception as e:
        if "unique constraint" in str(e).lower():
            raise HTTPException(status_code=400, detail="Email or Student ID already registered")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=list)
async def get_members():
    try:
        result = supabase.table("members").select("id, email, student_id").execute()
        return result.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/featured", response_model=list)
async def get_featured_members():
    try:
        result = supabase.table("members").select("*").eq("featured", True).execute()
        return result.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{member_id}", response_model=dict)
async def update_member(member_id: str, member: MemberUpdate, _: dict = Depends(verify_token)):
    update_data = {k: v for k, v in member.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow().isoformat()

    try:
        result = supabase_admin.table("members").update(update_data).eq("id", member_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Member not found")
        return result.data[0]
    except Exception as e:
        if "unique constraint" in str(e).lower():
            raise HTTPException(status_code=400, detail="Email or Student ID already registered")
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_member(member_id: str, _: dict = Depends(verify_token)):
    try:
        result = supabase_admin.table("members").delete().eq("id", member_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Member not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_for_event(registration: EventRegistrationCreate):
    registration_data = {
        "id": str(uuid.uuid4()),
        "event_id": registration.event_id,
        "member_id": registration.member_id,
        "registered_at": datetime.utcnow().isoformat()
    }

    try:
        # Check if event exists and is not full
        event = supabase.table("events").select("attendees, max_attendees").eq("id", registration.event_id).execute()
        if not event.data:
            raise HTTPException(status_code=404, detail="Event not found")
        if event.data[0]["attendees"] >= event.data[0]["max_attendees"]:
            raise HTTPException(status_code=400, detail="Event is full")

        # Check if member exists
        member = supabase.table("members").select("id, events_attended").eq("id", registration.member_id).execute()
        if not member.data:
            raise HTTPException(status_code=404, detail="Member not found")

        # Register and increment attendees
        result = supabase.table("event_registrations").insert(registration_data).execute()
        supabase.table("events").update({"attendees": event.data[0]["attendees"] + 1}).eq("id", registration.event_id).execute()
        supabase.table("members").update({"events_attended": member.data[0]["events_attended"] + 1}).eq("id", registration.member_id).execute()
        return result.data[0]
    except Exception as e:
        if "unique constraint" in str(e).lower():
            raise HTTPException(status_code=400, detail="Member already registered for this event")
        raise HTTPException(status_code=400, detail=str(e))