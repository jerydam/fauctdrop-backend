from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth, events, blogs, uploads, members

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Adjust for your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routes
app.include_router(auth.router, prefix="/auth")
app.include_router(events.router, prefix="/events")
app.include_router(blogs.router, prefix="/blogs")
app.include_router(uploads.router, prefix="/uploads")
app.include_router(members.router, prefix="/members")

@app.get("/")
async def root():
    return {"message": "Welcome to the Blockchain Club API"}