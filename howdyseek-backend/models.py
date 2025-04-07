from sqlalchemy import Column, Integer, String, ForeignKey, create_engine, Float, DateTime, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime

Base = declarative_base()

# Junction table for many-to-many relationship between users and courses
user_courses = Table(
    'user_courses',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('course_id', Integer, ForeignKey('courses.id'), primary_key=True)
)


class Settings(Base):
    __tablename__ = 'settings'

    id = Column(Integer, primary_key=True)
    min_refresh_interval = Column(Float, default=20.0)
    max_refresh_interval = Column(Float, default=30.0)

    def to_dict(self):
        return {
            "id": self.id,
            "min_refresh_interval": self.min_refresh_interval,
            "max_refresh_interval": self.max_refresh_interval
        }


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    webhook_url = Column(String(255), unique=True, nullable=False)
    stop_time = Column(DateTime, nullable=True)  # Time when user tracking should stop

    # Many-to-many relationship to courses
    courses = relationship("Course", secondary=user_courses, back_populates="users")

    # One-to-many relationship to notification history
    notifications = relationship("NotificationHistory", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "webhook_url": self.webhook_url,
            "stop_time": self.stop_time.isoformat() if self.stop_time else None,
            "courses": [course.to_dict() for course in self.courses]
        }


class Course(Base):
    __tablename__ = 'courses'

    id = Column(Integer, primary_key=True)
    course_name = Column(String(100), nullable=False)
    professor = Column(String(100), nullable=False)
    crn = Column(String(20), nullable=False, unique=True)
    last_seat_count = Column(Integer, nullable=True)  # For tracking seat numbers
    last_updated = Column(DateTime, nullable=True, default=datetime.now)  # When seat count was last updated

    # Many-to-many relationship to users
    users = relationship("User", secondary=user_courses, back_populates="courses")

    # One-to-many relationship to notification history
    notifications = relationship("NotificationHistory", back_populates="course", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "course_name": self.course_name,
            "professor": self.professor,
            "crn": self.crn,
            "last_seat_count": self.last_seat_count,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None
        }


class NotificationHistory(Base):
    __tablename__ = 'notification_history'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    seat_count = Column(Integer, nullable=False)
    notification_time = Column(DateTime, nullable=False, default=datetime.now)
    notification_type = Column(String(20), nullable=False)  # 'initial', 'change', or 'full'

    # Relationships
    user = relationship("User", back_populates="notifications")
    course = relationship("Course", back_populates="notifications")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "course_id": self.course_id,
            "seat_count": self.seat_count,
            "notification_time": self.notification_time.isoformat() if self.notification_time else None,
            "notification_type": self.notification_type
        }


def init_db(db_url="sqlite:///howdyseek.db"):
    """Initialize the database with tables"""
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)

    # Create default settings if they don't exist
    Session = sessionmaker(bind=engine)
    session = Session()

    if not session.query(Settings).first():
        default_settings = Settings(min_refresh_interval=20.0, max_refresh_interval=30.0)
        session.add(default_settings)
        session.commit()

    session.close()
    return engine


def get_session(engine):
    """Create a session factory bound to the engine"""
    Session = sessionmaker(bind=engine)
    return Session()
