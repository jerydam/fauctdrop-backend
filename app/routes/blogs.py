from fastapi import APIRouter, HTTPException, status, Depends
from app.models.schemas import BlogCreate, BlogFromUrl, BlogUpdate
from app.config.settings import supabase, supabase_admin
from app.utils.auth import get_admin_user
from app.utils.web_scraper import extract_article_content
from datetime import datetime
import uuid

router = APIRouter()

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_blog(blog: BlogCreate, admin: str = Depends(get_admin_user)):
    blog_data = {
        "id": str(uuid.uuid4()),
        "title": blog.title,
        "excerpt": blog.excerpt,
        "content": blog.content,
        "author": blog.author,
        "author_bio": blog.author_bio,
        "author_avatar": blog.author_avatar,
        "category": blog.category,
        "tags": blog.tags,
        "image": blog.image,
        "featured": blog.featured,
        "likes": 0,
        "read_time": f"{max(1, len(blog.content.split()) // 200)} min read",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
    
    try:
        result = supabase_admin.table("blogs").insert(blog_data).execute()
        return result.data[0]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/from-url", status_code=status.HTTP_201_CREATED)
async def create_blog_from_url(blog_data: BlogFromUrl, admin: str = Depends(get_admin_user)):
    extracted = extract_article_content(str(blog_data.url))
    
    blog_record = {
        "id": str(uuid.uuid4()),
        "title": extracted["title"],
        "excerpt": extracted["excerpt"],
        "content": extracted["content"],
        "author": blog_data.author,
        "author_bio": blog_data.author_bio,
        "author_avatar": blog_data.author_avatar,
        "category": blog_data.category,
        "tags": blog_data.tags,
        "image": extracted["image"],
        "featured": blog_data.featured,
        "likes": 0,
        "read_time": f"{max(1, len(extracted['content'].split()) // 200)} min read",
        "source_url": str(blog_data.url),
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
    
    try:
        result = supabase_admin.table("blogs").insert(blog_record).execute()
        return result.data[0]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/")
async def get_blogs(category: str | None = None, featured: bool | None = None, limit: int | None = None, search: str | None = None):
    try:
        query = supabase.table("blogs").select("*")
        
        if category:
            query = query.eq("category", category)
        if featured is not None:
            query = query.eq("featured", featured)
        if search:
            query = query.or_(f"title.ilike.%{search}%,excerpt.ilike.%{search}%")
        
        query = query.order("created_at", desc=True)
        
        if limit:
            query = query.limit(limit)
        
        result = query.execute()
        return result.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{blog_id}")
async def get_blog(blog_id: str):
    try:
        result = supabase.table("blogs").select("*").eq("id", blog_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Blog not found")
        return result.data[0]
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{blog_id}")
async def update_blog(blog_id: str, blog: BlogUpdate, admin: str = Depends(get_admin_user)):
    update_data = {k: v for k, v in blog.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow().isoformat()
    
    try:
        result = supabase_admin.table("blogs").update(update_data).eq("id", blog_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Blog not found")
        return result.data[0]
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{blog_id}")
async def delete_blog(blog_id: str, admin: str = Depends(get_admin_user)):
    try:
        result = supabase_admin.table("blogs").delete().eq("id", blog_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Blog not found")
        return {"message": "Blog deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{blog_id}/like")
async def like_blog(blog_id: str):
    try:
        result = supabase.table("blogs").select("likes").eq("id", blog_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Blog not found")
        
        current_likes = result.data[0]["likes"]
        new_likes = current_likes + 1
        
        update_result = supabase.table("blogs").update({"likes": new_likes}).eq("id", blog_id).execute()
        return {"likes": new_likes}
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail=str(e))