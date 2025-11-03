# AI Service Chatbot

AI-powered RAG (Retrieval-Augmented Generation) service for textbooks using FastAPI, LangChain, and FAISS.

## Features

- 📚 PDF document ingestion with text extraction and chunking
- 🔍 Vector-based semantic search using FAISS
- 🤖 RAG (Retrieval-Augmented Generation) query endpoint
- 🚀 FastAPI REST API
- 📊 Health check endpoint

## Prerequisites

- Python 3.8+
- pip
- Tesseract OCR (for OCR functionality)

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd ai_service_chatbot/app
```

### 2. Create virtual environment

**Windows:**

```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux/Mac:**

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Tesseract OCR

**Windows:**

- Download from: https://github.com/UB-Mannheim/tesseract/wiki
- Add to PATH during installation

**Linux:**

```bash
sudo apt-get install tesseract-ocr
```

**Mac:**

```bash
brew install tesseract
```

### 5. Configure environment variables

Create a `.env` file in the `app` directory:

```bash
# OpenAI Configuration (if using OpenAI embeddings)
OPENAI_API_KEY=your_openai_api_key_here

# Other optional configurations
LOG_LEVEL=INFO
```

## Running the Application

### Method 1: Using the shell script

**Linux/Mac:**

```bash
chmod +x run.sh
./run.sh
```

**Windows:**

```powershell
.\run.ps1
```

### Method 2: Using uvicorn directly

**Windows:**

```powershell
# Activate virtual environment
.venv\Scripts\activate

# Set PYTHONPATH
$env:PYTHONPATH = $PWD

# Run the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Linux/Mac:**

```bash
# Activate virtual environment
source .venv/bin/activate

# Set PYTHONPATH
export PYTHONPATH=$(pwd)

# Run the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Method 3: Using Python module

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## API Endpoints

### Health Check

```bash
GET http://localhost:8000/
```

Response:

```json
{
  "status": "ok",
  "message": "AI Service Chatbot is running 🚀"
}
```

### Ingestion Endpoint

```bash
POST http://localhost:8000/admin/ingest
Content-Type: application/json

{
  "pdf_url": "https://example.com/book.pdf",
  "book_name": "Mathematics Grade 10",
  "grade": 10
}
```

### RAG Query Endpoint

```bash
POST http://localhost:8000/rag/query
Content-Type: application/json

{
  "lesson_id": "lesson_123",
  "teacher_notes": "Explain the concept of derivatives",
  "k": 5
}
```

## API Documentation

Once the server is running, visit:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
app/
├── api/           # API endpoints
│   ├── ingest.py  # Document ingestion API
│   └── rag.py     # RAG query API
├── core/          # Core configuration
│   ├── config.py  # Configuration settings
│   └── logger.py  # Logging setup
├── data/          # Data storage
│   ├── cache/     # Cache directory
│   └── faiss/     # FAISS indices
├── models/        # Pydantic models
│   ├── ingest_model.py
│   └── rag_model.py
├── services/      # Business logic
│   ├── chunker.py     # Text chunking
│   ├── embedder.py    # Text embedding
│   ├── indexer.py     # FAISS indexing
│   ├── parser.py      # PDF parsing
│   ├── rag_engine.py  # RAG query engine
│   └── utils.py       # Utility functions
├── main.py        # FastAPI application
├── requirements.txt
├── run.sh         # Linux/Mac startup script
├── run.ps1        # Windows PowerShell startup script
├── .env.example   # Example environment variables
└── .gitignore     # Git ignore rules
```

## Troubleshooting

### Issue: Module not found error

**Solution:** Make sure you're in the `app` directory and PYTHONPATH is set correctly.

### Issue: Tesseract not found

**Solution:** Install Tesseract OCR and add it to your system PATH.

### Issue: Port 8000 already in use

**Solution:** Use a different port:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

## License

[Add your license here]

## Contact

[Add your contact information here]
