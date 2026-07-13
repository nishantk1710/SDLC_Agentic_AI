import { Link } from 'react-router-dom'

interface PhaseCardProps {
  phase: number
  title: string
  description: string
  status: 'pending' | 'in-progress' | 'awaiting-approval' | 'approved' | 'completed'
  href: string
  artifacts: number
}

const statusConfig = {
  'pending': { bg: 'bg-surface border-border', badge: 'badge-pending', label: 'Pending' },
  'in-progress': { bg: 'bg-surface border-primary', badge: 'badge-primary', label: 'In Progress' },
  'awaiting-approval': { bg: 'bg-surface border-warning', badge: 'badge-warning', label: 'Awaiting Approval' },
  'approved': { bg: 'bg-surface border-success', badge: 'badge-success', label: 'Approved' },
  'completed': { bg: 'bg-surface border-success', badge: 'badge-success', label: 'Completed' },
}

export default function PhaseCard({ phase, title, description, status, href, artifacts }: PhaseCardProps) {
  const config = statusConfig[status]

  return (
    <Link to={href}>
      <div className={`card ${config.bg} border-2 hover:shadow-lg transition cursor-pointer p-6 h-full`}>
        <div className="flex justify-between items-start mb-4">
          <div>
            <div className="text-h3 font-bold text-primary">Phase {phase}</div>
            <h3 className="text-h2 font-bold text-text mt-1">{title}</h3>
          </div>
          <span className={`badge ${config.badge}`}>{config.label}</span>
        </div>
        <p className="text-text-secondary mb-4">{description}</p>
        <div className="flex items-center justify-between pt-4 border-t border-border">
          <span className="text-small text-text-secondary">{artifacts} artifact{artifacts !== 1 ? 's' : ''}</span>
          <span className="text-primary font-semibold">View Phase →</span>
        </div>
      </div>
    </Link>
  )
}
