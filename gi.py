from fastapi import APIRouter, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from PIL import Image
import io

from medgemma_engine import MedGemmaEngine
from timeline_store import TimelineStore
from prompts import GI_SNAPSHOT_PROMPT, GI_CLARIFY_PROMPT

import asyncio
import websockets
import json

router = APIRouter(prefix="/api/gi", tags=["gi"])


engine = MedGemmaEngine("google/medgemma-4b-it")
timeline = TimelineStore()

latest_frame = None

import re


def clean_medgemma_output(raw_output: str) -> str:
    """
    Remove system prompts and duplicate label structures from MedGemma output
    """
    import re
    
    # Remove system prompt patterns
    prompt_patterns = [
        r"You are MedGemma.*?(?=Finding:|Location:|Risk Level:|$)",
        r"Analyze this.*?(?=Finding:|Location:|Risk Level:|$)",
        r"Return ONLY structured output.*?(?=Finding:|Location:|Risk Level:|$)",
        r"\[System\].*?(?=Finding:|Location:|Risk Level:|$)",
        r"Do NOT provide.*?(?=Finding:|Location:|Risk Level:|$)",
        r"Be cautious.*?(?=Finding:|Location:|Risk Level:|$)",
        r"assisting an endoscopist.*?(?=Finding:|Location:|Risk Level:|$)",
        r"<start_of_image>.*?(?=Finding:|Location:|Risk Level:|$)"
    ]
    
    cleaned = raw_output
    
    for pattern in prompt_patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    
    # ✅ CRITICAL FIX: Remove duplicate empty label structure
    # Pattern: "Finding:\nLocation:\nRisk Level (Low/Medium/High):\nSuggested Next Step:\n"
    empty_structure = re.compile(
        r"Finding:\s*\n\s*Location:\s*\n\s*Risk Level \(Low/Medium/High\):\s*\n\s*Suggested Next Step:\s*\n",
        re.IGNORECASE
    )
    cleaned = empty_structure.sub('', cleaned)
    
    # Also remove if it's at the beginning without newlines
    empty_structure_inline = re.compile(
        r"^Finding:\s*Location:\s*Risk Level \(Low/Medium/High\):\s*Suggested Next Step:\s*",
        re.IGNORECASE
    )
    cleaned = empty_structure_inline.sub('', cleaned)
    
    # Remove extra whitespace
    cleaned = re.sub(r'\n\s*\n', '\n', cleaned)
    cleaned = cleaned.strip()
    
    return cleaned

def extract_structured_answer(text: str) -> str:
    """
    Extract structured finding from MedGemma output
    Returns formatted string or empty string if not found
    """
    import re
    
    # First clean the text
    cleaned = clean_medgemma_output(text)
    
    # ✅ Extract structured components (flexible pattern)
    # Handles both "Risk Level:" and "Risk Level (Low/Medium/High):"
    pattern = re.compile(
        r"Finding:\s*(.*?)\s*\n"
        r"\s*Location:\s*(.*?)\s*\n"
        r"\s*Risk(?:\s+Level)?(?:\s*\(Low/Medium/High\))?:\s*(.*?)\s*\n"
        r"\s*Suggested (?:Next Step|Action):\s*(.*?)(?:\n|$)",
        re.DOTALL | re.IGNORECASE
    )

    match = pattern.search(cleaned)
    if match:
        finding = match.group(1).strip()
        location = match.group(2).strip()
        risk = match.group(3).strip()
        action = match.group(4).strip()
        
        # ✅ VALIDATION: Must have actual content in finding
        # Skip if finding is empty or just whitespace
        if not finding or len(finding) < 3:
            print(f"⚠️ Skipping - empty finding")
            return ""
        
        # Skip if finding contains prompt artifacts
        if any(word in finding.lower() for word in ['medgemma', 'analyze', 'endoscopist']):
            print(f"⚠️ Skipping - prompt artifact in finding")
            return ""
        
        return "\n".join([
            f"Finding: {finding}",
            f"Location: {location}",
            f"Risk Level: {risk}",
            f"Suggested Action: {action}",
        ])
    
    print(f"⚠️ No structured pattern matched")
    return ""


@router.post("/snapshot")
async def snapshot(file: UploadFile):
    global latest_frame

    try:
        img_bytes = await file.read()
        image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        latest_frame = image

        # Get raw output from MedGemma
        output = engine.analyze(image, GI_SNAPSHOT_PROMPT)
        
        print(f"\n📸 Raw MedGemma output ({len(output)} chars):")
        print(f"---\n{output[:200]}...\n---")
        
        # Extract structured answer
        clean = extract_structured_answer(output)
        
        # Use cleaned version if available
        if clean:
            result = clean
            print(f"✅ Extracted structured finding:")
            print(f"---\n{result}\n---")
        else:
            # Fallback: try basic cleaning
            result = clean_medgemma_output(output)
            
            # If still nothing useful, skip
            if not result or len(result) < 10:
                print(f"⚠️ No meaningful finding - skipping timeline")
                return {"status": "ok", "result": "No significant findings detected"}
            
            print(f"⚠️ Using cleaned raw output:")
            print(f"---\n{result[:200]}...\n---")
        
        # ✅ STRICT VALIDATION before adding to timeline
        # Must have actual content and not be prompt text
        should_add = (
            result and 
            len(result) > 15 and 
            not result.startswith('Finding:\nLocation:') and  # Empty structure
            'Finding:' in result and  # Must have actual finding
            not any(word in result.lower() for word in ['you are medgemma', 'analyze this', 'endoscopist'])
        )
        
        if should_add:
            timeline.add(result)
            print(f"💾 Added to timeline")
        else:
            print(f"⚠️ Validation failed - not adding to timeline")
            print(f"   Length: {len(result)}, Has 'Finding:': {'Finding:' in result}")
        
        return {"status": "ok", "result": result}
        
    except Exception as e:
        print(f"❌ Snapshot error: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "result": f"Analysis failed: {str(e)}"}


# ===== UPDATED TIMELINE ENDPOINT =====

@router.get("/timeline")
def get_timeline():
    """Get all findings from current timeline with strict filtering"""
    findings = timeline.all()
    
    structured_findings = []
    
    for idx, finding in enumerate(findings):
        # Clean the finding text
        if isinstance(finding, str):
            cleaned_text = clean_medgemma_output(finding)
            
            # ✅ STRICT VALIDATION
            is_valid = (
                cleaned_text and 
                len(cleaned_text) > 15 and
                'Finding:' in cleaned_text and
                not cleaned_text.startswith('Finding:\nLocation:') and  # Empty structure
                not any(word in cleaned_text.lower() for word in [
                    'you are medgemma', 
                    'analyze this', 
                    'endoscopist',
                    'return only'
                ])
            )
            
            if is_valid:
                structured_findings.append({
                    "id": idx,
                    "finding": cleaned_text,
                    "time": f"{idx * 3}s"
                })
            else:
                print(f"⚠️ Filtered out invalid finding {idx}")
                
        elif isinstance(finding, dict):
            finding_text = finding.get('finding', finding.get('text', ''))
            cleaned_text = clean_medgemma_output(str(finding_text))
            
            if cleaned_text and len(cleaned_text) > 15 and 'Finding:' in cleaned_text:
                structured_findings.append({
                    "id": finding.get('id', idx),
                    "finding": cleaned_text,
                    "time": finding.get('time', f"{idx * 3}s")
                })
    
    print(f"📊 Timeline: {len(findings)} raw → {len(structured_findings)} valid findings")
    
    return {"timeline": structured_findings}



@router.post("/clarify")
async def clarify(payload: dict):
    global latest_frame

    if latest_frame is None:
        return JSONResponse({"error": "No snapshot yet"}, status_code=400)

    question = payload.get("question", "")

    prompt = GI_CLARIFY_PROMPT.format(question=question)

    result = engine.analyze(latest_frame, prompt)
    timeline.add("CLARIFY: " + result)

    return {"answer": result}


import os, requests
import uuid
from datetime import datetime

# Track current session
current_session_id = None

@router.post("/session/start")
async def start_live_session(payload: dict):
    """Start a new live session"""
    global current_session_id
    
    try:
        current_session_id = str(uuid.uuid4())
        
        # Clear timeline if method exists
        if hasattr(timeline, 'clear'):
            timeline.clear()
        else:
            # Alternative: reset timeline list
            if hasattr(timeline, 'timeline'):
                timeline.timeline = []
        
        title = payload.get("title", f"Live Session {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
        print(f"🎬 Started live session: {current_session_id}")
        
        return JSONResponse({
            "session_id": current_session_id,
            "title": title,
            "started_at": datetime.now().isoformat()
        })
    
    except Exception as e:
        print(f"❌ Session start error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )


@router.post("/session/save")
async def save_live_session(payload: dict):
    """
    Save current live session to database with frames and export bundle
    Matches upload video flow - includes frame images
    """
    global current_session_id, latest_frame
    
    if not current_session_id:
        return JSONResponse({"error": "No active session"}, status_code=400)
    
    all_findings = timeline.all()
    if not all_findings:
        return JSONResponse({"error": "No findings to save"}, status_code=400)
    
    try:
        from database import SessionLocal
        from models import VideoSession, VideoFrame, FrameAnalysis, SessionSummary, User
        import json
        from datetime import datetime
        import zipfile
        from pathlib import Path
        from PIL import Image
        import io
        import base64
        
        db = SessionLocal()
        
        # Create storage directories
        frames_dir = Path(f"/workspace/frames/{current_session_id}")
        frames_dir.mkdir(parents=True, exist_ok=True)
        
        export_dir = Path("/workspace/exports")
        export_dir.mkdir(exist_ok=True)
        
        # Get or create user
        user = db.query(User).filter(User.email == "local@user.com").first()
        if not user:
            import hashlib
            user = User(
                id=str(uuid.uuid4()),
                email="local@user.com",
                hashed_password=hashlib.sha256(b"local").hexdigest(),
                full_name="Local User",
                role="physician",
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        
        # Create video session
        title = payload.get("title", f"Live Session {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        procedure_type = payload.get("procedure_type", "other")
        include_frames = payload.get("include_frames_in_export", False)  # Optional
        
        session = VideoSession(
            id=current_session_id,
            user_id=user.id,
            title=title,
            procedure_type=procedure_type,
            session_type="live",
            description="Live session with real-time AI analysis",
            processing_status="completed",
            processing_progress=100,
            processing_completed_at=datetime.now(),
            frame_count=len(all_findings)
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        
        # Save findings as frames + analyses + FRAME IMAGES
        high_risk_count = 0
        saved_frame_paths = []  # Track frame images for export
        
        for idx, entry in enumerate(all_findings):
            try:
                if isinstance(entry, dict):
                    finding_text = entry.get("finding", str(entry))
                    timestamp = entry.get("time", f"{idx*3}s")
                else:
                    finding_text = str(entry)
                    timestamp = f"{idx*3}s"
                
                # Extract structured data
                structured = extract_structured_answer(finding_text)
                
                if structured:
                    parts = structured.split('\n')
                    finding = ""
                    location = ""
                    risk_level = ""
                    action = ""
                    
                    for part in parts:
                        if part.startswith("Finding:"):
                            finding = part.replace("Finding:", "").strip()
                        elif part.startswith("Location:"):
                            location = part.replace("Location:", "").strip()
                        elif part.startswith("Risk Level:"):
                            risk_level = part.replace("Risk Level:", "").strip()
                        elif part.startswith("Suggested Action:"):
                            action = part.replace("Suggested Action:", "").strip()
                else:
                    finding = finding_text[:500]
                    location = "Unknown"
                    risk_level = "low"
                    action = ""
                
                # ===== SAVE FRAME IMAGE (if latest_frame available) =====
                frame_image_path = None
                if latest_frame is not None:
                    try:
                        frame_filename = f"frame_{idx:04d}.jpg"
                        frame_path = frames_dir / frame_filename
                        
                        # Save frame image
                        latest_frame.save(frame_path, "JPEG", quality=85)
                        
                        # Store relative path
                        frame_image_path = f"frames/{current_session_id}/{frame_filename}"
                        saved_frame_paths.append(str(frame_path))
                        
                        print(f"💾 Saved frame image: {frame_filename}")
                        
                    except Exception as img_error:
                        print(f"⚠️ Could not save frame image {idx}: {img_error}")
                
                # Create VideoFrame
                frame = VideoFrame(
                    id=str(uuid.uuid4()),
                    session_id=current_session_id,
                    frame_index=idx,
                    timestamp_ms=idx * 3000,
                    timestamp_formatted=timestamp,
                    frame_image_path=frame_image_path,  # ← Store path
                    analyzed=True
                )
                db.add(frame)
                db.flush()
                
                # Create FrameAnalysis
                analysis = FrameAnalysis(
                    id=str(uuid.uuid4()),
                    frame_id=frame.id,
                    session_id=current_session_id,
                    model_name="medgemma-4b",
                    finding=finding,
                    anatomical_location=location,
                    risk_level=risk_level.lower(),
                    suggested_action=action,
                    raw_output=finding_text,
                    confidence_score=0.85
                )
                db.add(analysis)
                
                if risk_level.lower() == "high":
                    high_risk_count += 1
                    
            except Exception as e:
                print(f"⚠️ Could not save finding {idx}: {e}")
                continue
        
        db.commit()
        
        # Create summary
        summary_text = f"""Live Session Analysis Summary

Total Findings Captured: {len(all_findings)}
High Risk Findings: {high_risk_count}
Frames Saved: {len(saved_frame_paths)}
Session Duration: ~{len(all_findings) * 3} seconds
Analysis Model: MedGemma-4B

Recent Key Findings:
"""
        
        key_findings_list = []
        for entry in all_findings[-10:]:
            if isinstance(entry, dict):
                finding_text = entry.get("finding", str(entry))
            else:
                finding_text = str(entry)
            
            structured = extract_structured_answer(finding_text)
            if structured:
                for line in structured.split('\n'):
                    if line.startswith("Finding:"):
                        finding_summary = line.replace("Finding:", "").strip()
                        key_findings_list.append(finding_summary[:200])
                        summary_text += f"- {finding_summary[:200]}\n"
                        break
            else:
                finding_summary = finding_text[:200]
                key_findings_list.append(finding_summary)
                summary_text += f"- {finding_summary}\n"
        
        summary = SessionSummary(
            id=str(uuid.uuid4()),
            session_id=current_session_id,
            overall_summary=summary_text,
            key_findings=json.dumps(key_findings_list),
            total_frames_analyzed=len(all_findings),
            high_risk_findings_count=high_risk_count
        )
        db.add(summary)
        db.commit()
        
        print(f"✅ Saved live session: {current_session_id}")
        print(f"   - Findings: {len(all_findings)}")
        print(f"   - High Risk: {high_risk_count}")
        print(f"   - Frame images: {len(saved_frame_paths)}")
        
        # ===== AUTO-GENERATE EXPORT BUNDLE WITH OPTIONAL FRAMES =====
        try:
            print(f"📦 Generating export bundle...")
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_filename = f"live_session_{current_session_id[:8]}_{timestamp}.zip"
            zip_path = export_dir / export_filename
            
            # Create ZIP bundle
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # 1. Metadata
                metadata = {
                    "session_id": session.id,
                    "title": session.title,
                    "procedure_type": session.procedure_type,
                    "session_type": "live",
                    "created_at": session.created_at.isoformat() if session.created_at else None,
                    "total_findings": len(all_findings),
                    "high_risk_findings": high_risk_count,
                    "frames_included": include_frames,
                    "frame_count": len(saved_frame_paths),
                    "export_generated_at": datetime.now().isoformat()
                }
                zipf.writestr("metadata.json", json.dumps(metadata, indent=2))
                
                # 2. Summary
                summary_data = {
                    "overall_summary": summary_text,
                    "total_frames_analyzed": len(all_findings),
                    "high_risk_findings_count": high_risk_count,
                    "key_findings": key_findings_list
                }
                zipf.writestr("summary.json", json.dumps(summary_data, indent=2))
                
                # 3. Findings CSV
                csv_content = "Frame_Index,Timestamp,Finding,Location,Risk Level,Suggested Action\n"
                
                analyses = db.query(FrameAnalysis).filter(
                    FrameAnalysis.session_id == current_session_id
                ).order_by(FrameAnalysis.created_at).all()
                
                for idx, analysis in enumerate(analyses):
                    ts = analysis.created_at.strftime("%Y-%m-%d %H:%M:%S") if analysis.created_at else "Unknown"
                    finding = (analysis.finding or "").replace('"', '""').replace('\n', ' ')
                    location = (analysis.anatomical_location or "").replace('"', '""')
                    risk = (analysis.risk_level or "").replace('"', '""')
                    action = (analysis.suggested_action or "").replace('"', '""').replace('\n', ' ')
                    
                    csv_content += f'{idx},"{ts}","{finding}","{location}","{risk}","{action}"\n'
                
                zipf.writestr("findings.csv", csv_content)
                
                # 4. Detailed findings JSON
                findings_json = []
                for analysis in analyses:
                    findings_json.append({
                        "finding": analysis.finding,
                        "location": analysis.anatomical_location,
                        "risk_level": analysis.risk_level,
                        "suggested_action": analysis.suggested_action,
                        "timestamp": analysis.created_at.isoformat() if analysis.created_at else None,
                        "confidence": float(analysis.confidence_score) if analysis.confidence_score else None,
                        "model": analysis.model_name
                    })
                
                zipf.writestr("findings.json", json.dumps(findings_json, indent=2))
                
                # 5. ===== OPTIONAL: Include frame images =====
                if include_frames and saved_frame_paths:
                    print(f"📸 Including {len(saved_frame_paths)} frame images in export...")
                    
                    for frame_path in saved_frame_paths:
                        if os.path.exists(frame_path):
                            # Add to ZIP under frames/ directory
                            arcname = f"frames/{os.path.basename(frame_path)}"
                            zipf.write(frame_path, arcname=arcname)
                    
                    print(f"✅ Added {len(saved_frame_paths)} frames to export")
                
                # 6. Human-readable report
                report = f"""
================================================================================
MEDICAL PROCEDURE ANALYSIS REPORT
================================================================================

Session ID: {session.id}
Title: {session.title}
Procedure Type: {session.procedure_type}
Session Type: Live Session
Date: {session.created_at.strftime("%Y-%m-%d %H:%M:%S") if session.created_at else "Unknown"}
Frames Captured: {len(saved_frame_paths)}

================================================================================
SUMMARY
================================================================================

{summary_text}

================================================================================
DETAILED FINDINGS
================================================================================

"""
                
                for idx, analysis in enumerate(analyses, 1):
                    ts = analysis.created_at.strftime("%H:%M:%S") if analysis.created_at else "Unknown"
                    
                    report += f"""
--- Finding #{idx} ({ts}) ---
Finding: {analysis.finding or "N/A"}
Location: {analysis.anatomical_location or "Not specified"}
Risk Level: {analysis.risk_level or "Unknown"}
Suggested Action: {analysis.suggested_action or "Continue observation"}
Frame: frame_{idx-1:04d}.jpg {"(included)" if include_frames else "(not included)"}

"""
                
                report += f"""
================================================================================
EXPORT CONTENTS
================================================================================

Files included:
- metadata.json (session information)
- summary.json (analysis summary)
- findings.csv (Excel-compatible findings)
- findings.json (detailed structured data)
- report.txt (this file)
{f"- frames/ directory ({len(saved_frame_paths)} JPEG images)" if include_frames else ""}

================================================================================
END OF REPORT
================================================================================

Generated by MedVision AI - Real-Time Medical Procedure Assistant
Export Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
                
                zipf.writestr("report.txt", report)
            
            # Update session with export path
            session.export_bundle_path = f"exports/{export_filename}"
            session.export_generated_at = datetime.now()
            db.commit()
            
            file_size_kb = zip_path.stat().st_size / 1024
            print(f"✅ Export bundle created: {export_filename}")
            print(f"   - Files: {'6 (with frames)' if include_frames else '5 (no frames)'}")
            print(f"   - Size: {file_size_kb:.2f} KB")
            print(f"   - Frames included: {include_frames}")
            
        except Exception as export_error:
            print(f"⚠️ Export generation failed (non-critical): {export_error}")
            import traceback
            traceback.print_exc()
        
        return {
            "status": "success",
            "session_id": current_session_id,
            "title": title,
            "findings_count": len(all_findings),
            "high_risk_count": high_risk_count,
            "frames_saved": len(saved_frame_paths),
            "export_available": session.export_bundle_path is not None,
            "frames_in_export": include_frames
        }
    
    except Exception as e:
        db.rollback()
        print(f"❌ Save session error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)
    
    finally:
        db.close()


@router.post("/session/clear")
async def clear_session():
    """Clear current session timeline"""
    global current_session_id
    
    timeline.clear()
    current_session_id = None
    
    return {"status": "success", "message": "Session cleared"}


@router.post("/session/current")
async def get_current_session():
    """Get current session info"""
    return {
        "session_id": current_session_id,
        "findings_count": len(timeline.all()),
        "has_findings": len(timeline.all()) > 0
    }


# Store transcripts in memory (could be saved to DB later)
session_transcripts = {}

@router.post("/transcript/save")
async def save_transcript(payload: dict):
    """Save conversation transcript message"""
    global current_session_id
    
    if not current_session_id:
        return JSONResponse({"error": "No active session"}, status_code=400)
    
    role = payload.get("role")  # 'user' or 'assistant'
    content = payload.get("content")
    
    if not role or not content:
        return JSONResponse({"error": "Missing role or content"}, status_code=400)
    
    # Initialize transcript for this session if needed
    if current_session_id not in session_transcripts:
        session_transcripts[current_session_id] = []
    
    # Add message to transcript
    from datetime import datetime
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    }
    
    session_transcripts[current_session_id].append(message)
    
    print(f"💬 Saved {role} message: {content[:50]}...")
    
    return {
        "status": "success",
        "message_count": len(session_transcripts[current_session_id])
    }


@router.get("/transcript/get")
async def get_transcript():
    """Get transcript for current session"""
    global current_session_id
    
    if not current_session_id or current_session_id not in session_transcripts:
        return {"transcript": []}
    
    return {
        "session_id": current_session_id,
        "transcript": session_transcripts[current_session_id],
        "message_count": len(session_transcripts[current_session_id])
    }


@router.websocket("/realtime")
async def websocket_proxy(client_ws: WebSocket):
    """
    WebSocket proxy: Browser → This server → OpenAI Realtime API
    Bypasses RunPod HTTP proxy which blocks WebRTC UDP traffic.
    Audio flows through WebSocket (TCP/HTTP) which the proxy supports.
    """
    await client_ws.accept()
    print("🔌 Client WebSocket connected")

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if not OPENAI_API_KEY:
        await client_ws.send_json({"type": "error", "error": {"message": "OPENAI_API_KEY not set"}})
        await client_ws.close()
        return

    openai_ws_url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17"

    try:
        async with websockets.connect(
            openai_ws_url,
            additional_headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "OpenAI-Beta": "realtime=v1"
            }
        ) as openai_ws:
            print("✅ Connected to OpenAI Realtime WebSocket")

            # Send session config to OpenAI
            await openai_ws.send(json.dumps({
                "type": "session.update",
                "session": {
                    "modalities": ["audio", "text"],
                    "instructions": """You are GI Copilot Medical Voice Assistant.
You help endoscopists by discussing what they see in real-time during procedures.
You automatically receive MedGemma findings prefixed with [New MedGemma Finding].
Reference these findings when the user asks about what is visible in the video.
Guidelines: Be conversational, keep responses concise (1-2 sentences), provide educational insights not diagnoses.""",
                    "voice": "alloy",
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {"model": "whisper-1"},
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 500
                    }
                }
            }))

            # Notify client we're ready
            await client_ws.send_json({"type": "proxy.connected"})

            # Bidirectional relay
            async def client_to_openai():
                try:
                    while True:
                        data = await client_ws.receive_text()
                        await openai_ws.send(data)
                except (WebSocketDisconnect, Exception) as e:
                    print(f"Client disconnected: {e}")

            async def openai_to_client():
                try:
                    async for message in openai_ws:
                        await client_ws.send_text(message)
                except Exception as e:
                    print(f"OpenAI WS closed: {e}")

            # Run both directions concurrently
            await asyncio.gather(
                client_to_openai(),
                openai_to_client(),
                return_exceptions=True
            )

    except Exception as e:
        print(f"❌ WebSocket proxy error: {e}")
        try:
            await client_ws.send_json({"type": "error", "error": {"message": str(e)}})
        except:
            pass
    finally:
        print("🔌 WebSocket proxy closed")


@router.post("/realtime/token")
def realtime_token():
    try:
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        
        if not OPENAI_API_KEY:
            return JSONResponse(
                {"error": "OPENAI_API_KEY not set"},
                status_code=500
            )

        url = "https://api.openai.com/v1/realtime/sessions"

        payload = {
            "model": "gpt-4o-realtime-preview-2024-12-17",
            "voice": "alloy",
            "modalities": ["audio", "text"],
            "output_audio_format": "pcm16",  # ← CRITICAL: Force audio output
            "instructions": """You are GI Copilot Voice Assistant.
You help endoscopists during procedures.
Respond naturally to all questions.
Reference MedGemma findings when relevant.
Be conversational and supportive.""",
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 500
            }
        }

        print(f"🔑 Requesting OpenAI realtime token...")

        r = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=10
        )
        
        if r.status_code != 200:
            print(f"❌ OpenAI API error: {r.status_code} - {r.text}")
            return JSONResponse(
                {"error": f"OpenAI API error: {r.text}"},
                status_code=r.status_code
            )

        data = r.json()
        
        if "client_secret" not in data:
            print(f"❌ Invalid response from OpenAI: {data}")
            return JSONResponse(
                {"error": "Invalid response from OpenAI API"},
                status_code=500
            )
        
        print(f"✅ OpenAI realtime token obtained")

        return {
            "client_secret": data["client_secret"]["value"]
        }
    
    except requests.exceptions.Timeout:
        print("❌ OpenAI API timeout")
        return JSONResponse(
            {"error": "OpenAI API timeout"},
            status_code=504
        )
    
    except requests.exceptions.RequestException as e:
        print(f"❌ OpenAI API request failed: {e}")
        return JSONResponse(
            {"error": f"OpenAI API request failed: {str(e)}"},
            status_code=500
        )
    
    except Exception as e:
        print(f"❌ Realtime token error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )