import { useState } from 'react'
import PhaseCard from '@/components/PhaseCard'

export default function DashboardPage() {
  const [phases] = useState([
    {
      phase: 1,
      title: 'Requirements',
      description: 'Define scope, features, and acceptance criteria',
      status: 'completed' as const,
      href: '/requirements',
      artifacts: 3,
    },
    {
      phase: 2,
      title: 'Design',
      description: 'Create architecture, mockups, and specifications',
      status: 'awaiting-approval' as const,
      href: '/design',
      artifacts: 7,
    },
    {
      phase: 3,
      title: 'Implementation',
      description: 'Generate source code from design pack',
      status: 'pending' as const,
      href: '/implementation',
      artifacts: 0,
    },
    {
      phase: 4,
      title: 'Testing',
      description: 'Validate functionality and quality',
      status: 'pending' as const,
      href: '/testing',
      artifacts: 0,
    },
  ])

  const completedPhases = phases.filter(p => p.status === 'completed').length
  const totalPhases = phases.length

  return (
    <div>
      <div className="mb-12">
        <h1 className="text-h1 font-bold text-text mb-2">SDLC Workflow</h1>
        <p className="text-text-secondary">
          Requirements → Design → Implementation → Testing
        </p>
      </div>

      {/* Progress Bar */}
      <div className="card p-6 mb-8">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-h3 font-semibold text-text">Progress</h3>
          <span className="text-text-secondary font-semibold">{completedPhases}/{totalPhases} phases</span>
        </div>
        <div className="w-full bg-surface-alt rounded-full h-3">
          <div
            className="bg-primary h-3 rounded-full transition-all"
            style={{ width: `${(completedPhases / totalPhases) * 100}%` }}
          />
        </div>
      </div>

      {/* Phase Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {phases.map((phase) => (
          <PhaseCard
            key={phase.phase}
            phase={phase.phase}
            title={phase.title}
            description={phase.description}
            status={phase.status}
            href={phase.href}
            artifacts={phase.artifacts}
          />
        ))}
      </div>

      {/* Info Box */}
      <div className="card bg-primary/5 border-primary border-2 p-6 mt-8">
        <h3 className="text-h3 font-bold text-text mb-2">📌 How It Works</h3>
        <ol className="space-y-2 text-text-secondary">
          <li><span className="font-semibold">Requirements Team</span> defines scope and features</li>
          <li><span className="font-semibold">Design Team</span> creates architecture and mockups</li>
          <li><span className="font-semibold">Implementation Team</span> generates code from design pack</li>
          <li><span className="font-semibold">Testing Team</span> validates quality and functionality</li>
        </ol>
        <p className="mt-4 text-small text-text-secondary">
          Each phase requires human approval before proceeding to the next stage.
        </p>
      </div>
    </div>
  )
}
