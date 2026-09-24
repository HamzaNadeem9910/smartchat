import { Navigate, useLocation } from 'react-router-dom';

interface RequireAdminAuthProps {
  children: JSX.Element;
}

export default function RequireAdminAuth({ children }: RequireAdminAuthProps) {
  const location = useLocation();
  
  const adminAuthRaw = localStorage.getItem('adminAuth');
  let adminAuth: { email: string; role: string } | null = null;
  
  if (adminAuthRaw) {
    try {
      adminAuth = JSON.parse(adminAuthRaw);
    } catch {
      adminAuth = null;
    }
  }

  if (!adminAuth || adminAuth.role !== 'admin') {
    return <Navigate to="/admin/login" state={{ from: location }} replace />;
  }

  return children;
}
