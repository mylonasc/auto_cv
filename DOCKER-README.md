# Docker Setup for auto_cv

## Quick Start

The easiest way to run the entire application is with Docker Compose:

```bash
# Start all services
docker-compose up -d

# Or use the quick start script
./start.sh
```

This will start:
- **Backend API** at http://localhost:8005
- **Frontend** at http://localhost:5173
- **Ollama** (optional) at http://localhost:11434

## Services

### Backend
- FastAPI server with CV processing endpoints
- Runs on port 8005
- Requires LaTeX packages for PDF generation
- Optional: Google Gemini API key for cloud LLM

### Frontend  
- React + TypeScript application
- Runs on port 5173 (mapped to port 80 in container)
- Communicates with backend via API

### Ollama (Optional)
- Local LLM service
- Enable containerized Ollama with: `docker-compose --profile with-ollama up -d`
- Pull models: `docker exec auto-cv-ollama ollama pull llama3`

#### Using Host Ollama Server
If you already have Ollama running on your host machine and want the Docker containers to use it:

1.  **Configure Ollama to listen on all interfaces**: By default, Ollama only listens on `127.0.0.1`.
    *   **On Linux (systemd)**:
        *   Run `sudo systemctl edit ollama.service`
        *   Add the following lines:
            ```ini
            [Service]
            Environment="OLLAMA_HOST=0.0.0.0:11434"
            ```
        *   Reload and restart:
            ```bash
            sudo systemctl daemon-reload
            sudo systemctl restart ollama
            ```
2.  **Verify Host Gateway**: The `docker-compose.yml` is configured to reach the host via `http://host.docker.internal:11434`.

## Environment Variables

Create a `.env` file (copy from `.env.example`):
```
GEMINI_API_KEY=your_api_key_here
```

## Volumes

The docker-compose setup uses volumes for:
- Backend code (live reload during development)
- Source code
- Config files
- CV data

## Building Individually

### Backend only:
```bash
docker build -f Dockerfile.backend -t auto-cv-backend .
docker run -p 8005:8005 auto-cv-backend
```

### Frontend only:
```bash
docker build -f Dockerfile.frontend -t auto-cv-frontend .
docker run -p 80:80 auto-cv-frontend
```

## Troubleshooting

### View logs:
```bash
docker-compose logs -f [service_name]
```

### Rebuild after changes:
```bash
docker-compose up -d --build
```

### Clean up:
```bash
docker-compose down -v  # Removes volumes too
```
