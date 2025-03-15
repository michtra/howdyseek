"""
HOWDY! SEEK API
"""

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session

from models import User, Course, Settings, init_db, get_session

# Initialize database
engine = init_db()

# Initialize FastAPI app
app = FastAPI(title="HowdySeek API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency to get database session
def get_db():
    db = get_session(engine)
    try:
        yield db
    finally:
        db.close()


# Pydantic models for request validation
class CourseBase(BaseModel):
    course_name: str
    professor: str
    crn: str


class CourseCreate(CourseBase):
    pass


class CourseResponse(CourseBase):
    id: int

    class Config:
        orm_mode = True


class UserBase(BaseModel):
    name: str
    webhook_url: str


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    name: Optional[str] = None
    webhook_url: Optional[str] = None


class UserResponse(UserBase):
    id: int
    courses: List[CourseResponse] = []

    class Config:
        orm_mode = True


# API Routes
@app.get("/users/", response_model=List[UserResponse])
def get_users(db: Session = Depends(get_db)):
    """Get all users with their courses"""
    users = db.query(User).all()
    return users


@app.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get a specific user by ID"""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.post("/users/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create a new user"""
    # Check if webhook URL already exists
    existing_user = db.query(User).filter(User.webhook_url == user.webhook_url).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Webhook URL already registered")

    # Create new user
    db_user = User(name=user.name, webhook_url=user.webhook_url)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.put("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: int, user: UserUpdate, db: Session = Depends(get_db)):
    """Update a user"""
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Update user fields if provided
    if user.name is not None:
        db_user.name = user.name
    if user.webhook_url is not None:
        db_user.webhook_url = user.webhook_url

    db.commit()
    db.refresh(db_user)
    return db_user


@app.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Delete a user"""
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(db_user)
    db.commit()
    return None


@app.get("/users/{user_id}/courses", response_model=List[CourseResponse])
def get_user_courses(user_id: int, db: Session = Depends(get_db)):
    """Get all courses for a specific user"""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user.courses


@app.post("/users/{user_id}/courses", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
def create_course(user_id: int, course: CourseCreate, db: Session = Depends(get_db)):
    """Add a course to a user"""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if course with same CRN already exists for this user
    existing_course = db.query(Course).filter(
        Course.user_id == user_id,
        Course.crn == course.crn
    ).first()

    if existing_course:
        raise HTTPException(status_code=400, detail="Course with this CRN already exists for this user")

    # Create new course
    db_course = Course(
        course_name=course.course_name,
        professor=course.professor,
        crn=course.crn,
        user_id=user_id
    )

    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return db_course


@app.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(course_id: int, db: Session = Depends(get_db)):
    """Delete a course"""
    db_course = db.query(Course).filter(Course.id == course_id).first()
    if db_course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    db.delete(db_course)
    db.commit()
    return None


# Settings models and endpoints
class SettingsResponse(BaseModel):
    id: int
    min_refresh_interval: float
    max_refresh_interval: float

    class Config:
        orm_mode = True


class SettingsUpdate(BaseModel):
    min_refresh_interval: Optional[float] = None
    max_refresh_interval: Optional[float] = None


@app.get("/settings/", response_model=SettingsResponse)
def get_settings(db: Session = Depends(get_db)):
    """Get application settings"""
    settings = db.query(Settings).first()
    if not settings:
        # This shouldn't happen as init_db creates default settings
        raise HTTPException(status_code=404, detail="Settings not found")
    return settings


@app.put("/settings/", response_model=SettingsResponse)
def update_settings(settings_update: SettingsUpdate, db: Session = Depends(get_db)):
    """Update application settings"""
    db_settings = db.query(Settings).first()
    if not db_settings:
        raise HTTPException(status_code=404, detail="Settings not found")

    # Validate refresh intervals
    min_interval = settings_update.min_refresh_interval
    max_interval = settings_update.max_refresh_interval

    if min_interval is not None and max_interval is not None:
        if min_interval > max_interval:
            raise HTTPException(
                status_code=400,
                detail="Minimum refresh interval cannot be greater than maximum"
            )
    elif min_interval is not None and min_interval > db_settings.max_refresh_interval:
        raise HTTPException(
            status_code=400,
            detail="Minimum refresh interval cannot be greater than maximum"
        )
    elif max_interval is not None and max_interval < db_settings.min_refresh_interval:
        raise HTTPException(
            status_code=400,
            detail="Maximum refresh interval cannot be less than minimum"
        )

    # Update fields if provided
    if min_interval is not None:
        db_settings.min_refresh_interval = min_interval
    if max_interval is not None:
        db_settings.max_refresh_interval = max_interval

    db.commit()
    db.refresh(db_settings)
    return db_settings


# Health check endpoint
@app.get("/health")
def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
