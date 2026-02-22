"""
Celery Tasks for Asynchronous Video Processing
"""

from celery import Celery, Task
from celery.utils.log import get_task_logger
import os
import tempfile
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from models import VideoSession, ProcessingTask
from video_processor import VideoProcessor
from storage_service import StorageService
from medgemma_engine import MedGemmaEngine
from database import get_db

logger = get_task_logger(__name__)

# Initialize Celery
celery_app = Celery(
    "gi_copilot",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    task_soft_time_limit=3300,  # 55 minutes soft limit
    worker_prefetch_multiplier=1,  # Process one task at a time per worker
    worker_max_tasks_per_child=10,  # Restart worker after 10 tasks (prevent memory leaks)
)


class DatabaseTask(Task):
    """Base task with database session"""
    
    _db = None
    _storage = None
    _ai_engine = None
    _processor = None
    
    @property
    def db(self) -> Session:
        if self._db is None:
            engine = create_engine(os.getenv("DATABASE_URL"))
            SessionLocal = sessionmaker(bind=engine)
            self._db = SessionLocal()
        return self._db
    
    @property
    def storage(self) -> StorageService:
        if self._storage is None:
            self._storage = StorageService(
                bucket_name=os.getenv("S3_BUCKET_NAME", "gi-copilot"),
                endpoint_url=os.getenv("S3_ENDPOINT_URL"),  # MinIO endpoint
            )
        return self._storage
    
    @property
    def ai_engine(self) -> MedGemmaEngine:
        if self._ai_engine is None:
            self._ai_engine = MedGemmaEngine(
                model_id=os.getenv("AI_MODEL_ID", "google/medgemma-4b-it")
            )
        return self._ai_engine
    
    @property
    def processor(self) -> VideoProcessor:
        if self._processor is None:
            self._processor = VideoProcessor(
                storage_service=self.storage,
                ai_engine=self.ai_engine,
                target_fps=float(os.getenv("TARGET_FPS", "1.0")),
                batch_size=int(os.getenv("BATCH_SIZE", "10"))
            )
        return self._processor


@celery_app.task(bind=True, base=DatabaseTask, name="tasks.process_video")
def process_video_task(self, session_id: str):
    """
    Main task: Process entire video pipeline
    """
    logger.info(f"Starting video processing for session {session_id}")
    
    try:
        # Update session status
        session = self.db.query(VideoSession).filter(
            VideoSession.id == session_id
        ).first()
        
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        session.processing_status = "processing"
        self.db.commit()
        
        # Create task record
        task_record = ProcessingTask(
            celery_task_id=self.request.id,
            session_id=session_id,
            task_type="process_video",
            task_status="running"
        )
        self.db.add(task_record)
        self.db.commit()
        
        # Download video to temporary location
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_video:
            temp_video_path = temp_video.name
            self.storage.download_file(session.original_video_path, temp_video_path)
        
        try:
            # Step 1: Extract frames (0-30%)
            logger.info("Extracting frames...")
            frames_extracted = self.processor.extract_frames(
                video_path=temp_video_path,
                session_id=session_id,
                db=self.db,
                progress_callback=lambda p: self._update_progress(session_id, p)
            )
            
            session.frame_count = frames_extracted
            self.db.commit()
            
            # Step 2: Analyze frames (30-80%)
            logger.info(f"Analyzing {frames_extracted} frames...")
            self.processor.analyze_frames_batch(
                session_id=session_id,
                db=self.db,
                progress_callback=lambda p: self._update_progress(session_id, p)
            )
            
            # Step 3: Generate summary (80-90%)
            logger.info("Generating summary...")
            self._update_progress(session_id, 80)
            summary = self.processor.generate_summary(session_id, self.db)
            
            # Step 4: Create export bundle (90-100%)
            logger.info("Creating export bundle...")
            self._update_progress(session_id, 90)
            bundle_path = self.processor.create_export_bundle(
                session_id=session_id,
                db=self.db,
                progress_callback=lambda p: self._update_progress(session_id, p)
            )
            
            # Update session
            session.export_bundle_path = bundle_path
            session.processing_status = "completed"
            session.processing_progress = 100
            self.db.commit()
            
            # Update task
            task_record.task_status = "success"
            task_record.progress_current = 100
            self.db.commit()
            
            logger.info(f"Video processing completed for session {session_id}")
            
            return {
                "status": "success",
                "session_id": session_id,
                "frames_extracted": frames_extracted,
                "bundle_path": bundle_path
            }
            
        finally:
            # Cleanup temporary video file
            if os.path.exists(temp_video_path):
                os.unlink(temp_video_path)
    
    except Exception as e:
        logger.error(f"Error processing video {session_id}: {str(e)}")
        
        # Update session
        session = self.db.query(VideoSession).filter(
            VideoSession.id == session_id
        ).first()
        if session:
            session.processing_status = "failed"
            self.db.commit()
        
        # Update task
        task_record = self.db.query(ProcessingTask).filter(
            ProcessingTask.celery_task_id == self.request.id
        ).first()
        if task_record:
            task_record.task_status = "failure"
            task_record.error_message = str(e)
            self.db.commit()
        
        raise
    
    finally:
        self.db.close()


def _update_progress(self, session_id: str, progress: int):
    """Update processing progress in database"""
    session = self.db.query(VideoSession).filter(
        VideoSession.id == session_id
    ).first()
    
    if session:
        session.processing_progress = progress
        self.db.commit()


@celery_app.task(bind=True, base=DatabaseTask, name="tasks.extract_frames")
def extract_frames_task(self, session_id: str, video_path: str):
    """
    Standalone task: Extract frames only
    """
    logger.info(f"Extracting frames for session {session_id}")
    
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_video:
            temp_video_path = temp_video.name
            self.storage.download_file(video_path, temp_video_path)
        
        try:
            frames_extracted = self.processor.extract_frames(
                video_path=temp_video_path,
                session_id=session_id,
                db=self.db
            )
            
            return {
                "status": "success",
                "frames_extracted": frames_extracted
            }
        finally:
            if os.path.exists(temp_video_path):
                os.unlink(temp_video_path)
    
    finally:
        self.db.close()


@celery_app.task(bind=True, base=DatabaseTask, name="tasks.analyze_frames")
def analyze_frames_task(self, session_id: str):
    """
    Standalone task: Analyze frames only
    """
    logger.info(f"Analyzing frames for session {session_id}")
    
    try:
        self.processor.analyze_frames_batch(
            session_id=session_id,
            db=self.db
        )
        
        return {"status": "success"}
    
    finally:
        self.db.close()


@celery_app.task(bind=True, base=DatabaseTask, name="tasks.generate_export")
def generate_export_task(self, session_id: str):
    """
    Standalone task: Generate export bundle only
    """
    logger.info(f"Generating export bundle for session {session_id}")
    
    try:
        bundle_path = self.processor.create_export_bundle(
            session_id=session_id,
            db=self.db
        )
        
        # Update session
        session = self.db.query(VideoSession).filter(
            VideoSession.id == session_id
        ).first()
        
        if session:
            session.export_bundle_path = bundle_path
            self.db.commit()
        
        return {
            "status": "success",
            "bundle_path": bundle_path
        }
    
    finally:
        self.db.close()


# Celery beat schedule for periodic tasks (optional)
celery_app.conf.beat_schedule = {
    "cleanup-old-exports": {
        "task": "tasks.cleanup_old_exports",
        "schedule": 86400.0,  # Daily
    },
}


@celery_app.task(name="tasks.cleanup_old_exports")
def cleanup_old_exports():
    """
    Periodic task: Clean up old export bundles
    """
    logger.info("Running cleanup of old exports")
    
    # This would implement your cleanup logic
    # e.g., delete exports older than 90 days
    pass
