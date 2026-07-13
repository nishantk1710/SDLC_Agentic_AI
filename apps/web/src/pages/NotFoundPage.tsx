import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <div className="flex items-center justify-center min-h-96">
      <div className="text-center">
        <h1 className="text-6xl font-bold text-primary mb-4">404</h1>
        <h2 className="text-h2 font-bold text-text mb-2">Page Not Found</h2>
        <p className="text-text-secondary mb-6">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <Link to="/" className="btn btn-primary">
          Back to Dashboard
        </Link>
      </div>
    </div>
  )
}
