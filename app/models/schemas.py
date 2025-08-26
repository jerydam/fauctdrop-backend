from pydantic import BaseModel, HttpUrl, EmailStr
from typing import Optional, List

class AdminLogin(BaseModel):
    username: str
    password: str

class EventCreate(BaseModel):
    title: str
    description: str
    full_description: Optional[str] = None
    date: str
    time: str
    location: str
    type: str
    max_attendees: int
    speaker_name: str
    speaker_title: str
    speaker_bio: str
    speaker_avatar: Optional[str] = None
    image: Optional[str] = None
    agenda: Optional[List[dict]] = None

class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    full_description: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    location: Optional[str] = None
    type: Optional[str] = None
    max_attendees: Optional[int] = None
    speaker_name: Optional[str] = None
    speaker_title: Optional[str] = None
    speaker_bio: Optional[str] = None
    speaker_avatar: Optional[str] = None
    image: Optional[str] = None
    agenda: Optional[List[dict]] = None
    status: Optional[str] = None

class BlogCreate(BaseModel):
    title: str
    excerpt: str
    content: str
    author: str
    author_bio: str
    author_avatar: Optional[str] = None
    category: str
    tags: List[str]
    image: Optional[str] = None
    featured: bool = False

class BlogFromUrl(BaseModel):
    url: HttpUrl
    author: str
    author_bio: str
    author_avatar: Optional[str] = None
    category: str
    tags: List[str]
    featured: bool = False

class BlogUpdate(BaseModel):
    title: Optional[str] = None
    excerpt: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None
    author_bio: Optional[str] = None
    author_avatar: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    image: Optional[str] = None
    featured: Optional[bool] = None

class MemberCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    student_id: str
    department: str
    level: str
    phone: Optional[str] = None
    interests: List[str]
    experience: str
    goals: Optional[str] = None
    newsletter: bool
    terms: bool
    role: Optional[str] = None
    avatar: Optional[str] = None
    projects: Optional[int] = 0
    events_attended: Optional[int] = 0
    achievements: Optional[List[str]] = None
    featured: Optional[bool] = False

class MemberUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    student_id: Optional[str] = None
    department: Optional[str] = None
    level: Optional[str] = None
    phone: Optional[str] = None
    interests: Optional[List[str]] = None
    experience: Optional[str] = None
    goals: Optional[str] = None
    newsletter: Optional[bool] = None
    role: Optional[str] = None
    avatar: Optional[str] = None
    projects: Optional[int] = None
    events_attended: Optional[int] = None
    achievements: Optional[List[str]] = None
    featured: Optional[bool] = None

class EventRegistrationCreate(BaseModel):
    event_id: str
    member_id: str