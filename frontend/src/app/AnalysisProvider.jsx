import React, { createContext, useContext, useState } from 'react';

const AnalysisContext = createContext(null);

export function AnalysisProvider({ children }) {
  const [analysisId, setAnalysisId] = useState(null);
  const [selectedModules, setSelectedModules] = useState({ ml: [], traditional: [] });

  const value = {
    analysisId,
    setAnalysisId,
    selectedModules,
    setSelectedModules,
  };

  return (
    <AnalysisContext.Provider value={value}>
      {children}
    </AnalysisContext.Provider>
  );
}

export function useAnalysis() {
  const context = useContext(AnalysisContext);
  if (!context) {
    throw new Error('useAnalysis must be used within AnalysisProvider');
  }
  return context;
}
