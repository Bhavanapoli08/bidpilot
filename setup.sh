#!/bin/bash

# BidPilot AI Setup Script
set -e

echo "================================"
echo "BidPilot AI - Development Setup"
echo "================================"
echo ""

# Check prerequisites
echo "Checking prerequisites..."
command -v docker &> /dev/null || { echo "❌ Docker not found. Install from https://www.docker.com"; exit 1; }
command -v docker-compose &> /dev/null || { echo "❌ Docker Compose not found"; exit 1; }

echo "✓ Docker & Docker Compose found"
echo ""

# Create .env if doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    echo "⚠ Edit .env with your API keys (OpenAI, AWS, Razorpay)"
fi

echo ""
echo "Building Docker images..."
docker-compose build

echo ""
echo "Starting services..."
docker-compose up -d

echo ""
echo "Waiting for services to be ready..."
sleep 10

echo ""
echo "================================"
echo "✓ Setup Complete!"
echo "================================"
echo ""
echo "Services running:"
echo "  Frontend:   http://localhost:3000"
echo "  Backend:    http://localhost:8000"
echo "  API Docs:   http://localhost:8000/docs"
echo "  Flower:     http://localhost:5555"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your credentials"
echo "  2. Visit http://localhost:3000"
echo "  3. Sign up with your email"
echo ""
echo "Useful commands:"
echo "  make logs          - View logs"
echo "  make migrate       - Run database migrations"
echo "  make test          - Run tests"
echo "  make down          - Stop all services"
echo ""
