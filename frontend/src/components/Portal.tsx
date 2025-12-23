import { useEffect, useState, memo } from 'react';
import { createPortal } from 'react-dom';

interface PortalProps {
  children: React.ReactNode;
}

/**
 * Portal component that renders children into document.body
 * Used for modals and overlays that need to escape the normal DOM hierarchy
 * 
 * Performance optimized with React.memo to prevent unnecessary re-renders.
 * 
 * Requirements:
 * - 10.1: Prevent unnecessary re-renders with React.memo
 */
function Portal({ children }: PortalProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    return () => setMounted(false);
  }, []);

  if (!mounted) return null;

  return createPortal(children, document.body);
}

// Export memoized component to prevent unnecessary re-renders
export default memo(Portal);
