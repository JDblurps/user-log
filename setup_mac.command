#!/bin/bash

set -e

cd "$(dirname "$0")"

echo "Setting up SimpleChat on your Mac..."

if ! command -v python3 >/dev/null 2>&1; then
    echo "Install Python 3 first:"
    echo "https://www.python.org/downloads/macos/"
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "Install Docker Desktop first:"
    echo "https://www.docker.com/products/docker-desktop/"
    exit 1
fi

python3 -m venv .venv

source .venv/bin/activate

python -m pip install --upgrade pip

pip install -r requirements.txt

if [ ! -f .env ]; then
    cp .env.example .env
fi

docker compose up -d db redis

echo "Waiting for PostgreSQL and Redis..."

sleep 5

python manage.py makemigrations messaging

python manage.py migrate

echo ""
echo "===================================="
echo "       SETUP COMPLETED!"
echo "===================================="

echo ""
echo "Next, run these commands:"
echo ""

echo "source .venv/bin/activate"

echo "python manage.py createsuperuser"

echo "python manage.py runserver"

echo ""
echo "Then visit:"
echo "http://127.0.0.1:8000"