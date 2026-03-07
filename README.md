# Polyglossia

Polyglossia is an AI-powered conversational language learning tool. It allows you to engage in natural dialogues with an AI tutor while receiving real-time linguistic support, grammar corrections, and vocabulary expansion.

## Key Features
- **Natural Conversations**: Chat with an AI tutor in your target language.
- **Contextual Vocabulary**: Automatically identifies and extracts important vocabulary from your chats.
- **Grammar Feedback**: Provides instant corrections and explanations for your mistakes.
- **Multi-language Support**: Designed for learners of Swedish, German, Finnish, Spanish, Portuguese, and Dutch.
- **Voice Integration**: High-quality TTS and STT for listening and speaking practice.

## Prerequisites
- **Node.js** (v18+)
- **Python** (3.10+)
- **Ollama** (Running locally)
- **Google Cloud Credentials** (For TTS/STT services)
- **Piper** (Optional local TTS fallback)

## Installation

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/polyglossia.git
cd polyglossia
```

### 2. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Frontend Setup
```bash
cd ../frontend
npm install
```

## Configuration
- Create a `google-credentials.json` file in the root directory for Google Cloud services.
- Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable pointing to this file.
- Ensure Ollama is running on your machine.

## Running the Application
```bash
./start.sh
```

## Integration with Wordhord
Vocabulary extracted during Polyglossia sessions is saved in Markdown files, which can then be imported into **Wordhord** for spaced repetition training.

## License
MIT
