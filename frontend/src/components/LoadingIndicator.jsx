import { useEffect, useState } from 'react';
import './LoadingIndicator.css';

export default function LoadingIndicator({ stage, progress = 0, message }) {
  const [dots, setDots] = useState('');

  useEffect(() => {
    const interval = setInterval(() => {
      setDots((prev) => (prev.length >= 3 ? '' : prev + '.'));
    }, 500);

    return () => clearInterval(interval);
  }, []);

  const getStageInfo = () => {
    switch (stage) {
      case 'intent':
        return {
          label: 'Analyzing query complexity',
          icon: '🔍',
          color: '#4a90e2'
        };
      case 'tools':
        return {
          label: 'Running tools',
          icon: '🔧',
          color: '#28a745'
        };
      case 'stage1':
        return {
          label: 'Collecting responses from council',
          icon: '💭',
          color: '#6f42c1'
        };
      case 'stage2':
        return {
          label: 'Peer review in progress',
          icon: '⚖️',
          color: '#fd7e14'
        };
      case 'stage3':
        return {
          label: 'Synthesizing final answer',
          icon: '✨',
          color: '#20c997'
        };
      case 'title':
        return {
          label: 'Generating conversation title',
          icon: '📝',
          color: '#17a2b8'
        };
      default:
        return {
          label: 'Processing',
          icon: '⏳',
          color: '#6c757d'
        };
    }
  };

  const stageInfo = getStageInfo();

  return (
    <div className="loading-indicator">
      <div className="loading-header">
        <span className="loading-icon" style={{ color: stageInfo.color }}>
          {stageInfo.icon}
        </span>
        <span className="loading-label">
          {message || stageInfo.label}
          {dots}
        </span>
      </div>

      {progress > 0 && (
        <div className="progress-bar-container">
          <div
            className="progress-bar-fill"
            style={{
              width: `${Math.min(progress, 100)}%`,
              background: stageInfo.color
            }}
          />
        </div>
      )}

      <div className="loading-spinner">
        <div className="spinner" style={{ borderTopColor: stageInfo.color }} />
      </div>

      {stage === 'stage1' && (
        <div className="stage-hint">
          Models are independently analyzing your question...
        </div>
      )}

      {stage === 'stage2' && (
        <div className="stage-hint">
          Models are ranking each other's responses anonymously...
        </div>
      )}

      {stage === 'stage3' && (
        <div className="stage-hint">
          Chairman is synthesizing the best insights...
        </div>
      )}
    </div>
  );
}

// Compact version for inline loading states
export function LoadingDots() {
  const [dots, setDots] = useState('');

  useEffect(() => {
    const interval = setInterval(() => {
      setDots((prev) => (prev.length >= 3 ? '' : prev + '.'));
    }, 400);

    return () => clearInterval(interval);
  }, []);

  return <span className="loading-dots">{dots}</span>;
}

// Progress bar component
export function ProgressBar({ progress, color = '#4a90e2', height = 4 }) {
  return (
    <div className="progress-bar-standalone" style={{ height: `${height}px` }}>
      <div
        className="progress-bar-fill"
        style={{
          width: `${Math.min(progress, 100)}%`,
          background: color
        }}
      />
    </div>
  );
}
