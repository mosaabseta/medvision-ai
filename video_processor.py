"""
Video Processing Service
Handles frame extraction, analysis, and export generation
"""

import os
import cv2
import json
import tempfile
import zipfile
from pathlib import Path
from typing import List, Dict, Optional, Generator
from datetime import datetime
import numpy as np
from PIL import Image
import torch
import json
import re

from sqlalchemy.orm import Session
from models import VideoSession, VideoFrame, FrameAnalysis, SessionSummary
from storage_service import StorageService
from medgemma_engine import MedGemmaEngine


class VideoProcessor:
    """
    Efficient video processing with memory management
    """
    
    def __init__(
        self,
        storage_service: StorageService,
        ai_engine: MedGemmaEngine,
        target_fps: float = 1.0,
        batch_size: int = 10
    ):
        self.storage = storage_service
        self.ai_engine = ai_engine
        self.target_fps = target_fps
        self.batch_size = batch_size
    
    def extract_frames(
        self,
        video_path: str,
        session_id: str,
        db: Session,
        progress_callback=None
    ) -> int:
        """
        Extract frames from video with intelligent sampling
        
        Returns: Number of frames extracted
        """
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        # Get video properties
        original_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_ms = (total_frames / original_fps) * 1000
        
        # Calculate frame sampling interval
        frame_interval = int(original_fps / self.target_fps)
        
        frames_extracted = 0
        frame_index = 0
        
        while True:
            ret, frame = cap.read()
            
            if not ret:
                break
            
            # Sample frames at target FPS
            if frame_index % frame_interval == 0:
                timestamp_ms = int((frame_index / original_fps) * 1000)
                
                # Convert timestamp to HH:MM:SS.mmm
                hours = timestamp_ms // 3600000
                minutes = (timestamp_ms % 3600000) // 60000
                seconds = (timestamp_ms % 60000) // 1000
                milliseconds = timestamp_ms % 1000
                timestamp_formatted = f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
                
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(frame_rgb)
                
                # Save frame to storage
                frame_filename = f"frame_{frames_extracted:06d}.jpg"
                frame_path = self.storage.save_frame(
                    session_id,
                    frame_filename,
                    pil_image
                )
                
                # Detect if keyframe (simplified - check for scene change)
                is_keyframe = self._is_keyframe(frame)
                
                # Create database record
                db_frame = VideoFrame(
                    session_id=session_id,
                    frame_index=frames_extracted,
                    timestamp_ms=timestamp_ms,
                    timestamp_formatted=timestamp_formatted,
                    frame_image_path=frame_path,
                    is_keyframe=is_keyframe
                )
                db.add(db_frame)
                
                frames_extracted += 1
                
                # Commit every 10 frames to avoid memory buildup
                if frames_extracted % 10 == 0:
                    db.commit()
                    
                    if progress_callback:
                        progress = int((frame_index / total_frames) * 30)  # 0-30% for extraction
                        progress_callback(progress)
            
            frame_index += 1
        
        cap.release()
        db.commit()
        
        return frames_extracted
    
    def _is_keyframe(self, frame: np.ndarray) -> bool:
        """
        Simple keyframe detection based on image characteristics
        """
        # Calculate average brightness and contrast
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mean_brightness = np.mean(gray)
        std_contrast = np.std(gray)
        
        # Consider keyframe if high contrast and good brightness
        return std_contrast > 50 and 50 < mean_brightness < 200
    
    def analyze_frames_batch(
        self,
        session_id: str,
        db: Session,
        progress_callback=None
    ):
        """
        Analyze frames in batches to manage memory
        """
        # Get all unanalyzed frames
        frames = db.query(VideoFrame).filter(
            VideoFrame.session_id == session_id,
            VideoFrame.analyzed == False
        ).order_by(VideoFrame.frame_index).all()
        
        total_frames = len(frames)
        
        for i in range(0, total_frames, self.batch_size):
            batch = frames[i:i + self.batch_size]
            
            for frame in batch:
                start_time = datetime.now()
                
                # Load frame image
                image = self.storage.load_frame(frame.frame_image_path)
                
                # Run AI analysis
                analysis_result = self.ai_engine.analyze(
                    image,
                    prompt=self._get_analysis_prompt()
                )
                
                inference_time = int((datetime.now() - start_time).total_seconds() * 1000)
                print("\n===== MEDGEMMA OUTPUT =====")
                print(analysis_result)
                print("============================\n")
                # Parse structured output
                parsed = self._parse_analysis(analysis_result)
                
                # Create analysis record
                db_analysis = FrameAnalysis(
                    frame_id=frame.id,
                    session_id=session_id,
                    model_name=self.ai_engine.model_id,
                    inference_time_ms=inference_time,
                    finding=parsed.get("finding"),
                    anatomical_location=parsed.get("location"),
                    risk_level=parsed.get("risk_level"),
                    confidence_score=parsed.get("confidence", 0.75),
                    detected_features=json.dumps(parsed.get("detected_features", [])),
                    suggested_action=parsed.get("suggested_action"),
                    raw_output=analysis_result
                )
                db.add(db_analysis)
                
                # Mark frame as analyzed
                frame.analyzed = True
            
            # Commit batch
            db.commit()
            
            # Clear GPU cache
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            if progress_callback:
                progress = 30 + int((i / total_frames) * 50)  # 30-80% for analysis
                progress_callback(progress)
    
    def _get_analysis_prompt(self) -> str:
        """Get analysis prompt"""
        return """
You are analyzing a GI endoscopy frame.

You MUST respond EXACTLY in this format:

Finding: <short description or "No abnormal finding">
Location: <anatomical location or "Unknown">
Risk Level: Low / Medium / High
Suggested Action: <short suggestion>

Example:
Finding: Normal mucosa
Location: Stomach
Risk Level: Low
Suggested Action: Continue routine inspection

Be educational, not diagnostic.
"""
    
    def _parse_analysis(self, raw_output: str) -> Dict:
        result = {
            "finding": "No abnormal finding",
            "location": "Unknown",
            "risk_level": "low",
            "confidence": 0.75,
            "features": [],
            "suggested_action": "Continue inspection"
        }

        if not raw_output:
            return result

        # --- NEW: extract first structured block ---
        pattern = re.compile(
            r"Finding:\s*(.*?)\n"
            r"Location:\s*(.*?)\n"
            r"Risk Level:\s*(.*?)\n"
            r"Suggested Action:\s*(.*?)(?:\n|$)",
            re.DOTALL
        )

        match = pattern.search(raw_output)
        if match:
            result["finding"] = match.group(1).strip()
            result["location"] = match.group(2).strip()
            risk_text = match.group(3).lower()
            result["suggested_action"] = match.group(4).strip()

            if "high" in risk_text:
                result["risk_level"] = "high"
                result["confidence"] = 0.85
            elif "medium" in risk_text:
                result["risk_level"] = "medium"
                result["confidence"] = 0.80
            else:
                result["risk_level"] = "low"

            # feature extraction
            raw_lower = raw_output.lower()
            feature_keywords = ["erythema", "ulcer", "polyp", "inflammation", "bleeding", "lesion"]
            result["features"] = [kw for kw in feature_keywords if kw in raw_lower]

            return result

    # fallback to your original logic


    def generate_summary(
        self,
        session_id: str,
        db: Session
    ) -> SessionSummary:
        """
        Generate educational summary of entire session
        """
        # Get all analyses
        analyses = db.query(FrameAnalysis).filter(
            FrameAnalysis.session_id == session_id
        ).all()
        
        if not analyses:
            raise ValueError("No analyses found for session")
        
        # Aggregate findings
        all_findings = [a.finding for a in analyses if a.finding]
        high_risk = [a for a in analyses if a.risk_level == "high"]
        
        # Extract key findings (unique high/medium risk)
        key_findings = []
        seen_findings = set()
        
        for analysis in analyses:
            if analysis.risk_level in ["high", "medium"]:
                finding_key = f"{analysis.anatomical_location}_{analysis.finding[:50]}"
                if finding_key not in seen_findings:
                    key_findings.append(
                        f"{analysis.anatomical_location}: {analysis.finding[:100]}"
                    )
                    seen_findings.add(finding_key)
        
        # Generate overall summary
        overall_summary = self._generate_overall_summary(analyses)
        
        # Create summary record
        summary = SessionSummary(
            session_id=session_id,
            overall_summary=overall_summary,
            key_findings=json.dumps(key_findings[:10]),  # Top 10
            total_frames_analyzed=len(analyses),
            high_risk_findings_count=len(high_risk)
        )
        
        db.add(summary)
        db.commit()
        
        return summary
    
    def _generate_overall_summary(self, analyses: List[FrameAnalysis]) -> str:
        """Generate educational summary from all analyses"""
        
        if not analyses:
            return "No significant findings."
        
        total = len(analyses)
        high_risk = len([a for a in analyses if a.risk_level == "high"])
        medium_risk = len([a for a in analyses if a.risk_level == "medium"])
        
        # Collect unique anatomical locations
        locations = set(a.anatomical_location for a in analyses if a.anatomical_location)
        
        summary = f"""
Educational Summary:

Total frames analyzed: {total}
High-risk findings: {high_risk}
Medium-risk findings: {medium_risk}
Anatomical regions examined: {', '.join(locations) if locations else 'Various'}

This educational analysis highlights areas that may warrant further attention during the procedure. 
All findings should be interpreted by a qualified physician in the full clinical context.
"""
        
        return summary.strip()
    
    def create_export_bundle(
        self,
        session_id: str,
        db: Session,
        progress_callback=None
    ) -> str:
        """
        Create downloadable ZIP bundle with all artifacts
        
        Returns: Path to bundle in storage
        """
        # Get session data
        session = db.query(VideoSession).filter(VideoSession.id == session_id).first()
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        # Get all data
        frames = db.query(VideoFrame).filter(VideoFrame.session_id == session_id).all()
        analyses = db.query(FrameAnalysis).filter(FrameAnalysis.session_id == session_id).all()
        summary = db.query(SessionSummary).filter(SessionSummary.session_id == session_id).first()
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # 1. Copy original video
            if session.original_video_path:
                video_dest = temp_path / "original_video.mp4"
                self.storage.download_file(session.original_video_path, str(video_dest))
            
            if progress_callback:
                progress_callback(85)
            
            # 2. Generate frame_analysis.json
            frame_data = []
            for frame in frames:
                analysis = next((a for a in analyses if a.frame_id == frame.id), None)
                
                frame_entry = {
                    "frame_index": frame.frame_index,
                    "timestamp": frame.timestamp_formatted,
                    "timestamp_ms": frame.timestamp_ms,
                }
                
                if analysis:
                    frame_entry.update({
                        "analysis": analysis.finding,
                        "location": analysis.anatomical_location,
                        "risk_level": analysis.risk_level,
                        "confidence_score": float(analysis.confidence_score) if analysis.confidence_score else 0.75,
                        "detected_features": json.loads(analysis.detected_features or "[]")
                    })
                
                frame_data.append(frame_entry)
            
            analysis_file = temp_path / "frame_analysis.json"
            with open(analysis_file, "w") as f:
                json.dump(frame_data, f, indent=2)
            
            if progress_callback:
                progress_callback(90)
            
            # 3. Generate summary.txt
            if summary:
                summary_file = temp_path / "summary.txt"
                with open(summary_file, "w") as f:
                    f.write(summary.overall_summary)
                    f.write("\n\n")
                    f.write("Key Findings:\n")
                    for i, finding in enumerate(json.loads(summary.key_findings or "[]"), 1):
                        f.write(f"{i}. {finding}\n")
            
            # 4. Generate metadata.json
            metadata = {
                "session_id": str(session_id),
                "title": session.title,
                "procedure_type": session.procedure_type,
                "created_at": session.created_at.isoformat(),
                "duration_seconds": float(session.video_duration_seconds) if session.video_duration_seconds else 0,
                "total_frames": session.frame_count,
                "frames_analyzed": len(analyses),
                "export_generated_at": datetime.utcnow().isoformat()
            }
            
            metadata_file = temp_path / "metadata.json"
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)
            
            if progress_callback:
                progress_callback(95)
            
            # 5. Create ZIP archive
            bundle_filename = f"gi_copilot_export_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            bundle_temp_path = temp_path / bundle_filename
            
            with zipfile.ZipFile(bundle_temp_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file_path in temp_path.glob("*"):
                    if file_path.is_file() and file_path.suffix != ".zip":
                        zipf.write(file_path, file_path.name)
            
            # 6. Upload to storage
            bundle_storage_path = self.storage.save_export_bundle(
                session_id,
                bundle_filename,
                str(bundle_temp_path)
            )
            
            if progress_callback:
                progress_callback(100)
            
            return bundle_storage_path
