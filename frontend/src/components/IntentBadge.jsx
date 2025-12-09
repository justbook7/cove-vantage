import React from 'react';
import './IntentBadge.css';

export default function IntentBadge({ intent }) {
  if (!intent) return null;

  const { complexity, suggested_models, estimated_cost, reasoning, confidence, workflow } = intent;

  // Color coding by complexity
  const getComplexityColor = () => {
    switch (complexity) {
      case 'simple':
        return '#10b981'; // green
      case 'moderate':
        return '#3b82f6'; // blue
      case 'complex':
        return '#f59e0b'; // amber
      case 'expert':
        return '#ef4444'; // red
      default:
        return '#6b7280'; // gray
    }
  };

  return (
    <div className="intent-badge" style={{ borderLeftColor: getComplexityColor() }}>
      <div className="intent-header">
        <span className="intent-complexity" style={{ color: getComplexityColor() }}>
          {complexity.charAt(0).toUpperCase() + complexity.slice(1)} complexity
        </span>
        <span className="intent-separator">•</span>
        <span className="intent-models">
          {suggested_models.length} {suggested_models.length === 1 ? 'model' : 'models'}
        </span>
        <span className="intent-separator">•</span>
        <span className="intent-cost">
          Est. ${estimated_cost.toFixed(3)}
        </span>
      </div>

      {reasoning && (
        <div className="intent-reasoning">
          {reasoning}
        </div>
      )}

      {confidence !== undefined && confidence < 0.7 && (
        <div className="intent-warning">
          ⚠️ Low confidence classification ({Math.round(confidence * 100)}%)
        </div>
      )}

      <div className="intent-details">
        <span className="intent-workflow">Workflow: {workflow}</span>
        {suggested_models.length > 0 && (
          <span className="intent-model-list">
            Models: {suggested_models.map(m => m.split('/')[1] || m).join(', ')}
          </span>
        )}
      </div>
    </div>
  );
}
