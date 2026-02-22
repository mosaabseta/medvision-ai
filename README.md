# MedVisor - Production System

AI-powered educational assistant for medical procedures with comprehensive video analysis and context-aware chat.

## 🌟 Features

### Core Capabilities
- **Video Upload & Processing**: Upload recorded procedure videos for batch analysis
- **Real-time Frame Analysis**: AI-powered analysis using MedGemma
- **Context-Aware Chat**: Educational dialogue with frame-level context
- **Export Bundles**: Download complete analysis packages
- **Temporal Memory**: Chat assistant remembers previous findings
- **Live Streaming**: Real-time analysis during procedures (legacy feature)

### New Features (v2.0)
- ✅ Recorded video processing pipeline
- ✅ Frame-by-frame AI analysis
- ✅ Structured data extraction
- ✅ Conversation logging with video timestamps
- ✅ Downloadable export bundles (ZIP)
- ✅ Async task processing with Celery
- ✅ Scalable storage with S3/MinIO
- ✅ Production-ready database schema

## 📋 Table of Contents
- [Architecture](#architecture)
- [Installation](#installation)
- [API Usage](#api-usage)
- [Deployment](#deployment)
- [Development](#development)

## 🏗️ Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system design.

**High-Level Overview:**
```
┌─────────────┐
│   Client    │ (Web, Mobile, Desktop)
└──────┬──────┘
       │
┌──────▼─────────────────────────────────┐
│      FastAPI Gateway                   │
│  - Video Upload                        │
│  - Chat Interface                      │
│  - Real-time Streaming                 │
└──────┬─────────────────────────────────┘
       │
┌──────▼─────────────┬───────────────────┐
│  Celery Workers    │  AI Engine        │
│  - Frame Extract   │  - MedGemma-4B    │
│  - Batch Analysis  │  - GPT-4 (Chat)   │
│  - Export Gen      │                   │
└────────────────────┴───────────────────┘
       │
┌──────▼─────────────┬───────────────────┐
│   PostgreSQL       │   MinIO/S3        │
│   - Metadata       │   - Videos        │
│   - Analysis       │   - Frames        │
│   - Conversations  │   - Exports       │
└────────────────────┴───────────────────┘
```

## 🚀 Installation

### Option 1: Docker Compose (Recommended)

```bash
# Clone repository
git clone https://github.com/mosaabseta/medvisor.git
cd doc-copilot

# Configure environment
cp .env.template .env
nano .env  # Edit configuration

# Start services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f api
```

### Option 2: Manual Installation

```bash
# Prerequisites
- Python 3.10+
- PostgreSQL 15+
- Redis 7+
- FFmpeg

# Install dependencies
pip install -r requirements_production.txt

# Setup database
createdb medvisor
alembic upgrade head

# Start Redis
redis-server

# Start API
uvicorn main_app:app --host 0.0.0.0 --port 8000

# Start Celery worker (separate terminal)
celery -A tasks worker --loglevel=info
```

## 📡 API Usage

### Authentication

```bash
# Register user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "doctor@hospital.com",
    "password": "secure_password",
    "full_name": "Dr. Smith"
  }'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "doctor@hospital.com",
    "password": "secure_password"
  }'

# Response
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

### Video Upload & Processing

```bash
# Upload video
curl -X POST http://localhost:8000/api/v1/videos/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@procedure_video.mp4" \
  -F "title=Upper GI Procedure 2024-02-11" \
  -F "procedure_type=upper_gi"

# Response
{
  "status": "success",
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "task_id": "abc123...",
  "message": "Video uploaded successfully. Processing started.",
  "video_info": {
    "duration_seconds": 1800,
    "fps": 30,
    "resolution": "1920x1080",
    "file_size_mb": 450.5
  }
}
```

### Check Processing Status

```bash
# Poll for status
curl -X GET http://localhost:8000/api/v1/videos/{session_id}/status \
  -H "Authorization: Bearer YOUR_TOKEN"

# Response
{
  "session_id": "123e4567...",
  "status": "processing",
  "progress": 65,
  "started_at": "2024-02-11T10:30:00Z"
}
```

### Get Analysis Results

```bash
# Get frame-level analysis
curl -X GET "http://localhost:8000/api/v1/videos/{session_id}/frames?skip=0&limit=10" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Response
{
  "frames": [
    {
      "frame_id": "...",
      "frame_index": 0,
      "timestamp": "00:00:01.033",
      "timestamp_ms": 1033,
      "is_keyframe": true,
      "analyzed": true,
      "analysis": {
        "finding": "Mild erythema observed in the gastric mucosa",
        "location": "Gastric body",
        "risk_level": "low",
        "confidence_score": 0.87,
        "detected_features": ["erythema", "mucosal_changes"]
      }
    }
  ],
  "total": 1800,
  "skip": 0,
  "limit": 10
}
```

### Get Summary

```bash
# Get educational summary
curl -X GET http://localhost:8000/api/v1/videos/{session_id}/summary \
  -H "Authorization: Bearer YOUR_TOKEN"

# Response
{
  "session_id": "...",
  "overall_summary": "Educational Summary:\n\nTotal frames analyzed: 1800...",
  "key_findings": [
    "Gastric body: Mild erythema with mucosal irregularity",
    "Duodenum: Normal appearing mucosa",
    "Esophagus: No significant findings"
  ],
  "statistics": {
    "total_frames_analyzed": 1800,
    "high_risk_findings": 2
  }
}
```

### Chat with Context

```bash
# Send chat message
curl -X POST http://localhost:8000/api/v1/chat/message \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "123e4567...",
    "message": "Can you explain the finding at 00:05:30?",
    "timestamp_ms": 330000
  }'

# Response
{
  "user_message": {
    "message_id": "...",
    "role": "user",
    "content": "Can you explain the finding at 00:05:30?",
    "created_at": "2024-02-11T11:00:00Z"
  },
  "assistant_message": {
    "message_id": "...",
    "role": "assistant",
    "content": "At timestamp 00:05:30, the analysis identified mild erythema in the gastric mucosa...",
    "created_at": "2024-02-11T11:00:01Z",
    "frame_context": {
      "timestamp": "00:05:30.500",
      "finding": "Mild erythema in gastric mucosa",
      "location": "Gastric body",
      "risk_level": "low"
    }
  }
}
```

### Download Export Bundle

```bash
# Get download URL
curl -X GET http://localhost:8000/api/v1/videos/{session_id}/export \
  -H "Authorization: Bearer YOUR_TOKEN"

# Response
{
  "session_id": "...",
  "download_url": "https://s3.amazonaws.com/gi-copilot/...",
  "expires_in_seconds": 3600
}

# Download bundle
wget "PRESIGNED_URL" -O procedure_export.zip
```

### Export Bundle Contents

```
procedure_export.zip
├── original_video.mp4
├── frame_analysis.json
├── summary.txt
├── transcript.json
└── metadata.json
```

**frame_analysis.json:**
```json
[
  {
    "frame_index": 0,
    "timestamp": "00:00:01.033",
    "timestamp_ms": 1033,
    "analysis": "Normal appearing esophageal mucosa",
    "location": "Esophagus",
    "risk_level": "low",
    "confidence_score": 0.92,
    "detected_features": []
  },
  ...
]
```

**transcript.json:**
```json
{
  "session_id": "...",
  "procedure_type": "upper_gi",
  "conversation_started": "2024-02-11T10:30:00Z",
  "message_count": 25,
  "messages": [
    {
      "timestamp": "2024-02-11T10:35:00Z",
      "video_timestamp": 300000,
      "role": "user",
      "content": "What is this lesion?"
    },
    {
      "timestamp": "2024-02-11T10:35:01Z",
      "role": "assistant",
      "content": "Based on the visible characteristics..."
    }
  ]
}
```

## 🧪 Testing

```bash
# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html

# Test specific module
pytest tests/test_video_processor.py -v

# Integration tests
pytest tests/integration/ -v
```

## 🔧 Development

### Project Structure

```
gi-copilot/
├── main_app.py              # FastAPI application
├── models.py                # Database models
├── database.py              # DB connection
├── auth.py                  # Authentication
├── routes_video.py          # Video endpoints
├── routes_chat.py           # Chat endpoints
├── gi.py                    # Legacy real-time routes
├── video_processor.py       # Video processing logic
├── storage_service.py       # S3/MinIO storage
├── medgemma_engine.py       # AI engine
├── tasks.py                 # Celery tasks
├── prompts.py               # AI prompts
├── requirements_production.txt
├── docker-compose.yml
├── Dockerfile_production
├── .env.template
├── ARCHITECTURE.md
├── DEPLOYMENT.md
└── README.md
```

### Adding New Features

1. **Add Database Model** (models.py)
2. **Create Migration** (alembic revision)
3. **Add API Route** (routes_*.py)
4. **Implement Logic** (service files)
5. **Write Tests** (tests/)
6. **Update Documentation**

### Code Style

```bash
# Format code
black .

# Lint
flake8 .

# Type checking
mypy .
```

## 📊 Monitoring

### Metrics Endpoints

```bash
# Application health
curl http://localhost:8000/health

# Celery monitoring
http://localhost:5555  # Flower UI

# Database metrics
psql -h localhost -U gi_copilot -c "SELECT * FROM pg_stat_activity;"
```

### Logs

```bash
# API logs
docker-compose logs -f api

# Worker logs
docker-compose logs -f celery_worker

# All logs
docker-compose logs -f
```

## 🔒 Security

### Best Practices
1. **Always use HTTPS** in production
2. **Rotate API keys** regularly
3. **Enable database encryption** at rest
4. **Use secrets management** (AWS Secrets Manager, Vault)
5. **Implement rate limiting**
6. **Regular security audits**
7. **Keep dependencies updated**

### HIPAA Compliance
- All PHI is encrypted at rest and in transit
- Audit logs track all data access
- Automatic session timeouts
- Role-based access control
- Data retention policies

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see LICENSE file.

## 👥 Authors

- Medical AI Team
- Contact: mosaabagrof@gmail.com

## 🙏 Acknowledgments

- MedGemma team at Google
- FastAPI framework
- Celery distributed task queue
- Open source community

---

**Note**: This is an educational tool. All findings and suggestions must be validated by qualified medical professionals. Never use for autonomous diagnostic decisions.
