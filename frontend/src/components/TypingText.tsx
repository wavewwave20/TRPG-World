import { useState, useEffect } from 'react';

interface TypingTextProps {
  text: string;
  speed?: number; // Characters per second
  onComplete?: () => void;
}

export default function TypingText({ text, speed = 50, onComplete }: TypingTextProps) {
  const [displayedText, setDisplayedText] = useState('');
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    // Reset when text changes
    setDisplayedText('');
    setCurrentIndex(0);
  }, [text]);

  useEffect(() => {
    if (currentIndex >= text.length) {
      // Animation complete
      if (onComplete) {
        onComplete();
      }
      return;
    }

    // Calculate delay in milliseconds per character
    const delayMs = 1000 / speed;

    const timeoutId = setTimeout(() => {
      setDisplayedText(text.slice(0, currentIndex + 1));
      setCurrentIndex(currentIndex + 1);
    }, delayMs);

    return () => clearTimeout(timeoutId);
  }, [currentIndex, text, speed, onComplete]);

  return <>{displayedText}</>;
}
