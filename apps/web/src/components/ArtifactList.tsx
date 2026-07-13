interface Artifact {
  id: string
  name: string
  type: 'document' | 'code' | 'schema' | 'config' | 'spec'
  size?: string
  status: 'generated' | 'pending' | 'reviewing'
}

interface ArtifactListProps {
  artifacts: Artifact[]
  title?: string
}

const typeConfig = {
  document: { icon: '📄', color: 'text-blue-600' },
  code: { icon: '💻', color: 'text-green-600' },
  schema: { icon: '🗂️', color: 'text-purple-600' },
  config: { icon: '⚙️', color: 'text-gray-600' },
  spec: { icon: '📋', color: 'text-orange-600' },
}

const statusConfig = {
  generated: { bg: 'bg-success/12', text: 'text-success', label: 'Generated' },
  pending: { bg: 'bg-warning/12', text: 'text-warning', label: 'Pending' },
  reviewing: { bg: 'bg-primary/12', text: 'text-primary', label: 'Reviewing' },
}

export default function ArtifactList({ artifacts, title = 'Artifacts' }: ArtifactListProps) {
  return (
    <div className="card p-6 mt-6">
      <h3 className="text-h3 font-bold text-text mb-4">{title}</h3>
      <div className="space-y-3">
        {artifacts.map((artifact) => {
          const type = typeConfig[artifact.type]
          const status = statusConfig[artifact.status]
          return (
            <div
              key={artifact.id}
              className="flex items-center justify-between p-4 bg-surface rounded-md border border-border hover:border-primary transition"
            >
              <div className="flex items-center gap-4 flex-1">
                <span className="text-2xl">{type.icon}</span>
                <div className="flex-1">
                  <p className="font-semibold text-text">{artifact.name}</p>
                  <p className="text-small text-text-secondary">{artifact.type}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                {artifact.size && <span className="text-small text-text-secondary">{artifact.size}</span>}
                <span className={`badge ${status.bg} ${status.text}`}>{status.label}</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
