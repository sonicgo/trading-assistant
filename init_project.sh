#!/bin/bash

# Trading Assistant - Phase 0 Bootstrap Script
# Creates directory structure and initial configuration files.

echo "🚀 Initializing Trading Assistant Project..."

# 1. Create Directory Structure
mkdir -p backend/app/api
mkdir -p backend/app/core
mkdir -p backend/app/domain
mkdir -p backend/app/worker
mkdir -p database
mkdir -p frontend/src/app
mkdir -p frontend/src/components
mkdir -p frontend/src/lib

echo "✅ Directories created."

# 2. Create .env file (Secrets)
cat > .env <<EOF
# Database
POSTGRES_USER=ta_app
POSTGRES_PASSWORD=ta_secret
POSTGRES_DB=trading_assistant
DATABASE_URL=postgresql://ta_app:ta_secret@db:5432/trading_assistant

# Security
SECRET_KEY=dev_secret_key_change_in_prod

# External APIs (Placeholders)
OPENAI_API_KEY=sk-placeholder
MARKET_DATA_KEY=placeholder

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
EOF
echo "✅ .env created."

# 3. Create docker-compose.yml
cat > docker-compose.yml <<EOF
version: '3.8'

services:
  db:
    image: postgres:16-alpine
    restart: always
    environment:
      POSTGRES_USER: \${POSTGRES_USER}
      POSTGRES_PASSWORD: \${POSTGRES_PASSWORD}
      POSTGRES_DB: \${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432" # Exposed for local tool access (VS Code SQLTools)
    networks:
      - ta_net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ta_app -d trading_assistant"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: always
    ports:
      - "6379:6379"
    networks:
      - ta_net

  api:
    build: ./backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - ./backend:/app
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    networks:
      - ta_net

  worker:
    build: ./backend
    command: python -m app.worker.runner
    volumes:
      - ./backend:/app
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    networks:
      - ta_net

  # UI is usually run locally via 'npm run dev' for better DX, 
  # but this container is for full integration testing.
  ui:
    build: ./frontend
    ports:
      - "3000:3000"
    env_file: .env
    depends_on:
      - api
    networks:
      - ta_net

volumes:
  postgres_data:

networks:
  ta_net:
    driver: bridge
EOF
echo "✅ docker-compose.yml created."

# 4. Create Database Schema (The PDM v2)
# (Copying the approved schema_v2.sql content here)
cat > database/init.sql <<EOF
-- Trading Assistant Initial Schema (PDM v2)
-- All timestamps UTC, UUIDv7 keys, JSONB for payloads.

CREATE SCHEMA IF NOT EXISTS ta;

-- Users
CREATE TABLE IF NOT EXISTS ta.users (
  user_id uuid PRIMARY KEY,
  email text NOT NULL UNIQUE,
  is_enabled boolean DEFAULT true,
  created_at timestamptz DEFAULT now()
);

-- Portfolios
CREATE TABLE IF NOT EXISTS ta.portfolios (
  portfolio_id uuid PRIMARY KEY,
  owner_user_id uuid REFERENCES ta.users(user_id),
  name text NOT NULL,
  base_currency char(3) DEFAULT 'GBP',
  created_at timestamptz DEFAULT now()
);

-- (Placeholder: Full schema_v2.sql should be pasted here in production)
-- For Phase 0, we just ensure the DB starts.
EOF
echo "✅ database/init.sql created."

# 5. Backend Setup (FastAPI)
cat > backend/requirements.txt <<EOF
fastapi==0.109.0
uvicorn[standard]==0.27.0
sqlalchemy==2.0.25
alembic==1.13.1
psycopg2-binary==2.9.9
pydantic==2.6.0
pydantic-settings==2.1.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
redis==5.0.1
apscheduler==3.10.4
requests==2.31.0
httpx==0.26.0
EOF

cat > backend/Dockerfile <<EOF
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (needed for psycopg2 build sometimes)
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default command (overridden in docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

cat > backend/app/main.py <<EOF
from fastapi import FastAPI

app = FastAPI(title="Trading Assistant API")

@app.get("/health")
def health_check():
    return {"status": "ok", "phase": "0"}
EOF
echo "✅ Backend scaffolded."

# 6. Frontend Setup (Next.js)
# We create a minimal package.json so 'npm install' works immediately.
cat > frontend/package.json <<EOF
{
  "name": "trading-assistant-ui",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "14.1.0",
    "react": "^18",
    "react-dom": "^18"
  }
}
EOF

cat > frontend/Dockerfile <<EOF
FROM node:20-alpine
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build
CMD ["npm", "start"]
EOF
echo "✅ Frontend scaffolded."

echo "🚀 Phase 0 Bootstrap Complete!"
echo "Next steps:"
echo "1. Run 'docker-compose up -d db redis' to start infrastructure."
echo "2. Open backend/ folder in terminal and run 'pip install -r requirements.txt' for local dev."
echo "3. Open frontend/ folder and run 'npm install' then 'npm run dev'."