import { useState } from 'react'
import ApprovalPanel from '@/components/ApprovalPanel'
import ArtifactList from '@/components/ArtifactList'

export default function DesignPage() {
  const [isAwaitingApproval, setIsAwaitingApproval] = useState(true)
  const [approvalStatus, setApprovalStatus] = useState<'none' | 'approved' | 'rejected'>('none')

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
