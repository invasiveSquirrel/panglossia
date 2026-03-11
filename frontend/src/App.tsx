import { useState, useEffect, useRef, useCallback, memo } from 'react';
import { Mic, MicOff, Send, Volume2, Trash2 } from 'lucide-react';
import './App.css';

type Language = 'swedish' | 'german' | 'finnish' | 'portuguese' | 'spanish' | 'dutch';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

const MessageItem = memo(({ msg, onSpeak }: { msg: Message, onSpeak: (text: string) => void }) => {
  return (
    <div className={`message ${msg.role}`}>
      <div className="message-content">
        {msg.content}
        {msg.role === 'assistant' && (
          <button className="btn icon-btn mini-btn speak-btn" onClick={() => onSpeak(msg.content)}>
            <Volume2 size={16} />
          </button>
        )}
      </div>
    </div>
  );
});

const LANG_CODES: Record<Language, string> = {
  swedish: 'sv-SE',
  german: 'de-DE',
  finnish: 'fi-FI',
  portuguese: 'pt-BR',
  spanish: 'es-MX',
  dutch: 'nl-NL'
};

const LANG_NAMES: Record<Language, string> = {
  swedish: 'Svenska',
  german: 'Deutsch',
  finnish: 'Suomi',
  portuguese: 'Português',
  spanish: 'Español',
  dutch: 'Nederlands'
};

const WELCOME_TEXT: Record<Language, string> = {
  swedish: 'Låt oss öva svenska!',
  german: 'Lass uns Deutsch üben!',
  finnish: 'Harjoitellaan suomea ja ruotsia!',
  portuguese: 'Vamos praticar português!',
  spanish: '¡Practiquemos español!',
  dutch: 'Laten we Nederlands oefenen!'
};

const INSTRUCTION_TEXT: Record<Language, string> = {
  swedish: 'Klicka på mikrofonen för att tala eller skriv nedan.',
  german: 'Klicke auf das mikrofon, um zu sprechen, eller schreibe unten.',
  finnish: 'Napsauta mikrofonia puhuaksesi tai kirjoita alle.',
  portuguese: 'Clique no microfone para falar ou escreva abaixo.',
  spanish: 'Haz clic en el micrófono para hablar o escribe abajo.',
  dutch: 'Klik op de microfoon om te praten of schrijf hieronder.'
};

const PLACEHOLDER_TEXT: Record<Language, string> = {
  swedish: 'Prata med mig på svenska...',
  german: 'Sprich mit mir auf Deutsch...',
  finnish: 'Puhu minulle suomeksi tai ruotsiksi...',
  portuguese: 'Fale comigo em português...',
  spanish: 'Hable conmigo en español...',
  dutch: 'Praat med me in het Nederlands...'
};

const LANGUAGES: Language[] = ['swedish', 'german', 'finnish', 'portuguese', 'spanish', 'dutch'];

function App() {
  const [language, setLanguage] = useState<Language>(() => {
    return (localStorage.getItem('polyglossia-last-lang') as Language) || 'swedish';
  });
  const [messages, setMessages] = useState<Message[]>([]);
  const messagesLangRef = useRef<Language>(language);
  const [input, setInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [sttError, setSttError] = useState<string | null>(null);
  const [playbackRate, setPlaybackRate] = useState(1.0);
  const scrollRef = useRef<HTMLDivElement>(null);
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    const saved = localStorage.getItem(`polyglossia-history-${language}`);
    setMessages(saved ? JSON.parse(saved) : []);
    messagesLangRef.current = language;
    localStorage.setItem('polyglossia-last-lang', language);
  }, [language]);

  useEffect(() => {
    if (messages.length > 0 && messagesLangRef.current === language) {
      localStorage.setItem(`polyglossia-history-${language}`, JSON.stringify(messages));
    }
  }, [messages, language]);

  const resetHistory = () => {
    if (window.confirm(`Reset your conversation with ${LANG_NAMES[language]}?`)) {
      setMessages([]);
      localStorage.removeItem(`polyglossia-history-${language}`);
      window.speechSynthesis.cancel();
    }
  };

  useEffect(() => {
    const loadVoices = () => { window.speechSynthesis.getVoices(); };
    window.speechSynthesis.onvoiceschanged = loadVoices;
    loadVoices();
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      setTimeout(() => {
        scrollRef.current!.scrollTop = scrollRef.current!.scrollHeight;
      }, 50);
    }
  }, [messages, isLoading]);

  const speak = useCallback(async (text: string) => {
    if (!text) return;
    const cleanText = text.split('[English]')[0].split('VOCABULARY')[0].replace(/[^\p{L}\p{N}\s\.,\?!]/gu, " ").trim();
    if (!cleanText) return;

    try {
      const res = await fetch('http://localhost:8000/speak', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: cleanText, language, speed: playbackRate }),
      });
      if (res.ok) return;
    } catch (e) {
      console.error("Speak failed:", e);
    }

    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = LANG_CODES[language];
    utterance.rate = playbackRate;
    window.speechSynthesis.speak(utterance);
  }, [language, playbackRate]);

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;
    const userMsg: Message = { role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    const msgToSend = input;
    setInput('');
    setIsLoading(true);

    try {
      const res = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msgToSend, language, history: messages }),
      });
      const data = await res.json();
      if (data.response) {
        setMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
        speak(data.response);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  const startRecording = async () => {
    try {
      setSttError(null);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        const formData = new FormData();
        formData.append('audio', audioBlob);
        formData.append('language', language);

        setIsLoading(true);
        try {
          const response = await fetch('http://localhost:8000/transcribe', { method: 'POST', body: formData });
          const data = await response.json();
          if (data.transcript) setInput(prev => (prev ? prev + ' ' : '') + data.transcript);
          else if (data.detail) setSttError(`Transcription Error: ${data.detail}`);
        } catch (error) {
          setSttError('Transcription failed. Ensure Google Speech API is enabled.');
        } finally {
          setIsLoading(false);
        }
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      setSttError('Microphone access denied or hardware not found.');
    }
  };

  return (
    <div className="app-container">
      <header>
        <div className="logo">
          <h1>
            Panglossia&nbsp;&nbsp;&nbsp;
            <span style={{ color: '#eed49f', fontFamily: '"Noto Serif Hebrew", serif', fontWeight: 900 }}>
              א
            </span>
          </h1>
        </div>
        <div className="controls">
          <div className="speed-selector">
            {[1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7].map(rate => (
              <button 
                key={rate} 
                className={playbackRate === rate ? 'active' : ''} 
                onClick={() => setPlaybackRate(rate)}
                title={`Speed: ${rate}x`}
              >
                {rate === 1.0 ? '1x' : rate.toString().substring(1) + 'x'}
              </button>
            ))}
          </div>
          <div className="language-selector">
            {LANGUAGES.map((lang) => (
              <button key={lang} className={language === lang ? 'active' : ''} onClick={() => { setLanguage(lang); window.speechSynthesis.cancel(); }}>
                {LANG_NAMES[lang]}
              </button>
            ))}
            <button 
              className="reset-btn-mini" 
              onClick={resetHistory} 
              title="Reset Conversation"
            >
              <Trash2 size={20} strokeWidth={1.5} />
            </button>
          </div>
        </div>
      </header>

      <main ref={scrollRef}>
        {messages.length === 0 ? (
          <div className="welcome">
            <h2>{WELCOME_TEXT[language]}</h2>
            <p>{INSTRUCTION_TEXT[language]}</p>
          </div>
        ) : (
          messages.map((msg, i) => (
            <MessageItem key={i} msg={msg} onSpeak={speak} />
          ))
        )}
        {isLoading && <div className="message assistant loading"><div className="typing-indicator"><span></span><span></span><span></span></div></div>}
        {sttError && <div className="error-banner">{sttError}</div>}
      </main>

      <footer>
        <div className="input-container">
          <button className={`btn icon-btn ${isRecording ? 'recording' : ''}`} onClick={() => isRecording ? mediaRecorderRef.current?.stop() : startRecording()}>
            {isRecording ? <MicOff size={20} /> : <Mic size={20} />}
          </button>
          <input 
            type="text" 
            placeholder={PLACEHOLDER_TEXT[language]} 
            value={input} 
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
          />
          <button className="btn primary icon-btn" onClick={sendMessage} disabled={isLoading || !input.trim()}>
            <Send size={20} />
          </button>
        </div>
      </footer>
    </div>
  );
}

export default App;
