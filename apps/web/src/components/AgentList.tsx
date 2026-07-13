interface Agent {
  id: string
  name: string
  description: string
  status: 'idle' | 'running' | 'completed' | 'error'
}

interface AgentListProps {
  agents: Agent[]
  title?: string
}

const statusConfig = {
  idle: { bg: 'bg-surface-alt', text: 'text-text-secondary', label: 'Idle' },
  running: { bg: 'bg-primary/10', text: 'text-primary', label: 'Running' },
  completed: { bg: 'bg-success/10', text: 'text-success', label: 'Completed' },
  error: { bg: 'bg-error/10', text: 'text-error', label: 'Error' },
}

export default function AgentList({ agents, title = 'Agents' }: AgentListProps) {
  return (
    <div className="card p-6 mt-6">
      <h3 className="text-h3 font-bold text-text mb-4">{title}</h3>
      <div className="space-y-3">
        {agents.map((agent, index) => {
          const status = statusConfig[agent.status]
          return (
            <div
              key={agent.id}
              className="flex items-start justify-between gap-4 p-4 bg-surface rounded-md border border-border hover:border-primary transition"
            >
              <div className="flex items-start gap-4 flex-1">
                <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-small flex-shrink-0">
                  {index + 1}
                </div>
                <div className="flex-1">
                  <p className="font-semibold text-text">{agent.name}</p>
                  <p className="text-small text-text-secondary mt-1">{agent.description}</p>
                </div>
              </div>
              <span className={`badge ${status.bg} ${status.text} flex-shrink-0`}>{status.label}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
