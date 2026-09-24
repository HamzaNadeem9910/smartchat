import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';

interface Props {
  children: JSX.Element;
}

export default function RequireAuth({ children }: Props) {
  const location = useLocation();
  const isAuthed = Boolean(localStorage.getItem('auth'));

  if (!isAuthed) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}
