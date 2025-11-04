# AI Service Chatbot

AI-powered RAG (Retrieval-Augmented Generation) service for textbooks using FastAPI, LangChain, and FAISS.

## Features

- 📚 PDF document ingestion with text extraction and chunking
- 🎯 Automatic chapter and lesson detection from textbook structure
- 🔍 Vector-based semantic search using FAISS
- 🤖 RAG (Retrieval-Augmented Generation) query endpoint with strict grounding
- 📊 Confidence threshold filtering to prevent hallucinations
- 🚀 FastAPI REST API
- 📊 Health check endpoint
- 🗂️ Book management: list, ingest, and delete documents

## Prerequisites

- Python 3.8+
- pip
- Tesseract OCR (for OCR functionality)
- Poppler (for PDF processing)

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd ai_service_chatbot
```

### 2. Create virtual environment

**Windows:**

```bash
python -m venv app/.venv
app\.venv\Scripts\activate
```

**Linux/Mac:**

```bash
python -m venv app/.venv
source app/.venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r app/requirements.txt
```

### 4. Install Tesseract OCR

**Windows:**

1. Download Tesseract OCR from: https://github.com/UB-Mannheim/tesseract/wiki
   - Choose the setup file, e.g., `Tesseract-OCR-Setup-5.3.3.20231005.exe`
2. During installation:
   - ✅ **Important:** Tick "Add Tesseract to the system PATH for current user"
3. After installation, Tesseract will be at: `C:\Program Files\Tesseract-OCR\tesseract.exe`
4. Verify installation:
   ```powershell
   tesseract --version
   ```
   You should see:
   ```
   tesseract v5.x.x
    leptonica-...
    libjpeg ...
   ```
5. Install Vietnamese language data:
   - Download from: https://github.com/tesseract-ocr/tessdata/blob/main/vie.traineddata
   - Or fast version: https://github.com/tesseract-ocr/tessdata_fast/blob/main/vie.traineddata
   - Copy `vie.traineddata` to: `C:\Program Files\Tesseract-OCR\tessdata\`
   - Verify: `tesseract -l vie --list-langs` (should include `vie`)

**Linux:**

```bash
sudo apt-get install tesseract-ocr
sudo apt-get install libtesseract-dev
sudo apt-get install tesseract-ocr-vie  # Vietnamese language pack
```

**Mac:**

```bash
brew install tesseract
brew install tesseract-lang  # Includes Vietnamese
```

### 5. Install Poppler (for PDF processing)

**Windows:**

1. Download Poppler for Windows from: https://github.com/oschwartz10612/poppler-windows/releases/
2. Extract to a folder, e.g., `C:\poppler`
3. Add `C:\poppler\Library\bin` to your system PATH:
   - Open Start Menu → Search "Edit environment variables"
   - Environment Variables → System variables → Path → Edit → New
   - Add: `C:\poppler\Library\bin`
   - OK all dialogs
4. Restart terminal and verify:
   ```powershell
   where pdfinfo
   # Should show: C:\poppler\Library\bin\pdfinfo.exe
   ```

**Linux:**

```bash
sudo apt-get install poppler-utils
```

**Mac:**

```bash
brew install poppler
```

### 6. Configure environment variables

Create a `.env` file in the `app` directory:

```bash
# OpenAI Configuration (if using OpenAI embeddings)
OPENAI_API_KEY=your_openai_api_key_here

# Other optional configurations
LOG_LEVEL=INFO
```

Example:

```bash
cp app/.env.example app/.env
# Then edit app/.env and add your OpenAI API key
```

## Running the Application

### Method 1: Using the shell script (Recommended)

**Linux/Mac:**

```bash
chmod +x app/run.sh
./app/run.sh
```

**Windows:**

```powershell
.\app\run.ps1
```

> Note: The scripts automatically navigate to the project root directory.

### Method 2: Using uvicorn directly

**Windows (from project root):**

```powershell
# Activate virtual environment (if not already activated)
.venv\Scripts\activate

# Run the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Windows (from app/ directory):**

```powershell
# Set PYTHONPATH to parent directory so 'app' module can be found
$env:PYTHONPATH = ".."

# Run the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Linux/Mac (from project root):**

```bash
# Activate virtual environment (if not already activated)
source .venv/bin/activate

# Run the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Linux/Mac (from app/ directory):**

```bash
# Set PYTHONPATH to parent directory
export PYTHONPATH=..

# Run the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Method 3: Using Python module

```bash
# Make sure you're in the project root directory
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

### Ingestion Endpoints

**Get all ingested books:**

```bash
GET http://localhost:8000/admin/ingest
```

Response:

```json
{
  "books": {
    "Mathematics Grade 10": {
      "grade": 10,
      "chunks": 1250,
      "pages": [1, 2, 3, ...]
    }
  }
}
```

**Get book structure (chapters/lessons):**

```bash
GET http://localhost:8000/admin/ingest/Mathematics Grade 10/structure
```

Response:

```json
{
  "book_name": "Mathematics Grade 10",
  "structure": {
    "Hàm số": {
      "lessons": {
        "Hàm số bậc nhất": {
          "pages": [5, 6, 7],
          "chunks": 15
        },
        "Hàm số bậc hai": {
          "pages": [8, 9, 10],
          "chunks": 18
        }
      },
      "total_chunks": 33,
      "pages": [5, 6, 7, 8, 9, 10]
    }
  }
}
```

**Ingest a new book:**

```bash
POST http://localhost:8000/admin/ingest
Content-Type: application/json

{
  "pdf_url": "https://example.com/book.pdf",
  "book_name": "Mathematics Grade 10",
  "grade": 10
}
```

**Delete a book:**

```bash
DELETE http://localhost:8000/admin/ingest/Mathematics Grade 10
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
ai_service_chatbot/
├── app/
│   ├── api/           # API endpoints
│   │   ├── ingest.py  # Document ingestion API
│   │   └── rag.py     # RAG query API
│   ├── core/          # Core configuration
│   │   ├── config.py  # Configuration settings
│   │   └── logger.py  # Logging setup
│   ├── data/          # Data storage
│   │   ├── cache/     # Cache directory
│   │   └── faiss/     # FAISS indices
│   ├── models/        # Pydantic models
│   │   ├── ingest_model.py
│   │   └── rag_model.py
│   ├── services/      # Business logic
│   │   ├── chunker.py     # Text chunking
│   │   ├── embedder.py    # Text embedding
│   │   ├── indexer.py     # FAISS indexing
│   │   ├── parser.py      # PDF parsing
│   │   ├── rag_engine.py  # RAG query engine
│   │   └── utils.py       # Utility functions
│   ├── main.py        # FastAPI application
│   ├── requirements.txt
│   ├── run.sh         # Linux/Mac startup script
│   ├── run.ps1        # Windows PowerShell startup script
│   ├── .env.example   # Example environment variables
│   └── .gitignore     # Git ignore rules
├── .gitignore         # Root gitignore
└── README.md          # This file
```

## Troubleshooting

### Issue: Module not found error

**Solution:** Make sure you're in the project root directory and PYTHONPATH is set to the project root.

### Issue: Tesseract not found

**Error message:** `pytesseract.pytesseract.TesseractNotFoundError: tesseract is not installed or it's not in your PATH.`

**Solution:**

1. Install Tesseract OCR and **ensure** you tick "Add Tesseract to the system PATH" during installation
2. Verify installation by running `tesseract --version` in a new terminal
3. If not found, manually add `C:\Program Files\Tesseract-OCR` to your system PATH
4. **Restart your terminal** after adding to PATH

### Issue: Vietnamese language data not found

**Error message:** `Error opening data file ...\tessdata\vie.traineddata` or `Failed loading language 'vie'`

**Solution:**

1. Download `vie.traineddata` from:
   - Standard: https://github.com/tesseract-ocr/tessdata/blob/main/vie.traineddata
   - Fast: https://github.com/tesseract-ocr/tessdata_fast/blob/main/vie.traineddata
2. Copy to: `C:\Program Files\Tesseract-OCR\tessdata\`
3. (Optional) Set environment variable `TESSDATA_PREFIX=C:\Program Files\Tesseract-OCR\tessdata`
4. Verify: `tesseract -l vie --list-langs`

### Issue: Poppler not found ("Is poppler installed and in PATH?")

**Solution:** Install Poppler and add to PATH. See section 5 in Installation.

### Issue: Port 8000 already in use

**Solution:** Use a different port:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

## License

© 2025 Pham Dang Khoi. All rights reserved.

## Contact

**Pham Dang Khoi**  
Email: dangkhoipham80@gmail.com  
Phone: +84 795 335 577
