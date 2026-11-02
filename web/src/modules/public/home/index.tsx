import { Navigate } from 'react-router-dom';

import { LoginScreen } from '@/components/app/marketing/login-screen.js';
import { useBasisSession } from '@/lib/session/basis-session.js';

export function HomePage() {
  const { ready, user, homePath } = useBasisSession();

  if (ready && user) return <Navigate to={homePath} replace />;

  return <LoginScreen />;
}
