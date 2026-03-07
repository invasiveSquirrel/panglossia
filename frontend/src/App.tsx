import React, { useState, useEffect, useRef } from 'react';
import { Mic, MicOff, Send, Volume2, Sparkles, Settings, Trash2 } from 'lucide-react';
import './App.css';

type Language = 'swedish' | 'german' | 'finnish' | 'portuguese' | 'spanish' | 'dutch' | 'scottish_gaelic';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

const LANG_CODES: Record<Language, string> = {
  swedish: 'sv-SE',
  german: 'de-DE',
  finnish: 'fi-FI',
  portuguese: 'pt-BR',
  spanish: 'es-MX',
  dutch: 'nl-NL',
  scottish_gaelic: 'en-GB'
};

const LANG_NAMES: Record<Language, string> = {
  swedish: 'Svenska',
  german: 'Deutsch',
  finnish: 'Suomi',
  portuguese: 'Português',
  spanish: 'Español',
  dutch: 'Nederlands',
  scottish_gaelic: 'Gàidhlig'
};

const WELCOME_TEXT: Record<Language, string> = {
  swedish: 'Låt oss öva svenska!',
  german: 'Lass uns Deutsch üben!',
  finnish: 'Harjoitellaan suomea ja ruotsia!',
  portuguese: 'Vamos praticar português!',
  spanish: '¡Practiquemos español!',
  dutch: 'Laten we Nederlands oefenen!',
  scottish_gaelic: 'Bribha sinn Gàidhlig!'
};

const INSTRUCTION_TEXT: Record<Language, string> = {
  swedish: 'Klicka på mikrofonen för att tala eller skriv nedan.',
  german: 'Klicke auf das Mikrofon, um zu sprechen, oder schreibe unten.',
  finnish: 'Napsauta mikrofonia puhuaksesi tai kirjoita alle.',
  portuguese: 'Clique no microfone para falar ou escreva abaixo.',
  spanish: 'Haz clic en el micrófono para hablar o escribe abajo.',
  dutch: 'Klik op de microfoon om te praten of schrijf hieronder.',
  scottish_gaelic: 'Cliog air a’ mhiocrofon airson bruidhinn no sgrìobh gu h-ìosal.'
};

const PLACEHOLDER_TEXT: Record<Language, string> = {
  swedish: 'Prata med mig på svenska...',
  german: 'Sprich mit mir auf Deutsch...',
  finnish: 'Puhu minulle suomeksi tai ruotsiksi...',
  portuguese: 'Fale comigo em português...',
  spanish: 'Hable conmigo en español...',
  dutch: 'Praat met me in het Nederlands...',
  scottish_gaelic: 'Bruidhinn rium ann an Gàidhlig...'
};

const LANGUAGES: Language[] = ['swedish', 'german', 'finnish', 'portuguese', 'spanish', 'dutch', 'scottish_gaelic'];

function App() {
  const [language, setLanguage] = useState<Language>(() => {
    return (localStorage.getItem('polyglossia-last-lang') as Language) || 'swedish';
  });
  const [messages, setMessages] = useState<Message[]>([]);
  const messagesLangRef = useRef<Language>(language);
  const [input, setInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingType, setLoadingType] = useState<'transcribing' | 'thinking' | null>(null);
  const [sttError, setSttError] = useState<string | null>(null);
  const [availableVoices, setAvailableVoices] = useState<SpeechSynthesisVoice[]>([]);
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
    const loadVoices = () => setAvailableVoices(window.speechSynthesis.getVoices());
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

  const speak = async (text: string) => {
    if (!text) return;
    const cleanText = text.split('[English]')[0].split('VOCABULARY')[0].replace(/[^\p{L}\p{N}\s\.,\?!]/gu, " ").trim();
    if (!cleanText) return;

    try {
      const res = await fetch('http://localhost:8000/speak', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: cleanText, language }),
      });
      if (res.ok) return;
    } catch (e) {
      console.error("Speak failed:", e);
    }

    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = LANG_CODES[language];
    window.speechSynthesis.speak(utterance);
  };

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;
    const userMsg: Message = { role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    const msgToSend = input;
    setInput('');
    setIsLoading(true);
    setLoadingType('thinking');

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
      setLoadingType(null);
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
        setLoadingType('transcribing');
        try {
          const response = await fetch('http://localhost:8000/transcribe', { method: 'POST', body: formData });
          const data = await response.json();
          if (data.transcript) setInput(prev => (prev ? prev + ' ' : '') + data.transcript);
          else if (data.detail) setSttError(`Transcription Error: ${data.detail}`);
        } catch (error) {
          setSttError('Transcription failed. Ensure Google Speech API is enabled.');
        } finally {
          setIsLoading(false);
          setLoadingType(null);
        }
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      setSttError('Microphone access denied or hardware not found.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
    }
  };

  const renderContent = (content: string) => {
    return content.split('\n')
      .filter(line => !line.match(/^\d+\.\s*(Start|Begin|Beginne|Comienza|Empieza|Comece|Commence)\s+with/i))
      .map(line => line.replace(/^\d+\.\s*/, ''))
      .map((line, i) => {
        const isVocabHeader = line.toUpperCase().includes('VOCABULARY & EXAMPLES');
        const isAdviceHeader = line.toUpperCase().includes('HELPFUL ADVICE');
        const exampleMatch = line.match(/["'«„]([^"'»“]{2,})["'»“]/i);

        if (isVocabHeader || isAdviceHeader) {
          return <h4 key={i} className="vocab-header" style={{ color: isAdviceHeader ? 'var(--blue)' : 'var(--mauve)', borderBottomColor: isAdviceHeader ? 'var(--blue)' : 'var(--surface2)' }}>{line}</h4>;
        }

        // Apply specialized styling for linguistic info
        const parts = line.split(/(\[[^\]]+\]|\([^)]+\))/g);
        const renderedLine = parts.map((part, index) => {
          if (part.startsWith('[') && part.endsWith(']')) {
            return <code key={index} style={{ color: 'var(--sky)', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.9em', padding: '0 4px' }}>{part}</code>;
          }
          if (part.startsWith('(') && part.endsWith(')')) {
            return <code key={index} style={{ color: 'var(--teal)', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.9em', padding: '0 4px', fontStyle: 'italic' }}>{part}</code>;
          }
          return <span key={index}>{part}</span>;
        });

        return (
          <div key={i} className="chat-line">
            <span className="line-text">{renderedLine}</span>
            {exampleMatch && (
              <button onClick={() => speak(exampleMatch[1])} className="speak-btn-small">
                <Volume2 size={14} />
              </button>
            )}
          </div>
        );
      });
  };

  return (
    <div className="app-container">
      <header>
        <div className="logo">
          <h1>
            Polyglossia&nbsp;&nbsp;&nbsp;
            <span style={{ color: '#eed49f', fontFamily: '"Noto Serif Hebrew", serif', fontWeight: 900 }}>
              א
            </span>
          </h1>
        </div>
        <div className="controls">
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
        {messages.length === 0 && (
          <div className="welcome">
            <h2>{WELCOME_TEXT[language]}</h2>
            <p>{INSTRUCTION_TEXT[language]}</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            <div className="content">{renderContent(msg.content)}</div>
            {msg.role === 'assistant' && (
              <button onClick={() => speak(msg.content)} className="speak-btn"><Volume2 size={18} /></button>
            )}
          </div>
        ))}
      </main>

      <footer>
        {sttError && <div className="stt-error">{sttError}</div>}
        <div className="input-area">
          <button className={isRecording ? 'icon-btn recording' : 'icon-btn'} onClick={() => isRecording ? stopRecording() : startRecording()}>
            {isRecording ? <MicOff /> : <Mic />}
          </button>
          <input value={input} onChange={(e) => setInput(e.target.value)} onKeyPress={(e) => e.key === 'Enter' && sendMessage()} placeholder={PLACEHOLDER_TEXT[language]} />
          <button className="icon-btn send" onClick={sendMessage} disabled={!input.trim() || isLoading}><Send /></button>
        </div>
      </footer>
    </div>
  );
}

export default App;
