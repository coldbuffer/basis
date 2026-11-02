import { Navigate, useSearchParams } from 'react-router-dom';

/** Legacy route — auth lives on the home hero. */
export function LoginPage() {
  const [searchParams] = useSearchParams();
  const search = searchParams.toString();
  return <Navigate to={search ? `/?${search}` : '/'} replace />;
}
