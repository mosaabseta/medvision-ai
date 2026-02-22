"""
Database models for GI Copilot
Using SQLAlchemy ORM with SQLite compatibility
"""

from sqlalchemy import (
    Column, String, Integer, BigInteger, Boolean, Text, 
    TIMESTAMP, ForeignKey, CheckConstraint, UniqueConstraint, Numeric
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(String(50), default="physician")
    institution = Column(String(255))
    is_active = Column(Boolean, default=True)
    
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())
    last_login = Column(TIMESTAMP)
    
    # Relationships
    video_sessions = relationship("VideoSession", back_populates="user")
    conversations = relationship("Conversation", back_populates="user")


class VideoSession(Base):
    __tablename__ = "video_sessions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Metadata
    title = Column(String(500))
    description = Column(Text)
    procedure_type = Column(String(100), index=True)
    session_type = Column(String(50), nullable=False)  # live or recorded
    
    # Video details
    original_video_path = Column(String(1000))
    video_duration_seconds = Column(Numeric(10, 2))
    video_size_bytes = Column(BigInteger)
    frame_count = Column(Integer)
    fps = Column(Numeric(5, 2))
    
    # Processing
    processing_status = Column(String(50), default="pending", index=True)
    processing_progress = Column(Integer, default=0)
    processing_started_at = Column(TIMESTAMP)
    processing_completed_at = Column(TIMESTAMP)
    
    # Export
    export_bundle_path = Column(String(1000))
    export_generated_at = Column(TIMESTAMP)
    
    created_at = Column(TIMESTAMP, default=func.now(), index=True)
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        CheckConstraint(
            "session_type IN ('live', 'recorded')",
            name="valid_session_type"
        ),
    )
    
    # Relationships
    user = relationship("User", back_populates="video_sessions")
    frames = relationship("VideoFrame", back_populates="session", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="session", cascade="all, delete-orphan")
    summary = relationship("SessionSummary", back_populates="session", uselist=False)


class VideoFrame(Base):
    __tablename__ = "video_frames"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("video_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    frame_index = Column(Integer, nullable=False)
    timestamp_ms = Column(BigInteger, nullable=False)
    timestamp_formatted = Column(String(20))
    
    frame_image_path = Column(String(1000))
    is_keyframe = Column(Boolean, default=False)
    
    analyzed = Column(Boolean, default=False, index=True)
    created_at = Column(TIMESTAMP, default=func.now())
    
    __table_args__ = (
        UniqueConstraint("session_id", "frame_index", name="unique_session_frame"),
    )
    
    # Relationships
    session = relationship("VideoSession", back_populates="frames")
    analysis = relationship("FrameAnalysis", back_populates="frame", uselist=False)


class FrameAnalysis(Base):
    __tablename__ = "frame_analysis"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    frame_id = Column(String(36), ForeignKey("video_frames.id", ondelete="CASCADE"), nullable=False, unique=True)
    session_id = Column(String(36), ForeignKey("video_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    model_name = Column(String(100), nullable=False)
    inference_time_ms = Column(Integer)
    
    # Analysis results
    finding = Column(Text)
    anatomical_location = Column(String(200))
    risk_level = Column(String(50), index=True)
    confidence_score = Column(Numeric(5, 4))
    
    detected_features = Column(Text)  # JSON stored as text for SQLite
    suggested_action = Column(Text)
    raw_output = Column(Text)
    
    created_at = Column(TIMESTAMP, default=func.now(), index=True)
    
    # Relationships
    frame = relationship("VideoFrame", back_populates="analysis")


class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("video_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    started_at = Column(TIMESTAMP, default=func.now())
    ended_at = Column(TIMESTAMP)
    message_count = Column(Integer, default=0)
    
    # Relationships
    user = relationship("User", back_populates="conversations")
    session = relationship("VideoSession", back_populates="conversations")
    messages = relationship("ConversationMessage", back_populates="conversation", cascade="all, delete-orphan")


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("video_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    role = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    
    frame_id = Column(String(36), ForeignKey("video_frames.id", ondelete="SET NULL"))
    timestamp_ms = Column(BigInteger)
    
    model_name = Column(String(100))
    tokens_used = Column(Integer)
    
    created_at = Column(TIMESTAMP, default=func.now(), index=True)
    
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant', 'system')",
            name="valid_role"
        ),
    )
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")


class SessionSummary(Base):
    __tablename__ = "session_summaries"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("video_sessions.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    overall_summary = Column(Text, nullable=False)
    key_findings = Column(Text)  # JSON array stored as text for SQLite
    
    total_frames_analyzed = Column(Integer)
    high_risk_findings_count = Column(Integer)
    
    generated_at = Column(TIMESTAMP, default=func.now())
    
    # Relationships
    session = relationship("VideoSession", back_populates="summary")


class ProcessingTask(Base):
    __tablename__ = "processing_tasks"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    celery_task_id = Column(String(255), unique=True, nullable=False)
    session_id = Column(String(36), ForeignKey("video_sessions.id", ondelete="CASCADE"), index=True)
    
    task_type = Column(String(100), nullable=False)
    task_status = Column(String(50), default="pending", index=True)
    
    progress_current = Column(Integer, default=0)
    progress_total = Column(Integer)
    
    started_at = Column(TIMESTAMP)
    completed_at = Column(TIMESTAMP)
    error_message = Column(Text)
    
    created_at = Column(TIMESTAMP, default=func.now())