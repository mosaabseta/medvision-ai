"""
Chat Routes with Context-Aware Conversation
Integrates frame analysis into educational dialogue
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from models import VideoSession, VideoFrame, FrameAnalysis, Conversation, ConversationMessage, User
from database import get_db
from auth import get_current_user

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


class ChatMessageRequest(BaseModel):
    session_id: str
    message: str
    frame_id: Optional[str] = None  # Link to specific frame
    timestamp_ms: Optional[int] = None  # Video timestamp


class ChatMessageResponse(BaseModel):
    message_id: str
    role: str
    content: str
    created_at: str
    frame_context: Optional[dict] = None


@router.post("/message")
async def send_message(
    request: ChatMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Send chat message with context awareness
    
    Flow:
    1. Validate session access
    2. Get current frame context (if provided)
    3. Get recent conversation history
    4. Build context for AI
    5. Generate response
    6. Store both messages
    """
    
    # Verify session access
    session = db.query(VideoSession).filter(
        VideoSession.id == request.session_id,
        VideoSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get or create conversation
    conversation = db.query(Conversation).filter(
        Conversation.session_id == request.session_id
    ).first()
    
    if not conversation:
        conversation = Conversation(
            session_id=request.session_id,
            user_id=current_user.id
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    
    # Build context from frame and history
    context = await _build_conversation_context(
        db=db,
        session_id=request.session_id,
        conversation_id=conversation.id,
        frame_id=request.frame_id,
        timestamp_ms=request.timestamp_ms
    )
    
    # Store user message
    user_message = ConversationMessage(
        conversation_id=conversation.id,
        session_id=request.session_id,
        role="user",
        content=request.message,
        frame_id=request.frame_id,
        timestamp_ms=request.timestamp_ms
    )
    db.add(user_message)
    
    # Generate AI response with context
    ai_response = await _generate_ai_response(
        user_query=request.message,
        context=context
    )
    
    # Store assistant message
    assistant_message = ConversationMessage(
        conversation_id=conversation.id,
        session_id=request.session_id,
        role="assistant",
        content=ai_response["content"],
        frame_id=request.frame_id,
        timestamp_ms=request.timestamp_ms,
        model_name=ai_response.get("model_name", "gpt-4"),
        tokens_used=ai_response.get("tokens_used")
    )
    db.add(assistant_message)
    
    # Update conversation stats
    conversation.message_count += 2
    
    db.commit()
    db.refresh(assistant_message)
    
    return {
        "user_message": {
            "message_id": str(user_message.id),
            "role": "user",
            "content": request.message,
            "created_at": user_message.created_at.isoformat()
        },
        "assistant_message": {
            "message_id": str(assistant_message.id),
            "role": "assistant",
            "content": ai_response["content"],
            "created_at": assistant_message.created_at.isoformat(),
            "frame_context": context.get("current_frame")
        }
    }


async def _build_conversation_context(
    db: Session,
    session_id: str,
    conversation_id: str,
    frame_id: Optional[str] = None,
    timestamp_ms: Optional[int] = None
) -> dict:
    """
    Build comprehensive context for AI response
    """
    context = {
        "current_frame": None,
        "recent_frames": [],
        "conversation_history": [],
        "session_metadata": {}
    }
    
    # Get session metadata
    session = db.query(VideoSession).filter(VideoSession.id == session_id).first()
    context["session_metadata"] = {
        "procedure_type": session.procedure_type,
        "duration": float(session.video_duration_seconds) if session.video_duration_seconds else 0
    }
    
    # Get current frame analysis
    if frame_id:
        frame = db.query(VideoFrame).filter(VideoFrame.id == frame_id).first()
        if frame and frame.analysis:
            context["current_frame"] = {
                "timestamp": frame.timestamp_formatted,
                "finding": frame.analysis.finding,
                "location": frame.analysis.anatomical_location,
                "risk_level": frame.analysis.risk_level,
                "confidence": float(frame.analysis.confidence_score) if frame.analysis.confidence_score else None
            }
    elif timestamp_ms:
        # Find frame closest to timestamp
        frame = db.query(VideoFrame).filter(
            VideoFrame.session_id == session_id,
            VideoFrame.timestamp_ms <= timestamp_ms
        ).order_by(VideoFrame.timestamp_ms.desc()).first()
        
        if frame and frame.analysis:
            context["current_frame"] = {
                "timestamp": frame.timestamp_formatted,
                "finding": frame.analysis.finding,
                "location": frame.analysis.anatomical_location,
                "risk_level": frame.analysis.risk_level
            }
    
    # Get recent frames (last 5 analyzed frames)
    recent_frames = db.query(VideoFrame).join(FrameAnalysis).filter(
        VideoFrame.session_id == session_id,
        VideoFrame.analyzed == True
    ).order_by(VideoFrame.frame_index.desc()).limit(5).all()
    
    context["recent_frames"] = [
        {
            "timestamp": f.timestamp_formatted,
            "finding": f.analysis.finding,
            "risk_level": f.analysis.risk_level
        }
        for f in recent_frames if f.analysis
    ]
    
    # Get recent conversation (last 10 messages)
    recent_messages = db.query(ConversationMessage).filter(
        ConversationMessage.conversation_id == conversation_id
    ).order_by(ConversationMessage.created_at.desc()).limit(10).all()
    
    context["conversation_history"] = [
        {
            "role": m.role,
            "content": m.content
        }
        for m in reversed(recent_messages)
    ]
    
    return context


async def _generate_ai_response(user_query: str, context: dict) -> dict:
    """
    Generate AI response using context
    This is a placeholder - integrate with your actual AI service
    """
    
    # Build system prompt with context
    system_prompt = f"""
You are an educational AI assistant for medical procedures.

Session Context:
- Procedure Type: {context['session_metadata'].get('procedure_type', 'Unknown')}

Current Frame Analysis:
{_format_frame_context(context.get('current_frame'))}

Recent Findings:
{_format_recent_frames(context.get('recent_frames', []))}

IMPORTANT:
- Provide educational insights, NOT diagnostic conclusions
- Reference visible findings in the frame
- Suggest areas for further examination when appropriate
- Maintain professional medical terminology
"""
    
    # Build conversation messages
    messages = [
        {"role": "system", "content": system_prompt}
    ]
    
    # Add conversation history
    for msg in context.get("conversation_history", []):
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    # Add current query
    messages.append({"role": "user", "content": user_query})
    
    # Call your AI service here
    # For now, return a mock response
    # In production, integrate with OpenAI, Anthropic Claude, or your LLM
    
    response_content = f"""Based on the current frame analysis, I can provide the following educational insights:

{context.get('current_frame', {}).get('finding', 'No specific findings visible in this frame.')}

The anatomical location appears to be: {context.get('current_frame', {}).get('location', 'Not specified')}

Risk assessment: {context.get('current_frame', {}).get('risk_level', 'Low')}

This is for educational purposes. Always consult with a qualified physician for clinical decisions."""
    
    return {
        "content": response_content,
        "model_name": "gpt-4",
        "tokens_used": 150  # Placeholder
    }


def _format_frame_context(frame: Optional[dict]) -> str:
    """Format current frame context for prompt"""
    if not frame:
        return "No frame context available."
    
    return f"""
Timestamp: {frame.get('timestamp')}
Finding: {frame.get('finding')}
Anatomical Location: {frame.get('location')}
Risk Level: {frame.get('risk_level')}
Confidence: {frame.get('confidence', 'N/A')}
"""


def _format_recent_frames(frames: List[dict]) -> str:
    """Format recent frames for prompt"""
    if not frames:
        return "No recent frame history."
    
    formatted = []
    for i, frame in enumerate(frames, 1):
        formatted.append(
            f"{i}. [{frame.get('timestamp')}] {frame.get('finding')} (Risk: {frame.get('risk_level')})"
        )
    
    return "\n".join(formatted)


@router.get("/{session_id}/history")
def get_conversation_history(
    session_id: str,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get full conversation history for a session"""
    
    # Verify access
    session = db.query(VideoSession).filter(
        VideoSession.id == session_id,
        VideoSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get conversation
    conversation = db.query(Conversation).filter(
        Conversation.session_id == session_id
    ).first()
    
    if not conversation:
        return {"messages": [], "total": 0}
    
    # Get messages
    total = db.query(ConversationMessage).filter(
        ConversationMessage.conversation_id == conversation.id
    ).count()
    
    messages = db.query(ConversationMessage).filter(
        ConversationMessage.conversation_id == conversation.id
    ).order_by(ConversationMessage.created_at).offset(skip).limit(limit).all()
    
    return {
        "messages": [
            {
                "message_id": str(m.id),
                "role": m.role,
                "content": m.content,
                "timestamp_ms": m.timestamp_ms,
                "created_at": m.created_at.isoformat()
            }
            for m in messages
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/{session_id}/export")
def export_conversation(
    session_id: str,
    format: str = "json",  # json or txt
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export conversation transcript
    Used in the final bundle generation
    """
    
    # Verify access
    session = db.query(VideoSession).filter(
        VideoSession.id == session_id,
        VideoSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get conversation
    conversation = db.query(Conversation).filter(
        Conversation.session_id == session_id
    ).first()
    
    if not conversation:
        return {"transcript": []}
    
    # Get all messages
    messages = db.query(ConversationMessage).filter(
        ConversationMessage.conversation_id == conversation.id
    ).order_by(ConversationMessage.created_at).all()
    
    if format == "json":
        return {
            "session_id": str(session_id),
            "procedure_type": session.procedure_type,
            "conversation_started": conversation.started_at.isoformat(),
            "message_count": len(messages),
            "messages": [
                {
                    "timestamp": m.created_at.isoformat(),
                    "video_timestamp": m.timestamp_ms,
                    "role": m.role,
                    "content": m.content
                }
                for m in messages
            ]
        }
    else:  # txt format
        lines = [
            f"GI Copilot Conversation Transcript",
            f"Session: {session.title}",
            f"Date: {session.created_at.strftime('%Y-%m-%d %H:%M')}",
            f"Procedure Type: {session.procedure_type}",
            f"",
            f"=" * 60,
            f""
        ]
        
        for msg in messages:
            timestamp = msg.created_at.strftime("%H:%M:%S")
            lines.append(f"[{timestamp}] {msg.role.upper()}:")
            lines.append(msg.content)
            lines.append("")
        
        return {
            "transcript": "\n".join(lines)
        }
