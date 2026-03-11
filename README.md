# Panglossia

Panglossia is an AI-powered conversational language learning tool. It allows you to engage in natural dialogues with an AI tutor while receiving real-time linguistic support, grammar corrections, and vocabulary expansion.

## Key Features
- **Conversational Learning**: Chat with an AI tutor in your target language.
- **Adjustable Playback Speed**: Slow down the AI's voice (0.5x, 0.75x, 1.0x) to hear every syllable clearly, with pitch-preserved audio.
- **Dynamic Vocabulary Extraction**: Important words from your chat are saved directly to the shared Wordhord SQLite database.
- **Grammar Feedback**: Real-time corrections and grammatical explanations.
- **Multi-language Support**: Swedish, German, Finnish, Spanish, Portuguese, Dutch, and Scottish Gaelic.
- **Voice Integration**: High-quality TTS and STT via Google Cloud or local espeak-ng/Piper fallback.

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
- **espeak-ng**: For Scottish Gaelic and IPA support.

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
```bash
./start.sh
```

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

1.  **Select Practice Language**: Choose the language you want to speak (including Scottish Gaelic).
2.  **Chat**: Type in the chat box to converse with the AI tutor (Morag for Gaelic, Katja for German, etc.).
3.  **Learn**: Receive grammar corrections and watch as new words are automatically extracted.
4.  **Sync**: Your vocabulary is saved to `~/wordhord.db`, ready for use in **Wordhord**.

---

## ⚙️ Customizing the Tutor (Prompts)

You can customize your tutor's personality by editing the text files in `backend/prompts/` (e.g., `scottish_gaelic.txt`).
- **Change Level**: Edit the prompt to specify A1, B1, or B2 levels.
- **Change Personality**: Tell the AI to be a strict teacher or a friendly travel companion.

---

## Configuration
- **Google Cloud**: Place your `google-credentials.json` in the root and set `GOOGLE_APPLICATION_CREDENTIALS` to enable high-quality voice features.

## License
MIT
