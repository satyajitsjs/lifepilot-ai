"use client";

import { useEffect, useRef, useState } from "react";
import { Mic, MicOff, Volume2, VolumeX } from "lucide-react";

type SpeechResult = { isFinal: boolean; [index: number]: { transcript: string } };
type SpeechResultEvent = { resultIndex: number; results: ArrayLike<SpeechResult> };
type SpeechErrorEvent = { error: string };

interface BrowserSpeechRecognition {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechResultEvent) => void) | null;
  onerror: ((event: SpeechErrorEvent) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

type RecognitionConstructor = new () => BrowserSpeechRecognition;
type BrowserWithRecognition = Window & {
  SpeechRecognition?: RecognitionConstructor;
  webkitSpeechRecognition?: RecognitionConstructor;
};

function speechRecognitionConstructor(): RecognitionConstructor | undefined {
  if (typeof window === "undefined") return undefined;
  const browser = window as BrowserWithRecognition;
  return browser.SpeechRecognition || browser.webkitSpeechRecognition;
}

export function VoiceInputButton({ onTranscript }: { onTranscript: (text: string) => void }) {
  const [available, setAvailable] = useState(false);
  const [listening, setListening] = useState(false);
  const [language, setLanguage] = useState("en-IN");
  const [status, setStatus] = useState("");
  const [error, setError] = useState(false);
  const recognizerRef = useRef<BrowserSpeechRecognition | null>(null);

  useEffect(() => {
    setAvailable(Boolean(speechRecognitionConstructor()));
    return () => {
      recognizerRef.current?.abort();
      recognizerRef.current = null;
    };
  }, []);

  function toggleListening() {
    if (recognizerRef.current) {
      recognizerRef.current.stop();
      setStatus("Finishing transcription...");
      return;
    }
    const Recognizer = speechRecognitionConstructor();
    if (!Recognizer) {
      setError(true);
      setStatus("Voice recognition isn't available here. Try Chrome or Edge on HTTPS or localhost.");
      return;
    }

    const recognizer = new Recognizer();
    recognizer.lang = language;
    recognizer.continuous = false;
    recognizer.interimResults = true;

    recognizer.onresult = event => {
      const finalParts: string[] = [];
      const interimParts: string[] = [];
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const transcript = result[0]?.transcript?.trim();
        if (!transcript) continue;
        if (result.isFinal) finalParts.push(transcript);
        else interimParts.push(transcript);
      }
      if (finalParts.length) {
        onTranscript(finalParts.join(" "));
        setStatus("Transcript added. Review it, then select Generate plan.");
      } else if (interimParts.length) {
        setStatus("Hearing: " + interimParts.join(" ").slice(0, 120));
      }
    };
    recognizer.onerror = event => {
      const messages: Record<string, string> = {
        "not-allowed": "Microphone permission was denied. Allow microphone access in your browser.",
        "service-not-allowed": "Your browser blocked its speech recognition service.",
        "audio-capture": "No microphone was found. Check your audio input.",
        "no-speech": "No speech was detected. Please try again.",
        "network": "Speech recognition needs a working network connection.",
      };
      setError(true);
      setStatus(messages[event.error] || "Speech recognition stopped. Please try again.");
    };
    recognizer.onend = () => {
      recognizerRef.current = null;
      setListening(false);
    };
    recognizerRef.current = recognizer;
    setError(false);
    setStatus("Listening... speak your request.");
    try {
      recognizer.start(); // User click is required to start microphone access.
      setListening(true);
    } catch {
      recognizerRef.current = null;
      setListening(false);
      setError(true);
      setStatus("Could not start the microphone. Check browser permissions.");
    }
  }

  return (
    <div className="voice-input-wrap">
      <div className="voice-controls">
        <label className="voice-language">
          <select
            value={language}
            aria-label="Spoken language"
            onChange={event => setLanguage(event.target.value)}
            disabled={listening}
          >
            <option value="en-IN">English</option>
            <option value="hi-IN">हिन्दी</option>
          </select>
        </label>
        <button
          type="button"
          className={`voice-mic ${listening ? "is-listening" : ""}`}
          onClick={toggleListening}
          aria-label={listening ? "Stop voice input" : "Speak your action request"}
          aria-pressed={listening}
          title={available ? "Speak your request (review transcript before submitting)" : "Voice input unavailable in this browser"}
          disabled={!available}
        >
          {listening ? <MicOff size={17} /> : <Mic size={17} />}
          {listening ? "Stop" : "Speak"}
        </button>
      </div>
      {(!available || status) && (
        <p className={`voice-status ${error ? "voice-error" : ""}`} role="status">
          {status || "Voice isn't supported in this browser. Try Chrome or Edge."}
        </p>
      )}
    </div>
  );
}

export function ReadAloudButton({ text }: { text: string }) {
  const [speaking, setSpeaking] = useState(false);
  const [available, setAvailable] = useState(false);

  useEffect(() => {
    setAvailable(typeof window !== "undefined" &&
      "speechSynthesis" in window && "SpeechSynthesisUtterance" in window);
    return () => {
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  function toggleSpeech() {
    if (!available) return;
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text.slice(0, 950));
    utterance.lang = "en-IN";
    utterance.rate = 1;
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    window.speechSynthesis.speak(utterance);
    setSpeaking(true);
  }

  return (
    <button
      type="button"
      className="modal-speak"
      onClick={toggleSpeech}
      disabled={!available}
      aria-label={speaking ? "Stop reading the plan" : "Read the plan aloud"}
      title={speaking ? "Stop speaking" : "Read plan aloud"}
    >
      {speaking ? <VolumeX size={18} /> : <Volume2 size={18} />}
    </button>
  );
}
