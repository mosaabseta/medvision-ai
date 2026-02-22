"""
Enhanced FastAPI Routes for GI Copilot - Video Upload and Processing
Simplified for local use (no authentication required)
"""

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session
from typing import Optional
import os
import tempfile
from pathlib import Path
import cv2
from datetime import datetime
import uuid

from models import VideoSession, VideoFrame, FrameAnalysis, SessionSummary, User
from database import get_db, SessionLocal
from storage_service import StorageService

router = APIRouter(prefix="/api/v1/videos", tags=["videos"])

# Initialize storage service
storage = StorageService()


def get_or_create_default_user(db: Session) -> User:
    """Get or create default user for local testing"""
    user = db.query(User).filter(User.email == "local@user.com").first()
    
    if not user:
        # Use simple hash for local testing (not secure, only for development)
        import hashlib
        hashed_pw = hashlib.sha256("password".encode()).hexdigest()
        
        user = User(
            email="local@user.com",
            hashed_password=hashed_pw,
            full_name="Local User",
            role="physician",
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    return user


@router.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    title: str = None,
    description: str = None,
    procedure_type: str = None,
    db: Session = Depends(get_db)
):
    """
    Upload a recorded procedure video
    """
    
    # Get default user
    current_user = get_or_create_default_user(db)
    
    # Validate file type
    if not file.filename.lower().endswith((".mp4", ".avi", ".mov")):
        raise HTTPException(status_code=400, detail="Invalid video format. Supported: mp4, avi, mov")
    
    # Save to temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as temp_file:
        content = await file.read()
        temp_file.write(content)
        temp_file_path = temp_file.name
    
    try:
        # Extract video metadata
        cap = cv2.VideoCapture(temp_file_path)
        if not cap.isOpened():
            raise HTTPException(status_code=400, detail="Cannot process video file")
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_seconds = frame_count / fps if fps > 0 else 0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        
        # Get file size
        file_size = os.path.getsize(temp_file_path)
        
        # Create session record
        session = VideoSession(
            user_id=current_user.id,
            title=title or f"Procedure {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            description=description,
            procedure_type=procedure_type,
            session_type="recorded",
            video_duration_seconds=duration_seconds,
            video_size_bytes=file_size,
            fps=fps,
            processing_status="pending"
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        
        # Upload video to storage
        video_path = storage.save_video(
            str(session.id),
            temp_file_path,
            filename=f"original{Path(file.filename).suffix}"
        )
        
        session.original_video_path = video_path
        session.processing_status = "pending"
        db.commit()
        
        # For local development: Process immediately in background thread
        # In production, this would use Celery
        import threading
        
        def process_in_background():
            try:
                from video_processor import VideoProcessor
                from medgemma_engine import MedGemmaEngine
                
                # Update status
                db_session = SessionLocal()
                vid_session = db_session.query(VideoSession).filter(VideoSession.id == str(session.id)).first()
                vid_session.processing_status = "processing"
                db_session.commit()
                
                # Process video
                ai_engine = MedGemmaEngine()
                processor = VideoProcessor(storage, ai_engine)
                
                # Extract frames
                processor.extract_frames(
                    storage.get_file_path(video_path),
                    str(session.id),
                    db_session
                )
                
                # Analyze frames
                processor.analyze_frames_batch(str(session.id), db_session)
                
                # Generate summary
                processor.generate_summary(str(session.id), db_session)
                
                # Create export
                processor.create_export_bundle(str(session.id), db_session)
                
                # Update status
                vid_session.processing_status = "completed"
                vid_session.processing_progress = 100
                db_session.commit()
                db_session.close()
                
            except Exception as e:
                print(f"Error processing video: {e}")
                import traceback
                traceback.print_exc()
                
                db_session = SessionLocal()
                vid_session = db_session.query(VideoSession).filter(VideoSession.id == str(session.id)).first()
                if vid_session:
                    vid_session.processing_status = "failed"
                    db_session.commit()
                db_session.close()
        
        # Start processing in background
        thread = threading.Thread(target=process_in_background)
        thread.daemon = True
        thread.start()
        
        return JSONResponse({
            "status": "success",
            "session_id": str(session.id),
            "task_id": "local-processing",
            "message": "Video uploaded successfully. Processing started.",
            "video_info": {
                "duration_seconds": duration_seconds,
                "fps": fps,
                "resolution": f"{width}x{height}",
                "file_size_mb": round(file_size / (1024 * 1024), 2)
            }
        })
    
    finally:
        # Clean up temporary file
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


@router.get("/{session_id}")
def get_video_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get video session details"""
    
    session = db.query(VideoSession).filter(VideoSession.id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get analysis statistics
    total_frames = db.query(VideoFrame).filter(VideoFrame.session_id == session_id).count()
    analyzed_frames = db.query(VideoFrame).filter(
        VideoFrame.session_id == session_id,
        VideoFrame.analyzed == True
    ).count()
    
    high_risk_count = db.query(FrameAnalysis).filter(
        FrameAnalysis.session_id == session_id,
        FrameAnalysis.risk_level == "high"
    ).count()
    
    return {
        "session_id": str(session.id),
        "title": session.title,
        "description": session.description,
        "procedure_type": session.procedure_type,
        "session_type": session.session_type,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "duration_seconds": float(session.video_duration_seconds) if session.video_duration_seconds else 0,
        "processing_status": session.processing_status,
        "processing_progress": session.processing_progress,
        "statistics": {
            "total_frames": total_frames,
            "analyzed_frames": analyzed_frames,
            "high_risk_findings": high_risk_count
        },
        "export_available": session.export_bundle_path is not None
    }


@router.get("/{session_id}/status")
def get_processing_status(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get real-time processing status"""
    
    session = db.query(VideoSession).filter(VideoSession.id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": str(session.id),
        "status": session.processing_status,
        "progress": session.processing_progress,
        "started_at": session.processing_started_at.isoformat() if session.processing_started_at else None,
        "completed_at": session.processing_completed_at.isoformat() if session.processing_completed_at else None
    }


@router.get("/{session_id}/frames")
def get_frames(
    session_id: str,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get frame list with analysis"""
    
    session = db.query(VideoSession).filter(VideoSession.id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    frames = db.query(VideoFrame).filter(
        VideoFrame.session_id == session_id
    ).order_by(VideoFrame.frame_index).offset(skip).limit(limit).all()
    
    result = []
    for frame in frames:
        frame_data = {
            "frame_id": str(frame.id),
            "frame_index": frame.frame_index,
            "timestamp": frame.timestamp_formatted,
            "timestamp_ms": frame.timestamp_ms,
            "is_keyframe": frame.is_keyframe,
            "analyzed": frame.analyzed
        }
        
        # Add analysis if available
        if frame.analysis:
            # Parse JSON string for features if needed
            import json
            features = frame.analysis.detected_features
            if isinstance(features, str):
                try:
                    features = json.loads(features)
                except:
                    features = []
            
            frame_data["analysis"] = {
                "finding": frame.analysis.finding,
                "location": frame.analysis.anatomical_location,
                "risk_level": frame.analysis.risk_level,
                "confidence_score": float(frame.analysis.confidence_score) if frame.analysis.confidence_score else None,
                "detected_features": features
            }
        
        result.append(frame_data)
    
    return {
        "frames": result,
        "skip": skip,
        "limit": limit,
        "total": db.query(VideoFrame).filter(VideoFrame.session_id == session_id).count()
    }


@router.get("/{session_id}/summary")
def get_session_summary(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get educational summary"""
    
    session = db.query(VideoSession).filter(VideoSession.id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    summary = db.query(SessionSummary).filter(
        SessionSummary.session_id == session_id
    ).first()
    
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not yet generated")
    
    # Parse key_findings JSON if it's a string
    import json
    key_findings = summary.key_findings
    if isinstance(key_findings, str):
        try:
            key_findings = json.loads(key_findings)
        except:
            key_findings = []
    
    return {
        "session_id": str(session_id),
        "overall_summary": summary.overall_summary,
        "key_findings": key_findings,
        "statistics": {
            "total_frames_analyzed": summary.total_frames_analyzed,
            "high_risk_findings": summary.high_risk_findings_count
        },
        "generated_at": summary.generated_at.isoformat() if summary.generated_at else None
    }


@router.get("/{session_id}/export")
def download_export(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Download export bundle"""
    
    session = db.query(VideoSession).filter(VideoSession.id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if not session.export_bundle_path:
        raise HTTPException(status_code=404, detail="Export not yet generated")
    
    # Get absolute file path
    file_path = storage.get_file_path(session.export_bundle_path)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Export file not found")
    
    # Return file for download
    return FileResponse(
        file_path,
        media_type="application/zip",
        filename=os.path.basename(file_path)
    )


@router.delete("/{session_id}")
def delete_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Delete video session and all associated data"""
    
    session = db.query(VideoSession).filter(VideoSession.id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Delete from storage
    try:
        storage.delete_session_files(str(session.id))
    except Exception as e:
        print(f"Error deleting storage files: {e}")
    
    # Delete from database (cascade will handle related records)
    db.delete(session)
    db.commit()
    
    return {"status": "success", "message": "Session deleted"}


@router.get("/")
def list_sessions(
    skip: int = 0,
    limit: int = 20,
    procedure_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all video sessions"""
    
    query = db.query(VideoSession)
    
    if procedure_type:
        query = query.filter(VideoSession.procedure_type == procedure_type)
    
    total = query.count()
    sessions = query.order_by(VideoSession.created_at.desc()).offset(skip).limit(limit).all()
    
    return {
        "sessions": [
            {
                "session_id": str(s.id),
                "title": s.title,
                "procedure_type": s.procedure_type,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "processing_status": s.processing_status,
                "export_available": s.export_bundle_path is not None
            }
            for s in sessions
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }