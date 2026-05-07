# auto_cv

The `auto_cv` project is a LLM ("GenAI")-enabled CV customizer.

Given a job posting and a CV, the system creates a rendered file that
contains the parts of the experience of the CV candidate that are the most relevant and aligned with the provided posting.

The system architecture diagram is as follows:

![high level system arhc](assets/images/auto_cv_v0-1.png)

## Quick Start with Docker Compose

The easiest way to run the entire application (frontend + backend) is using Docker Compose:

### Prerequisites
- Docker and Docker Compose installed
- (Optional) Google Gemini API key for cloud LLM support

### Starting the Application

1. **Clone the repository** (if not already done):
   ```bash
   git clone <repository-url>
   cd auto_cv
   ```

2. **Set up environment variables** (optional):
   Create a `.env` file in the root directory:
   ```bash
   GEMINI_API_KEY=your_api_key_here
   ```

3. **Start all services**:
   ```bash
   docker-compose up -d
   ```
   This will start:
   - Backend API at http://localhost:8005
   - Frontend at http://localhost:5173
   - (Optional) Ollama service at http://localhost:11434 (use `--profile with-ollama` flag)

4. **View logs**:
   ```bash
   docker-compose logs -f
   ```

5. **Stop all services**:
   ```bash
   docker-compose down
   ```

### Running with Ollama (Local LLM)

To enable local LLM support with Ollama:
```bash
docker-compose --profile with-ollama up -d
```

Then pull a model:
```bash
docker exec auto-cv-ollama ollama pull llama3
```

**Note:** If you want to use an Ollama server already running on your host machine, please refer to [DOCKER-README.md](DOCKER-README.md) for configuration instructions.

## Manual Setup (Without Docker)

### Backend Setup

1. **Navigate to the backend directory**:
   ```bash
   cd server_application/backend
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r ../../requirements.txt
   ```

4. **Set environment variables** (optional):
   ```bash
   export CV_CUSTOMIZER_ROOT=/home/charilaos/Workspace/auto_cv
   export GEMINI_API_KEY=your_api_key_here
   ```

5. **Start the backend server**:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8005
   ```

   The backend API will be available at http://localhost:8005

### Frontend Setup

1. **Navigate to the frontend directory**:
   ```bash
   cd frontend/auto-cv-customizer
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Start the development server**:
   ```bash
   npm run dev
   ```

   The frontend will be available at http://localhost:5173

### Building for Production

```bash
cd frontend/auto-cv-customizer
npm run build
```

The built files will be in the `dist/` directory.

## Enable Gemini

For getting a Gemini API key one needs to:
1. Create a GCP project (if it does not exist already) [console.google.com](console.google.com)
2. Create an API key [here](https://aistudio.google.com/app/apikey)

You can set the API key via environment variable (`GEMINI_API_KEY`) or via config file at `/home/charilaos/secrets/gemini_api_key.txt`.

## Ollama Context Window

Some of the authoring tasks (e.g., personal statement or cover letter), may benefit from having a very large context window.
This is mainly an issue for local models with ollama.
Ollama by default has only ~2k context window, which needs to be changed in order to allow for lengthier inputs.

You can inspect the actual context window of the running ollama server by running:
```
ps aux | grep ollama  # check the --ctx-size flag
```

To change, you need to create a "new" model with increased context:
```
ollama run llama3
>>> /set parameter num_ctx 4096
>>> /save llama3-4k
>>> /bye
```

Or by defining and setting a new model file.

## Running with OpenTelemetry Tracing

It may be helpful to use OpenTelemetry to get statistics about the runtimes, the errors, and intermediate outputs from the chains run.
There is an automatically instrumented script at `tools/autocv-otel.py` you can use for that.

Install the OpenTelemetry dependencies:
```bash
pip install -r requirements-otel.txt
```

Then run with:
```bash
python tools/autocv-otel.py
```

## Running the CLI Pipeline Script

To run the script-based CV generation flow directly:

```bash
python tools/autocv.py
```

Full argument example:

```bash
python tools/autocv.py \
  --candidate-json data/cv_section_data/charilaos_mylonas/master.json \
  --job-posting job_postings_text/Google_GNNs_Apr30-2026.txt \
  --candidate-id charilaos_mylonas \
  --candidate-name "Charilaos Mylonas" \
  --company-name Google \
  --analysis-provider google \
  --analysis-model gemini-3.1-pro-preview \
  --authoring-provider google \
  --authoring-model gemini-3.1-pro-preview \
  --cover-letter-provider google \
  --cover-letter-model gemini-3.1-pro-preview \
  --max-section-items-keep 5 \
  --min-relevance-score-keep 7 \
  --min-section-items-keep 1
```

Fast local preset (Ollama):

```bash
python tools/autocv.py \
  --candidate-json data/cv_section_data/charilaos_mylonas/master.json \
  --job-posting job_postings_text/Google_GNNs_Apr30-2026.txt \
  --analysis-provider ollama \
  --analysis-model llama3.1:latest \
  --authoring-provider ollama \
  --authoring-model llama3.1:latest \
  --cover-letter-provider ollama \
  --cover-letter-model llama3.1:latest
```

High-quality cloud preset (Google):

```bash
python tools/autocv.py \
  --candidate-json data/cv_section_data/charilaos_mylonas/master.json \
  --job-posting job_postings_text/Google_GNNs_Apr30-2026.txt \
  --analysis-provider google \
  --analysis-model gemini-3.1-pro-preview \
  --authoring-provider google \
  --authoring-model gemini-3.1-pro-preview \
  --cover-letter-provider google \
  --cover-letter-model gemini-3.1-pro-preview
```

Select template 2 from registry:

```bash
python tools/autocv.py \
  --candidate-json data/cv_section_data/charilaos_mylonas/master.json \
  --job-posting job_postings_text/Meta_151125.txt \
  --cv-template-id template2
```

Template registry is stored in `config/templates.json`.

## API Endpoints

### Backend API (main.py)
The backend exposes a job-based async API:
- `POST /v1/cv-jobs/` - Create a new CV processing job
- `GET /v1/cv-jobs/{jobId}` - Check job status
- `GET /v1/cv-jobs/{jobId}/result` - Get processing results
- `POST /v1/cv-jobs/{jobId}/cancel` - Cancel a job

Additional endpoints:
- `GET/PUT /v1/config/` - backend config
- `GET /v1/models/available` - model availability
- `GET/PUT /v1/cv-data/{candidate}` and versioned variants under `/v1/cv-data/{candidate}/versions`

## System Dependencies

For PDF rendering, the following LaTeX packages are needed:
```bash
sudo apt-get install texlive latex-xelatex
# Then install additional packages:
tlmgr install fontawesome academicons
```

Or use the provided install script:
```bash
./system_installs.sh
```

## Project Structure

```
auto_cv/
├── server_application/backend/  # FastAPI backend
├── frontend/auto-cv-customizer/ # React frontend
├── src/                         # Core CV processing logic
├── data/                        # Runtime data (cv_section_data, artifacts, cache, jobs)
├── tools/                       # CLI/script workflows (autocv, otel)
├── research/                    # Notebooks and exploratory analyses
├── config/                      # Configuration files
├── docker-compose.yml           # Docker Compose setup
├── Dockerfile.backend           # Backend Dockerfile
├── Dockerfile.frontend          # Frontend Dockerfile
└── requirements.txt             # Python dependencies
```
