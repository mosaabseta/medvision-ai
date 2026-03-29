# MedVision AI 🏥

**Real-Time Medical Procedure Assistant powered by Google's MedGemma-4B**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)]
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)]
[![MedGemma](https://img.shields.io/badge/Model-MedGemma--4B-green.svg)]

> 🚀 Real-time AI vision analysis with natural voice interaction for medical procedures

---

## 📺 Demo

* ▶️ Watch 3-Minute Video Demo: https://youtu.be/bB6a30PUKz4

---

## 🎯 What is MedVision AI?

MedVision AI is a real-time medical procedure assistant that combines **Google's MedGemma-4B** for visual analysis with **OpenAI's Realtime API** for natural voice interaction, creating a conversational AI copilot for medical procedures.

**Core Innovation**: Physicians can watch procedures through their endoscope while MedVision AI simultaneously analyzes frames, identifies findings, and answers questions via voice—completely hands-free.

---

## 🌍 Vision

MedVision AI aims to augment—not replace—medical professionals by providing real-time insights, reducing cognitive load, and improving procedural accuracy.

Our goal is to make advanced AI assistance accessible across:

* High-resource hospitals
* Training institutions
* Underserved and remote settings

---

## ✨ Key Features

✅ **Real-time Frame Analysis** - MedGemma-4B processes video at 2–3 FPS
✅ **Hands-Free Voice Interaction** - Natural conversation about findings
✅ **Automatic Documentation** - Timestamped findings with structured export
✅ **Privacy-First Design** - Visual-only analysis, no patient data required
✅ **Production-Ready Architecture** - On-premise capable, secure deployment

---

## 🚀 Quick Start

### Prerequisites

* Python 3.10+
* NVIDIA GPU with 24GB+ VRAM (A10/A100 recommended)
* CUDA 11.8+
* PostgreSQL 14+
* FFmpeg
* OpenAI API key (for voice features)

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

### Tech Stack

* **AI**: MedGemma-4B-IT (Google HAI-DEF)
* **Backend**: Python, FastAPI, SQLAlchemy
* **Frontend**: Vanilla JavaScript, WebRTC
* **Database**: PostgreSQL
* **Voice**: OpenAI Realtime API
* **Video**: FFmpeg
* **Deployment**: GPU servers (Hetzner / RunPod)

---

## 💡 Use Cases

1. **Endoscopy Procedures** – Polyp/lesion detection during colonoscopy and upper GI
2. **Surgical Assistance** – Anatomical landmark identification
3. **Medical Training** – Real-time feedback for residents
4. **Telemedicine** – Remote procedural guidance
5. **Quality Assurance** – Automated documentation and review

---

## 📊 Performance

**Measured on NVIDIA A10 GPU (n=100 frames):**

| Metric                 | Result                          | Status |
| ---------------------- | ------------------------------- | ------ |
| Frame Analysis Latency | 380ms (P50), 480ms (P95)        | ✅      |
| Voice Response Time    | 1.4s (P50), 1.8s (P95)          | ✅      |
| Parse Success Rate     | 94%                             | ✅      |
| Throughput             | 2.6 FPS (live), 8.5 FPS (batch) | ✅      |
| GPU Memory             | 9.1GB (inference)               | ✅      |

---

## 🔒 Privacy & Compliance

### Privacy-First Design

* Processes visual data only
* No patient identifiers required
* No PHI storage
* On-premise deployment supported
* End-to-end encryption (TLS 1.3)

### Medical Disclaimer

> This is an AI-assisted tool for educational and research purposes.
> NOT approved for clinical use.
> All findings must be validated by qualified medical professionals.

---

## ⚙️ Optimization Techniques

* Mixed Precision (bfloat16) → ~42% speedup
* Model caching → eliminates cold starts
* Smart frame sampling → ~30% fewer frames
* Batch processing → up to 8.5x throughput
* Prompt engineering → 94% structured output

---

## 🛠️ Configuration

```bash
OPENAI_API_KEY=your_api_key_here

DATABASE_URL=postgresql://user:password@localhost/medvision

HOST=0.0.0.0
PORT=8000

CUDA_VISIBLE_DEVICES=0
```

---

## 🧪 Testing

```bash
pytest tests/

python benchmarks/run_latency_test.py
python benchmarks/run_parsing_test.py
python benchmarks/run_memory_test.py
```

---

## 🤝 Contributors

We welcome contributions from the community!

### Team

* **Dr. Mosaab Agrof (Seta)** – Developer & AI Engineer (Research Assistant at Kuwait University)
* **Dr. Sami Elamin** – Gastroenterology , Hepatology & Endoscopy MD at Harvard Medical School
* **Prof. Tyler M. Berzin** – Associate Professor of Medicine ,MD, MS, FASGE, FACG at Harvard Medical School - Center For Advanced Endoscopy

---
### How to Contribute

* Fork the repository
* Create a feature branch
* Submit a pull request

You can also contribute by:

* Reporting bugs
* Suggesting features
* Improving documentation
* Adding new medical procedure support

---

## 📄 License

* Open Source: AGPL v3.0
* Commercial use requires a separate license

---

## 📞 Contact

* 📧 [mosaabagrof@gmail.com](mailto:mosaabagrof@gmail.com)
* 💬 GitHub Issues for bugs & feature requests

---

## ⭐ Support

If you find this project useful, consider giving it a star ⭐

---

*Building the future of AI-assisted medicine*
