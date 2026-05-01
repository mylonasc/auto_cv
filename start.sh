#!/bin/bash

# Quick start script for auto_cv project

echo "🚀 Starting auto_cv application..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Creating from .env.example..."
    cp .env.example .env
    echo "✏️  Edit .env file to add your GEMINI_API_KEY if needed."
fi

# Start services
echo "📦 Starting services with docker-compose..."
docker-compose up -d

echo ""
echo "✅ Services started!"
echo ""
echo "📍 Access points:"
echo "   Frontend: http://localhost:5173"
echo "   Backend API: http://localhost:8005"
echo "   Ollama (if enabled): http://localhost:11434"
echo ""
echo "📋 Useful commands:"
echo "   View logs: docker-compose logs -f"
echo "   Stop services: docker-compose down"
echo "   Restart: docker-compose restart"
echo ""
