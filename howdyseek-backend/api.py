"""
HOWDY! SEEK API
"""

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from models import User, Course, Settings, NotificationHistory, init_db, get_session

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
    last_seat_count: Optional[int] = None


class CourseCreate(CourseBase):
    pass


class CourseResponse(CourseBase):
    id: int
    last_updated: Optional[datetime] = None

    class Config:
        orm_mode = True


class UserBase(BaseModel):
    name: str
    webhook_url: str
    stop_time: Optional[datetime] = None


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    name: Optional[str] = None
    webhook_url: Optional[str] = None
    stop_time: Optional[datetime] = None


class UserResponse(UserBase):
    id: int
    courses: List[CourseResponse] = []

    class Config:
        orm_mode = True


class NotificationHistoryBase(BaseModel):
    user_id: int
    course_id: int
    seat_count: int
    notification_type: str


class NotificationHistoryCreate(NotificationHistoryBase):
    pass


class NotificationHistoryResponse(NotificationHistoryBase):
    id: int
    notification_time: datetime

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
    db_user = User(
        name=user.name,
        webhook_url=user.webhook_url,
        stop_time=user.stop_time
    )
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

    # Special handling for stop_time to allow setting it to None
    # We need to check if the field was included in the request, not just if it's non-None
    update_data = user.dict(exclude_unset=False)
    if 'stop_time' in update_data:
        db_user.stop_time = user.stop_time

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


@app.get("/courses/", response_model=List[CourseResponse])
def get_courses(db: Session = Depends(get_db)):
    """Get all courses"""
    courses = db.query(Course).all()
    return courses


@app.get("/courses/{course_id}", response_model=CourseResponse)
def get_course(course_id: int, db: Session = Depends(get_db)):
    """Get a specific course by ID"""
    course = db.query(Course).filter(Course.id == course_id).first()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@app.get("/users/{user_id}/courses", response_model=List[CourseResponse])
def get_user_courses(user_id: int, db: Session = Depends(get_db)):
    """Get all courses for a specific user"""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user.courses


@app.post("/users/{user_id}/courses", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
def add_course_to_user(user_id: int, course: CourseCreate, db: Session = Depends(get_db)):
    """Add a course to a user, creating the course if it doesn't exist"""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if course with same CRN already exists for this user
    user_has_course = False
    for user_course in user.courses:
        if user_course.crn == course.crn:
            user_has_course = True
            break

    if user_has_course:
        raise HTTPException(status_code=400, detail="User already has a course with this CRN")

    # Check if the course already exists in the database
    existing_course = db.query(Course).filter(Course.crn == course.crn).first()

    if existing_course:
        # Course exists, just add it to the user
        user.courses.append(existing_course)
        db.commit()
        db.refresh(existing_course)
        return existing_course
    else:
        # Create new course
        db_course = Course(
            course_name=course.course_name,
            professor=course.professor,
            crn=course.crn,
            last_seat_count=course.last_seat_count,
            last_updated=datetime.now()
        )
        db.add(db_course)
        db.flush()  # Flush to get the course ID without committing

        # Add course to user
        user.courses.append(db_course)
        db.commit()
        db.refresh(db_course)
        return db_course


@app.put("/courses/{course_id}", response_model=CourseResponse)
def update_course(course_id: int, course: CourseBase, db: Session = Depends(get_db)):
    """Update a course"""
    db_course = db.query(Course).filter(Course.id == course_id).first()
    if db_course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    # Update course fields
    db_course.course_name = course.course_name
    db_course.professor = course.professor
    db_course.crn = course.crn
    if course.last_seat_count is not None:
        db_course.last_seat_count = course.last_seat_count
        db_course.last_updated = datetime.now()

    db.commit()
    db.refresh(db_course)
    return db_course


@app.delete("/users/{user_id}/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_course_from_user(user_id: int, course_id: int, db: Session = Depends(get_db)):
    """Remove a course from a user's course list"""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    course = db.query(Course).filter(Course.id == course_id).first()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    if course not in user.courses:
        raise HTTPException(status_code=404, detail="Course not found in user's courses")

    user.courses.remove(course)
    db.commit()
    return None


@app.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(course_id: int, db: Session = Depends(get_db)):
    """Delete a course completely, but only if it's not associated with any users"""
    db_course = db.query(Course).filter(Course.id == course_id).first()
    if db_course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    # Check if the course is associated with any users
    if db_course.users:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete course: it is still associated with one or more users"
        )

    db.delete(db_course)
    db.commit()
    return None


# Notification History
@app.post("/notifications/", response_model=NotificationHistoryResponse, status_code=status.HTTP_201_CREATED)
def create_notification(notification: NotificationHistoryCreate, db: Session = Depends(get_db)):
    """Create a new notification history record"""
    # Verify user and course exist
    user = db.query(User).filter(User.id == notification.user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    course = db.query(Course).filter(Course.id == notification.course_id).first()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    # Create notification record
    db_notification = NotificationHistory(
        user_id=notification.user_id,
        course_id=notification.course_id,
        seat_count=notification.seat_count,
        notification_time=datetime.now(),
        notification_type=notification.notification_type
    )
    db.add(db_notification)
    db.commit()
    db.refresh(db_notification)
    return db_notification


@app.get("/users/{user_id}/notifications", response_model=List[NotificationHistoryResponse])
def get_user_notifications(user_id: int, db: Session = Depends(get_db)):
    """Get all notifications for a specific user"""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    notifications = db.query(NotificationHistory).filter(NotificationHistory.user_id == user_id).all()
    return notifications


@app.get("/courses/{course_id}/notifications", response_model=List[NotificationHistoryResponse])
def get_course_notifications(course_id: int, db: Session = Depends(get_db)):
    """Get all notifications for a specific course"""
    course = db.query(Course).filter(Course.id == course_id).first()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    notifications = db.query(NotificationHistory).filter(NotificationHistory.course_id == course_id).all()
    return notifications


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
