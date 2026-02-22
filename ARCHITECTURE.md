# GI Copilot - Production System Architecture

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture Design](#architecture-design)
3. [Component Details](#component-details)
4. [Data Flow](#data-flow)
5. [Scalability Strategy](#scalability-strategy)
6. [Security Considerations](#security-considerations)

---

## System Overview

### Core Capabilities
- **Real-time Video Analysis**: Live endoscopy frame processing
- **Recorded Video Processing**: Batch analysis of uploaded videos
- **Context-Aware Chat**: Educational AI assistant with temporal memory
- **Data Export**: Comprehensive bundled downloads

### Technology Stack
- **Backend**: FastAPI (async/await for concurrent processing)
- **AI Engine**: MedGemma (HuggingFace Transformers)
- **Database**: PostgreSQL (relational data) + MinIO/S3 (object storage)
- **Task Queue**: Celery + Redis (async video processing)
- **Caching**: Redis (frame analysis cache)
- **Storage**: MinIO (self-hosted S3-compatible) or AWS S3

---

## Architecture Design

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Layer                          │
│  (Web UI, Mobile App, Desktop Client)                       │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                     API Gateway (FastAPI)                    │
│  - Authentication/Authorization                              │
│  - Rate Limiting                                             │
│  - Request Routing                                           │
└───────┬───────────────────────────────────┬─────────────────┘
        │                                   │
┌───────▼──────────────┐         ┌─────────▼─────────────────┐
│  Real-time Pipeline  │         │  Batch Processing Pipeline │
│                      │         │                            │
│  - Live Frame Capture│         │  - Video Upload Handler    │
│  - Instant Analysis  │         │  - Frame Extraction        │
│  - Voice Integration │         │  - Batch AI Analysis       │
└──────────────────────┘         └────────────────────────────┘
        │                                   │
        └────────────────┬──────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   Core Services Layer                        │
├──────────────────────┬──────────────────┬───────────────────┤
│  AI Engine Service   │  Storage Service │  Chat Service     │
│  - Frame Analysis    │  - Video Storage │  - Conversation   │
│  - Model Management  │  - Frame Cache   │  - Context Memory │
│  - Batch Processing  │  - Export Builder│  - LLM Integration│
└──────────────────────┴──────────────────┴───────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    Data Layer                                │
├──────────────────────┬──────────────────┬───────────────────┤
│  PostgreSQL          │  Redis           │  MinIO/S3         │
│  - Video Metadata    │  - Task Queue    │  - Video Files    │
│  - Frame Analysis    │  - Cache         │  - Frame Images   │
│  - Conversations     │  - Session State │  - Export Bundles │
└──────────────────────┴──────────────────┴───────────────────┘
```

---

## Component Details

### 1. API Gateway (FastAPI)

**Responsibilities:**
- Request routing and load balancing
- Authentication (JWT tokens)
- Rate limiting per user/session
- WebSocket management for real-time features
- CORS handling

**Key Endpoints:**
```
POST   /api/v1/videos/upload          # Upload recorded video
GET    /api/v1/videos/{id}            # Get video metadata
POST   /api/v1/videos/{id}/process    # Start batch processing
GET    /api/v1/videos/{id}/status     # Check processing status
GET    /api/v1/videos/{id}/export     # Download bundle

POST   /api/v1/realtime/session       # Start live session
POST   /api/v1/realtime/frame         # Submit live frame
GET    /api/v1/realtime/analysis      # Get latest analysis

POST   /api/v1/chat/message           # Send chat message
GET    /api/v1/chat/{session_id}      # Get conversation history
```

### 2. Video Processing Pipeline

**Architecture Pattern: Producer-Consumer with Task Queue**

```python
# Workflow:
1. Upload Video → Store in MinIO → Create DB entry
2. Enqueue processing task → Celery worker picks up
3. Extract frames → Batch analyze → Store results
4. Update progress in real-time (WebSocket)
5. Generate export bundle → Notify user
```

**Frame Extraction Strategy:**
- **Intelligent Sampling**: Extract keyframes + uniform intervals
- **Adaptive Rate**: High motion = more frames, static = fewer
- **Target**: 1-3 FPS for most procedures (configurable)

**Memory Management:**
- Process frames in batches of 10-20
- Use generators to avoid loading entire video
- Clear GPU memory between batches
- Stream analysis results to database

### 3. AI Engine Service

**Model Management:**
```python
# Multi-model architecture for scalability
- Primary: MedGemma-4B (current frame analysis)
- Secondary: Lightweight CNN (rapid pre-screening)
- Tertiary: GPT-4/Claude (complex reasoning, chat)
```

**Optimization Techniques:**
- **Model Quantization**: INT8 for inference speedup
- **Batch Inference**: Process multiple frames simultaneously
- **GPU Memory Pooling**: Reuse allocated memory
- **Model Caching**: Keep model in GPU memory (persistent workers)

**Analysis Pipeline:**
```
Frame → Pre-processing → Feature Extraction → 
MedGemma Analysis → Post-processing → Structured Output
```

### 4. Storage Service

**Object Storage (MinIO/S3):**
```
/videos/
  /{user_id}/
    /{video_id}/
      original.mp4
      frames/
        frame_0001.jpg
        frame_0002.jpg
        ...
      exports/
        bundle_{timestamp}.zip
```

**Caching Strategy:**
```python
# Redis Cache Structure
frame:{video_id}:{frame_index} → analysis_json (TTL: 24h)
session:{session_id} → conversation_context (TTL: 1h)
processing:{video_id} → status_json (TTL: 6h)
```

### 5. Chat Service

**Context Management:**
- **Sliding Window**: Keep last 10 exchanges + current frame
- **Summary Injection**: Periodic conversation summarization
- **Frame References**: Link messages to specific timestamps
- **Multi-modal Context**: Combine text + visual analysis

**Integration Points:**
```python
Context = {
    "current_frame": Frame analysis from AI engine,
    "recent_frames": Last 5 frame analyses,
    "conversation_history": Last 10 messages,
    "video_metadata": Procedure type, timestamp, etc.,
    "user_intent": Extracted from conversation
}
```

---

## Data Flow

### Recorded Video Processing Flow

```
┌─────────────┐
│ User Uploads│
│   Video     │
└──────┬──────┘
       │
       ▼
┌──────────────────────┐
│ 1. Store Video       │
│    - MinIO/S3        │
│    - Generate UUID   │
│    - Create DB entry │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ 2. Enqueue Task      │
│    - Celery Task     │
│    - Priority: Normal│
└──────┬───────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│ 3. Frame Extraction Worker           │
│    - FFmpeg extraction                │
│    - Keyframe detection               │
│    - Store frames in S3               │
│    - Progress: 0-30%                  │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│ 4. AI Analysis Worker                │
│    - Batch load frames (10 at a time)│
│    - MedGemma inference               │
│    - Store structured results         │
│    - Cache in Redis                   │
│    - Progress: 30-80%                 │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│ 5. Summary Generation                │
│    - Aggregate findings               │
│    - Generate educational insights    │
│    - Progress: 80-90%                 │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│ 6. Export Bundle Creation            │
│    - Compile all artifacts            │
│    - Create ZIP archive               │
│    - Store in S3                      │
│    - Progress: 90-100%                │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────┐
│ 7. Notify User       │
│    - WebSocket push  │
│    - Email (optional)│
│    - Status: Complete│
└──────────────────────┘
```

### Real-time Analysis Flow

```
Live Video → Frame Capture (3 FPS) → Queue → AI Worker → 
Analysis Result → WebSocket → Client UI + Voice Assistant
```

---

## Scalability Strategy

### Horizontal Scaling

**API Layer:**
- Multiple FastAPI instances behind load balancer
- Session affinity for WebSocket connections
- Auto-scaling based on CPU/memory metrics

**Worker Layer:**
```python
# Celery worker pools
- Video processing workers: 2-4 per node
- AI inference workers: 1 per GPU
- Export workers: 2-4 per node
```

**Database Layer:**
- PostgreSQL read replicas for queries
- Master-slave replication
- Connection pooling (SQLAlchemy)

### Vertical Scaling

**GPU Optimization:**
- Use A10/A100 GPUs for production
- Multi-GPU inference with model parallelism
- Mixed precision (FP16) for 2x speedup

**Memory Management:**
```python
# Per-worker limits
- Max video size: 2 GB
- Frame batch size: 20 frames
- Max concurrent tasks: 3 per worker
```

### Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| Frame analysis latency | < 500ms | p95 |
| Video upload | 100 MB in 10s | Average |
| 1-hour video processing | < 15 min | End-to-end |
| Chat response time | < 2s | p99 |
| Export generation | < 30s | Average |

---

## Security Considerations

### Authentication & Authorization
- JWT tokens with short expiration (15 min)
- Refresh token mechanism
- Role-based access control (RBAC)
- PHI compliance (HIPAA if US-based)

### Data Protection
- **Encryption at rest**: AES-256 for stored videos
- **Encryption in transit**: TLS 1.3 for all API calls
- **Access logging**: Audit trail for all PHI access
- **Data retention**: Configurable purge policies

### Privacy & Compliance
```python
# De-identification pipeline
1. Strip DICOM metadata (if applicable)
2. Remove audio track (PHI risk)
3. Anonymize timestamps
4. Generate random IDs for exports
```

### Rate Limiting
```python
# Per-user limits
- Video uploads: 10 per day
- API calls: 100 per minute
- Export downloads: 5 per hour
```

---

## Monitoring & Observability

### Metrics to Track
- Video processing throughput (videos/hour)
- AI inference latency (ms)
- GPU utilization (%)
- Queue depth (tasks pending)
- Error rates by endpoint

### Logging Strategy
```python
# Structured logging
- Request ID tracing
- User actions
- System events
- Error tracking (Sentry)
```

### Health Checks
```
GET /health/live    # Service is running
GET /health/ready   # Service can handle requests
GET /health/db      # Database connectivity
GET /health/storage # S3/MinIO connectivity
GET /health/gpu     # GPU availability
```

---

## Cost Optimization

### Compute Costs
- **Spot instances** for batch workers (60% savings)
- **Auto-scaling** to match demand
- **Model caching** to reduce cold starts

### Storage Costs
```python
# Lifecycle policies
- Raw videos: 30-day retention
- Frames: Delete after export generation
- Exports: 90-day retention
- Archives: Move to Glacier after 180 days
```

### AI Inference Costs
- Use smaller models for pre-screening
- Batch inference for efficiency
- Cache repeated frame analyses

---

## Future Enhancements

1. **Multi-tenancy**: Separate instances per hospital/clinic
2. **Federated Learning**: Train models without centralizing data
3. **Real-time Collaboration**: Multiple viewers per procedure
4. **Mobile Apps**: iOS/Android native clients
5. **Advanced Analytics**: Trend detection across procedures
6. **Integration**: HL7/FHIR for EHR systems

---

## Deployment Architecture

```yaml
# Kubernetes Deployment Example
Services:
  - api-gateway (3 replicas)
  - celery-worker-video (2 replicas)
  - celery-worker-ai (2 replicas, GPU nodes)
  - celery-beat (1 replica, cron jobs)
  - postgresql (StatefulSet)
  - redis (StatefulSet)
  - minio (StatefulSet)

Auto-scaling:
  - API: CPU > 70%
  - Workers: Queue depth > 10
  
Resource Limits:
  - API: 2 CPU, 4 GB RAM
  - Video Worker: 4 CPU, 8 GB RAM
  - AI Worker: 8 CPU, 32 GB RAM, 1 GPU
```

---

## Disaster Recovery

### Backup Strategy
- **Database**: Daily automated backups, 30-day retention
- **Videos**: Replicated across 3 availability zones
- **Exports**: Backed up to separate S3 bucket

### Recovery Procedures
```
RPO (Recovery Point Objective): 1 hour
RTO (Recovery Time Objective): 4 hours
```

---

*End of Architecture Document*
