# Panglossia

Panglossia is an AI-powered conversational language learning tool. It allows you to engage in natural dialogues with an AI tutor while receiving real-time linguistic support, grammar corrections, and vocabulary expansion.

## Key Features
- **Conversational Learning**: Chat with an AI tutor in your target language.
- **Dynamic Vocabulary Extraction**: Important words from your chat are saved into Markdown files.
- **Grammar Feedback**: Real-time corrections and grammatical explanations.
- **Multi-language Support**: Swedish, German, Finnish, Spanish, Portuguese, and Dutch.
- **Voice Integration**: High-quality TTS and STT via Google Cloud or local Piper fallback.

---

## 🚀 Setting Up Ollama (AI Engine)

Panglossia requires [Ollama](https://ollama.com/) to be running locally as the brain of your tutor.

1.  **Download**: Visit [ollama.com](https://ollama.com/download) and download for Windows, macOS, or Linux.
2.  **Install**: Run the installer and ensure Ollama is active.
3.  **Pull the Model**: In your terminal, run:
    ```bash
    ollama run gemma2:9b
    ```
4.  **Keep it Running**: Ollama must be active in the background while you chat in Panglossia.

---

## 💻 Installation

### Prerequisites
- **Node.js** (v18 or higher)
- **Python** (v3.10 or higher)

### 1. Clone the repository
```bash
git clone https://github.com/invasiveSquirrel/panglossia.git
cd panglossia
```

### 2. OS-Specific Setup

#### **Windows**
1.  **Backend**:
    ```powershell
    cd backend
    python -m venv venv
    .\venv\Scripts\activate
    pip install -r requirements.txt
    ```
2.  **Frontend**:
    ```powershell
    cd ..\frontend
    npm install
    ```

#### **macOS**
1.  **Backend**:
    ```bash
    cd backend
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
2.  **Frontend**:
    ```bash
    cd ../frontend
    npm install
    ```

#### **Linux**
Follow the macOS steps above or use the provided `./start.sh`.

---

## 🏃 Running the Application

### Windows (Manual)
Open two terminals:
1.  **Terminal 1 (Backend)**:
    ```powershell
    cd backend
    .\venv\Scripts\activate
    python main.py
    ```
2.  **Terminal 2 (Frontend)**:
    ```powershell
    cd frontend
    npm run dev
    ```
3.  **Terminal 3 (Electron)**:
    ```powershell
    cd frontend
    npm run electron
    ```

### Linux / macOS / Git Bash
```bash
./start.sh
```

---

## 📖 How to Use Panglossia

1.  **Select Practice Language**: Choose the language you want to speak.
2.  **Chat**: Type in the chat box to converse with the AI tutor.
3.  **Learn**: Receive grammar corrections and watch as new words are automatically extracted into Markdown files.
4.  **Sync**: Use your extracted vocabulary in **Wordhord** for flashcard training.

---

## ⚙️ Customizing the Tutor (Prompts)

You can customize your tutor's personality by editing the text files in `backend/prompts/` (e.g., `swedish.txt`).
- **Change Level**: Edit the prompt to specify A1, B1, or B2 levels.
- **Change Personality**: Tell the AI to be a strict teacher or a friendly travel companion.

---

## Configuration
- **Google Cloud**: Place your `google-credentials.json` in the root and set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to enable high-quality voice features.

## License
MIT
