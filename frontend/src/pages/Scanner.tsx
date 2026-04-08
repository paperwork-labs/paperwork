import { Navigate, useLocation } from 'react-router-dom';

export default function Scanner() {
  const { search } = useLocation();
  const params = new URLSearchParams(search);
  if (!params.has('mode')) params.set('mode', 'scan');
  return <Navigate to={`/market/tracked?${params.toString()}`} replace />;
}
