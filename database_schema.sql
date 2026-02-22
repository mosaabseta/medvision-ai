-- =====================================================
-- GI Copilot - PostgreSQL Database Schema
-- =====================================================

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =====================================================
-- 1. USERS & AUTHENTICATION
-- =====================================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'physician',
    institution VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);

-- =====================================================
-- 2. VIDEO SESSIONS
-- =====================================================

CREATE TABLE video_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    title VARCHAR(500),
    description TEXT,
    procedure_type VARCHAR(100),
    session_type VARCHAR(50) NOT NULL,
    
    original_video_path VARCHAR(1000),
    video_duration_seconds NUMERIC(10, 2),
    video_size_bytes BIGINT,
    frame_count INTEGER,
    fps NUMERIC(5, 2),
    
    processing_status VARCHAR(50) DEFAULT 'pending',
    processing_progress INTEGER DEFAULT 0,
    processing_started_at TIMESTAMP,
    processing_completed_at TIMESTAMP,
    
    export_bundle_path VARCHAR(1000),
    export_generated_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT valid_session_type CHECK (session_type IN ('live', 'recorded'))
);

CREATE INDEX idx_video_sessions_user ON video_sessions(user_id);
CREATE INDEX idx_video_sessions_status ON video_sessions(processing_status);

-- =====================================================
-- 3. VIDEO FRAMES
-- =====================================================

CREATE TABLE video_frames (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES video_sessions(id) ON DELETE CASCADE,
    
    frame_index INTEGER NOT NULL,
    timestamp_ms BIGINT NOT NULL,
    timestamp_formatted VARCHAR(20),
    
    frame_image_path VARCHAR(1000),
    is_keyframe BOOLEAN DEFAULT FALSE,
    
    analyzed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(session_id, frame_index)
);

CREATE INDEX idx_frames_session ON video_frames(session_id);
CREATE INDEX idx_frames_timestamp ON video_frames(session_id, timestamp_ms);

-- =====================================================
-- 4. FRAME ANALYSIS
-- =====================================================

CREATE TABLE frame_analysis (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    frame_id UUID NOT NULL REFERENCES video_frames(id) ON DELETE CASCADE,
    session_id UUID NOT NULL REFERENCES video_sessions(id) ON DELETE CASCADE,
    
    model_name VARCHAR(100) NOT NULL,
    inference_time_ms INTEGER,
    
    finding TEXT,
    anatomical_location VARCHAR(200),
    risk_level VARCHAR(50),
    confidence_score NUMERIC(5, 4),
    
    detected_features JSONB,
    suggested_action TEXT,
    raw_output TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(frame_id)
);

CREATE INDEX idx_analysis_session ON frame_analysis(session_id);
CREATE INDEX idx_analysis_risk ON frame_analysis(risk_level);
CREATE INDEX idx_analysis_features ON frame_analysis USING GIN (detected_features);

-- =====================================================
-- 5. CONVERSATIONS
-- =====================================================

CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES video_sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    message_count INTEGER DEFAULT 0
);

CREATE INDEX idx_conversations_session ON conversations(session_id);

-- =====================================================
-- 6. CONVERSATION MESSAGES
-- =====================================================

CREATE TABLE conversation_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    session_id UUID NOT NULL REFERENCES video_sessions(id) ON DELETE CASCADE,
    
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    
    frame_id UUID REFERENCES video_frames(id) ON DELETE SET NULL,
    timestamp_ms BIGINT,
    
    model_name VARCHAR(100),
    tokens_used INTEGER,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT valid_role CHECK (role IN ('user', 'assistant', 'system'))
);

CREATE INDEX idx_messages_conversation ON conversation_messages(conversation_id);
CREATE INDEX idx_messages_session ON conversation_messages(session_id);
CREATE INDEX idx_messages_created ON conversation_messages(created_at);

-- =====================================================
-- 7. SESSION SUMMARIES
-- =====================================================

CREATE TABLE session_summaries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES video_sessions(id) ON DELETE CASCADE,
    
    overall_summary TEXT NOT NULL,
    key_findings TEXT[],
    
    total_frames_analyzed INTEGER,
    high_risk_findings_count INTEGER,
    
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(session_id)
);

-- =====================================================
-- 8. PROCESSING TASKS
-- =====================================================

CREATE TABLE processing_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    celery_task_id VARCHAR(255) UNIQUE NOT NULL,
    session_id UUID REFERENCES video_sessions(id) ON DELETE CASCADE,
    
    task_type VARCHAR(100) NOT NULL,
    task_status VARCHAR(50) DEFAULT 'pending',
    
    progress_current INTEGER DEFAULT 0,
    progress_total INTEGER,
    
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tasks_session ON processing_tasks(session_id);
CREATE INDEX idx_tasks_status ON processing_tasks(task_status);
