import React from 'react';
import { Navigate } from 'react-router-dom';

const StrategiesManager: React.FC = () => {
  return <Navigate to="/market/strategies" replace />;
};

export default StrategiesManager;
