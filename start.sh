#!/bin/bash

# Polyglossia Launcher
# Optimized for Gemini CLI and manual terminal use.

# Get the script directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "🚀 Starting Polyglossia..."

# 1. Clean up any stale processes
echo "🧹 Cleaning up old processes..."
fuser -k 8000/tcp 5173/tcp 2>/dev/null
pkill -f "electron" 2>/dev/null

# 2. Start Backend (FastAPI)
echo "🧠 Starting Backend..."
cd "$DIR/backend"

# Load Gemini API Key into environment
if [ -f "/home/chris/wordhord/wordhord_api.txt" ]; then
    export GOOGLE_API_KEY=$(cat /home/chris/wordhord/wordhord_api.txt)
    echo "✅ Gemini API Key loaded into environment."
fi

# Handle Google Cloud Credentials
if [ -f "$DIR/google-credentials.json" ] && ! grep -q "YOUR_PROJECT_ID" "$DIR/google-credentials.json"; then
    export GOOGLE_APPLICATION_CREDENTIALS="$DIR/google-credentials.json"
    echo "✅ Using Google Cloud TTS."
else
    echo "⚠️ Using local TTS fallback."
fi
# -B avoids corrupted .pyc files
nohup ./venv/bin/python -B main.py > backend.log 2>&1 &
BACKEND_PID=$!

# 3. Start Frontend (Vite)
echo "🖥️ Starting Frontend..."
cd "$DIR/frontend"
nohup npm run dev > frontend.log 2>&1 &
FRONTEND_PID=$!

# 4. Wait for services to initialize
echo "⏳ Initializing..."
sleep 5

# 5. Check if services started successfully
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "❌ Backend failed! Check backend/backend.log"
    exit 1
fi
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo "❌ Frontend failed! Check frontend/frontend.log"
    exit 1
fi

# 6. Launch Electron App
echo "✨ Launching Application window..."
nohup npx electron . --disable-gpu --disable-software-rasterizer --no-sandbox > electron.log 2>&1 &
ELECTRON_PID=$!

echo "-----------------------------------"
echo "✅ Polyglossia is now running!"
echo "-----------------------------------"

# Do not use 'wait' here so the Gemini CLI doesn't hang.
# If you run this in a terminal and want it to stay in the foreground, 
# you can run: wait
wait
