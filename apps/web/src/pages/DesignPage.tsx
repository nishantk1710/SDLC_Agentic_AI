import { useState } from 'react'
import ApprovalPanel from '@/components/ApprovalPanel'
import ArtifactList from '@/components/ArtifactList'
import AgentList from '@/components/AgentList'

export default function DesignPage() {
  const [isAwaitingApproval, setIsAwaitingApproval] = useState(true)
  const [approvalStatus, setApprovalStatus] = useState<'none' | 'approved' | 'rejected'>('none')

  const agents = [
    { id: '1', name: 'SRS Parser', description: 'Extract requirements, glossary, and user features from SRS document', status: 'completed' as const },
    { id: '2', name: 'Frontend Initializer', description: 'Create route list, state transitions, and design tokens', status: 'completed' as const },
    { id: '3', name: 'Schema Generator', description: 'Generate database schema', status: 'completed' as const },
    { id: '4', name: 'Repo Creator', description: 'Initialize repository with .env.example', status: 'completed' as const },
    { id: '5', name: 'Coding Guidelines', description: 'Create SKILL.md with tech stack guidelines', status: 'completed' as const },
    { id: '6', name: 'FE Structure Generator', description: 'Generate frontend project folder structure', status: 'completed' as const },
    { id: '7', name: 'BE Structure Generator', description: 'Generate backend project folder structure', status: 'completed' as const },
    { id: '8', name: 'API Contract Generator', description: 'Create OpenAPI contract and sample payloads', status: 'completed' as const },
    { id: '9', name: 'Validation Rules', description: 'Create validation rules matching schema and API contract', status: 'completed' as const },
    { id: '10', name: 'HTML Mockup Generator', description: 'Build functional HTML mockup with all UI components', status: 'completed' as const },
    { id: '11', name: 'API-to-UI Mapping', description: 'Map API endpoints to UI components (CSV)', status: 'completed' as const },
    { id: '12', name: 'Index/Manifest', description: 'Create manifest and validate all artifacts present', status: 'completed' as const },
    { id: '13', name: 'Validation Agent', description: 'Check artifacts for consistency; trigger re-runs on failure', status: 'completed' as const },
    { id: '14', name: 'Diagram Creator Agent', description: 'Generate Mermaid diagrams (use-case, ER, architecture)', status: 'completed' as const },
  ]

  const artifacts = [
    { id: '1', name: 'architecture.md', type: 'document' as const, size: '15 KB', status: 'generated' as const },
    { id: '2', name: 'openapi.yaml', type: 'spec' as const, size: '45 KB', status: 'generated' as const },
    { id: '3', name: 'schema.sql', type: 'schema' as const, size: '8 KB', status: 'generated' as const },
    { id: '4', name: 'mockup.html', type: 'code' as const, size: '120 KB', status: 'generated' as const },
    { id: '5', name: 'routes.json', type: 'config' as const, size: '6 KB', status: 'generated' as const },
    { id: '6', name: 'tokens.json', type: 'config' as const, size: '3 KB', status: 'generated' as const },
    { id: '7', name: 'state-transitions.md', type: 'document' as const, size: '10 KB', status: 'generated' as const },
  ]

  const handleApprove = () => {
    setApprovalStatus('approved')
    setIsAwaitingApproval(false)
  }

  const handleReject = () => {
    setApprovalStatus('rejected')
    setIsAwaitingApproval(false)
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-h1 font-bold text-text mb-2">Phase 2: Design</h1>
        <p className="text-text-secondary">Create architecture, mockups, and API specifications</p>
      </div>

      {/* Status Banner */}
      {approvalStatus === 'approved' && (
        <div className="card bg-success/5 border-success border-2 p-4 mb-6 flex items-start gap-3">
          <span className="text-2xl">✓</span>
          <div>
            <p className="font-semibold text-text">Approved</p>
            <p className="text-small text-text-secondary">Design phase approved. Implementation can now begin.</p>
          </div>
        </div>
      )}

      {approvalStatus === 'rejected' && (
        <div className="card bg-error/5 border-error border-2 p-4 mb-6 flex items-start gap-3">
          <span className="text-2xl">✗</span>
          <div>
            <p className="font-semibold text-text">Changes Requested</p>
            <p className="text-small text-text-secondary">The Design team will review your feedback and refine the design.</p>
          </div>
        </div>
      )}

      {/* Phase Content */}
      <div className="card p-6 mb-6">
        <h2 className="text-h2 font-bold text-text mb-4">🎨 Design Deliverables</h2>
        <div className="space-y-4 text-text-secondary">
          <p>The Design phase creates the technical and visual blueprint:</p>
          <div className="grid grid-cols-2 gap-4 mt-4">
            <div className="bg-surface rounded-md p-4 border border-border">
              <p className="font-semibold text-text mb-2">System Architecture</p>
              <p className="text-small">Technology stack, components, data flow</p>
            </div>
            <div className="bg-surface rounded-md p-4 border border-border">
              <p className="font-semibold text-text mb-2">API Specification</p>
              <p className="text-small">REST endpoints, request/response schemas</p>
            </div>
            <div className="bg-surface rounded-md p-4 border border-border">
              <p className="font-semibold text-text mb-2">Database Schema</p>
              <p className="text-small">Tables, relationships, constraints</p>
            </div>
            <div className="bg-surface rounded-md p-4 border border-border">
              <p className="font-semibold text-text mb-2">UI/UX Mockups</p>
              <p className="text-small">Screens, interactions, responsive design</p>
            </div>
          </div>
        </div>
      </div>

      {/* Agents */}
      <AgentList agents={agents} title="Design Agents" />

      {/* Artifacts */}
      <ArtifactList artifacts={artifacts} title="Generated Design Artifacts" />

      {/* Approval Panel */}
      <ApprovalPanel
        phaseTitle="Design"
        isAwaitingApproval={isAwaitingApproval}
        onApprove={handleApprove}
        onReject={handleReject}
      />

      {!isAwaitingApproval && approvalStatus === 'none' && (
        <button
          onClick={() => setIsAwaitingApproval(true)}
          className="btn btn-primary mt-6"
        >
          Request Approval
        </button>
      )}
    </div>
  )
}
