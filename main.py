from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from db.getdb import engine, Base
from routes import chat, auth

# Create FastAPI app
app = FastAPI(title="Chatbot API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
@app.on_event("startup")
async def startup():
    # Create database tables
    Base.metadata.create_all(bind=engine)

# Include routers
app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])

@app.get("/")
async def root():
    return {"message": "Welcome to Chatbot API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)