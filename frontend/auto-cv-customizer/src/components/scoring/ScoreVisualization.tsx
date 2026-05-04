import React from 'react';
import './ScoreVisualization.css';

interface ScoreVisualizationProps {
  score: number;
  maxScore?: number;
  size?: 'small' | 'medium' | 'large';
}

const ScoreVisualization: React.FC<ScoreVisualizationProps> = ({ 
  score, 
  maxScore = 10, 
  size = 'medium' 
}) => {
  const percentage = (score / maxScore) * 100;
  const getColor = (score: number) => {
    if (score >= 8) return '#22c55e'; // green
    if (score >= 5) return '#eab308'; // yellow
    return '#ef4444'; // red
  };

  const sizeClass = `score-${size}`;

  return (
    <div className={`score-visualization ${sizeClass}`}>
      <div className="score-bar-background">
        <div 
          className="score-bar-fill"
          style={{ 
            width: `${percentage}%`,
            backgroundColor: getColor(score)
          }}
        />
      </div>
      <span className="score-value">{score?.toFixed(1)}</span>
    </div>
  );
};

export default ScoreVisualization;