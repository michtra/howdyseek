from sqlalchemy import Column, Integer, String, ForeignKey, create_engine, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()


class Settings(Base):
    __tablename__ = 'settings'

    id = Column(Integer, primary_key=True)
    min_refresh_interval = Column(Float, default=30.0)
    max_refresh_interval = Column(Float, default=40.0)

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

    # Relationship to courses
    courses = relationship("Course", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "webhook_url": self.webhook_url,
            "courses": [course.to_dict() for course in self.courses]
        }


class Course(Base):
    __tablename__ = 'courses'

    id = Column(Integer, primary_key=True)
    course_name = Column(String(100), nullable=False)
    professor = Column(String(100), nullable=False)
    crn = Column(String(20), nullable=False)

    # Foreign key to User
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    # Relationship to User
    user = relationship("User", back_populates="courses")

    def to_dict(self):
        return {
            "id": self.id,
            "course_name": self.course_name,
            "professor": self.professor,
            "crn": self.crn
        }


def init_db(db_url="sqlite:///howdyseek.db"):
    """Initialize the database with tables"""
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)

    # Create default settings if they don't exist
    Session = sessionmaker(bind=engine)
    session = Session()

    if not session.query(Settings).first():
        default_settings = Settings(min_refresh_interval=30.0, max_refresh_interval=40.0)
        session.add(default_settings)
        session.commit()

    session.close()
    return engine


def get_session(engine):
    """Create a session factory bound to the engine"""
    Session = sessionmaker(bind=engine)
    return Session()
