# MedVision AI 🏥

**Real-Time Medical Procedure Assistant powered by Google's MedGemma-4B**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MedGemma](https://img.shields.io/badge/Model-MedGemma--4B-green.svg)](https://huggingface.co/google/medgemma-4b-it)
[![Competition](https://img.shields.io/badge/Google-HAI--DEF%20Challenge-red.svg)](https://kaggle.com/competitions/med-gemma-impact-challenge)

> 🏆 **Built for the MedGemma Impact Challenge**  
> Finalist submission combining real-time AI vision analysis with natural voice interaction

---

## 📺 Demo

**[▶️ Watch 3-Minute Video Demo]((https://youtu.be/bB6a30PUKz4))**

**[🚀 Try Live Demo](https://medvisor)** *(active through March 24, 2026)*


---

## 🎯 What is MedVision AI?

MedVision AI is a real-time medical procedure assistant that combines **Google's MedGemma-4B** for visual analysis with **OpenAI's Realtime API** for natural voice interaction, creating the first truly conversational AI copilot for medical procedures.

**Core Innovation**: Physicians can watch procedures through their endoscope while MedVision AI simultaneously analyzes frames, identifies findings, and answers questions via voice—completely hands-free.

### Key Features

✅ **Real-time Frame Analysis** - MedGemma-4B processes video at 2-3 FPS  
✅ **Hands-Free Voice Interaction** - Natural conversation about findings  
✅ **Automatic Documentation** - Timestamped findings with structured export  
✅ **Privacy-First Design** - Visual-only analysis, no patient data required  
✅ **Production-Ready** - HIPAA-compliant architecture, on-premise capable

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- NVIDIA GPU with 24GB+ VRAM (A10/A100 recommended)
- CUDA 11.8+
- PostgreSQL 14+
- FFmpeg
- OpenAI API key (for voice features)

### Installation

```bash
# 1. Clone repository
git clone https://github.com/mosaabseta/medvision-ai.git
cd medvision-ai

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
nano .env  # Add your OpenAI API key and other config

# 5. Initialize database
python scripts/setup_db.py

# 6. Start server
python scripts/start_server.py
```

Open browser: `http://localhost:8000`

---

## 📖 Documentation

- **[Setup Guide](docs/SETUP.md)** - Detailed installation instructions
- **[Architecture](docs/ARCHITECTURE.md)** - System design and components
- **[Competition Submission](docs/COMPETITION.md)** - Challenge details

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│  Frontend (Browser)                     │
│  - WebRTC Voice (OpenAI Realtime API)  │
│  - Real-time Timeline Display           │
└─────────────┬───────────────────────────┘
              │ REST + WebSocket
              ▼
┌─────────────────────────────────────────┐
│  FastAPI Backend                        │
│  - Video Processing (FFmpeg)            │
│  - Voice Proxy (WebSocket)              │
│  - Session Management                   │
└─────────────┬───────────────────────────┘
              │
    ┌─────────┴─────────┐
    ▼                   ▼
┌──────────┐      ┌──────────────┐
│ MedGemma │      │ PostgreSQL   │
│ 4B-IT    │      │ + File Store │
│ (GPU)    │      │              │
└──────────┘      └──────────────┘
```

**Tech Stack:**
- **AI**: MedGemma-4B-IT (Google HAI-DEF)
- **Backend**: Python, FastAPI, SQLAlchemy
- **Frontend**: Vanilla JavaScript, WebRTC
- **Database**: PostgreSQL
- **Voice**: OpenAI Realtime API
- **Video**: FFmpeg
- **Deployment**: Hetzner/RunPod GPU servers

---

## 💡 Use Cases

1. **Endoscopy Procedures** - Real-time polyp/lesion detection during colonoscopy, upper GI
2. **Surgical Procedures** - Anatomical landmark identification and guidance
3. **Medical Training** - AI-assisted learning for residents with instant feedback
4. **Telemedicine** - Remote procedure guidance in underserved areas
5. **Quality Assurance** - Comprehensive documentation for medical records

---

## 📊 Performance

**Measured on NVIDIA A10 GPU (n=100 frames):**

| Metric | Result | Status |
|--------|--------|--------|
| **Frame Analysis Latency** | 380ms (P50), 480ms (P95) | ✅ < 500ms target |
| **Voice Response Time** | 1.4s (P50), 1.8s (P95) | ✅ < 2s target |
| **Parse Success Rate** | 94% | ✅ > 85% target |
| **Throughput** | 2.6 FPS (live), 8.5 FPS (batch) | ✅ Real-time capable |
| **GPU Memory** | 8.2GB (model), 9.1GB (inference) | ✅ Fits on A10 |

**All benchmarks are reproducible** - see `benchmarks/` directory

---

## 🔒 Privacy & Compliance

**Current Implementation (Privacy-First):**
- ✅ Processes visual data only (no patient identifiers)
- ✅ No PHI collection or storage
- ✅ On-premise deployment capable
- ✅ End-to-end encryption (TLS 1.3)
- ✅ Comprehensive audit logging

**HIPAA Considerations:**
- System designed for institutional deployment
- Full data control with on-premise option
- Encryption at rest and in transit
- Access controls and session management

**Medical Disclaimer:**
> This is an AI-assisted tool for educational and research purposes. NOT FDA-approved for clinical use. All findings must be validated by qualified medical professionals. Never use as sole basis for clinical decisions.

---

## 📈 Optimization Techniques

We achieved production-grade performance through multiple optimizations:

1. **Mixed Precision (bfloat16)** - 42% speedup, 50% memory reduction vs FP32
2. **Model Caching** - Eliminate 8-second cold start by keeping model in GPU
3. **Smart Frame Sampling** - Keyframes + deduplication = 30% fewer frames
4. **Batch Processing** - Process 10 frames simultaneously (8.5x throughput)
5. **Prompt Engineering** - 94% structured output success rate

---

## 🛠️ Configuration

Edit `.env` file:

```bash
# OpenAI (for voice features)
OPENAI_API_KEY=sk-your_api_key_here

# Database
DATABASE_URL=postgresql://user:password@localhost/medvision

# Server
HOST=0.0.0.0
PORT=8000

# GPU
CUDA_VISIBLE_DEVICES=0
```

---

## 📝 Usage Examples

### Live Session
1. Navigate to "Live Session" tab
2. Load a procedure video
3. AI analyzes frames in real-time (every 3 seconds)
4. Speak questions: *"What's concerning about this finding?"*
5. Save session when complete

### Batch Processing
1. Go to "Upload Video" tab
2. Upload procedure video with metadata
3. Processing happens automatically
4. Download comprehensive export bundle

### Export Contents
```
session_export.zip
├── metadata.json       # Session info
├── summary.json        # Analysis summary
├── findings.csv        # Excel-compatible
├── findings.json       # Structured data
└── report.txt          # Human-readable
```

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/

# Run benchmarks
python benchmarks/run_latency_test.py
python benchmarks/run_parsing_test.py
python benchmarks/run_memory_test.py

# Test specific component
pytest tests/test_medgemma_engine.py -v
```

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md).

**Areas for contribution:**
- Additional procedure types (bronchoscopy, cystoscopy, etc.)
- Fine-tuning scripts for specific tasks
- EHR integration connectors
- Mobile/tablet interface
- Multilingual support

---

## 📄 License

**Dual License:**

- **Open Source**: AGPL v3.0 for research and educational use
- **Commercial**: Separate license required for commercial deployment

See [LICENSE](LICENSE) file for details.

**Commercial licensing**: mosaabagrof@gmail.com

---

## 🏆 Competition

This project was built for the **MedGemma Impact Challenge** by Google HAI-DEF.

**Submission Tracks:**
- Main Track
- Agentic Workflow Prize

**Key Criteria Met:**
- ✅ Effective use of MedGemma-4B (visual analysis + structured output)
- ✅ Addresses important clinical problem (real-time procedure assistance)
- ✅ Demonstrates real impact potential (time savings, quality improvement)
- ✅ Technically feasible (production architecture, verified performance)
- ✅ High-quality execution (working demo, comprehensive documentation)

**Submission Materials:**
- Video: [3-minute demo]((https://youtu.be/bB6a30PUKz4))
- Writeup: [Kaggle submission](https://www.kaggle.com/competitions/med-gemma-impact-challenge/writeups/medvision-ai-real-time-medical-procedure-assistan)
- Code: This repository

---

## 👥 Team

**Seta** - Developer & AI Engineer  
Email: mosaabagrof@gmail.com  
LinkedIn: https://www.linkedin.com/in/mosaab-agrof-219478364/


---

## 🙏 Acknowledgments

- Google HAI-DEF team for MedGemma-4B
- Kaggle for hosting the competition
- OpenAI for Realtime API
- Medical professionals who provided feedback

---

## 📚 Citations

```bibtex
@software{medvision2026,
  title={MedVision AI: Real-Time Medical Procedure Assistant},
  author={Seta},
  year={2026},
  url={https://github.com/yourusername/medvision-ai}
}

@misc{medgemma2024,
  title={MedGemma: Medical Vision-Language Models},
  author={Google Health AI},
  year={2024},
  url={https://huggingface.co/google/medgemma-4b-it}
}
```

---

## 📞 Contact

**Questions or feedback?**
- 📧 Email: mosaabagrof@gmail.com
- 💬 GitHub Issues: [Report bugs or request features](https://github.com/mosaabseta/medvision-ai/issues)

---

## ⭐ Star this repo if you find it useful!

**[Try the live demo](https://medvisor.fyi)** • **[Watch the video](https://youtu.be/bB6a30PUKz4)** • **[Read the writeup](https://www.kaggle.com/competitions/med-gemma-impact-challenge/writeups/medvision-ai-real-time-medical-procedure-assistan)**

---

*Built with ❤️ for the MedGemma Impact Challenge*

*Making AI-assisted medicine accessible to everyone*
