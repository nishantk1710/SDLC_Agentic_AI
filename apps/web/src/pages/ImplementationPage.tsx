import { useState } from 'react'
import ApprovalPanel from '@/components/ApprovalPanel'
import ArtifactList from '@/components/ArtifactList'

export default function ImplementationPage() {
  const [isAwaitingApproval, setIsAwaitingApproval] = useState(false)
  const [approvalStatus, setApprovalStatus] = useState<'none' | 'approved' | 'rejected'>('none')
  const [phaseStatus, setPhaseStatus] = useState<'pending' | 'in-progress' | 'completed'>('pending')

  const artifacts = [
    { id: '1', name: 'backend/src/main.ts', type: 'code' as const, size: '2 KB', status: 'pending' as const },
    { id: '2', name: 'backend/package.json', type: 'config' as const, size: '1 KB', status: 'pending' as const },
    { id: '3', name: 'frontend/src/App.tsx', type: 'code' as const, size: '3 KB', status: 'pending' as const },
    { id: '4', name: 'frontend/package.json', type: 'config' as const, size: '2 KB', status: 'pending' as const },
  ]

  const handleApprove = () => {
    setApprovalStatus('approved')
    setIsAwaitingApproval(false)
  }

  const handleReject = () => {
    setApprovalStatus('rejected')
    setIsAwaitingApproval(false)
  }

  const startImplementation = () => {
    setPhaseStatus('in-progress')
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-h1 font-bold text-text mb-2">Phase 3: Implementation</h1>
        <p className="text-text-secondary">Generate source code from design pack</p>
      </div>

      {/* Status Banner */}
      {approvalStatus === 'approved' && (
        <div className="card bg-success/5 border-success border-2 p-4 mb-6 flex items-start gap-3">
          <span className="text-2xl">✓</span>
          <div>
            <p className="font-semibold text-text">Approved</p>
            <p className="text-small text-text-secondary">Implementation approved. Ready to proceed to testing.</p>
          </div>
        </div>
      )}

      {approvalStatus === 'rejected' && (
        <div className="card bg-error/5 border-error border-2 p-4 mb-6 flex items-start gap-3">
          <span className="text-2xl">✗</span>
          <div>
            <p className="font-semibold text-text">Changes Requested</p>
            <p className="text-small text-text-secondary">The Implementation team will address your feedback.</p>
          </div>
        </div>
      )}

      {phaseStatus === 'pending' && (
        <div className="card bg-warning/5 border-warning border-2 p-6 mb-6">
          <h3 className="text-h3 font-bold text-text mb-2">⏳ Awaiting Start</h3>
          <p className="text-text-secondary mb-4">
            Implementation will begin once the Design phase is approved. Code generation will create:
          </p>
          <ul className="list-disc list-inside space-y-2 ml-4 text-text-secondary mb-4">
            <li>REST API backend (Node.js/NestJS)</li>
            <li>Frontend application (React/TypeScript)</li>
            <li>Database migrations</li>
            <li>Configuration files</li>
          </ul>
          <button onClick={startImplementation} className="btn btn-primary">
            Start Code Generation
          </button>
        </div>
      )}

      {phaseStatus === 'in-progress' && (
        <div className="card bg-primary/5 border-primary border-2 p-6 mb-6">
          <h3 className="text-h3 font-bold text-text mb-4">🔨 Generating Code...</h3>
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <span className="text-2xl">✓</span>
              <div>
                <p className="font-semibold text-text">Backend API</p>
                <p className="text-small text-text-secondary">Generated from openapi.yaml</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-2xl">✓</span>
              <div>
                <p className="font-semibold text-text">Database Schema</p>
                <p className="text-small text-text-secondary">Generated from schema.sql</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-2xl">⏳</span>
              <div>
                <p className="font-semibold text-text">Frontend Application</p>
                <p className="text-small text-text-secondary">Generating from mockups and routes...</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {phaseStatus === 'completed' && (
        <div className="card bg-success/5 border-success border-2 p-4 mb-6 flex items-start gap-3">
          <span className="text-2xl">✓</span>
          <div>
            <p className="font-semibold text-text">Code Generation Complete</p>
            <p className="text-small text-text-secondary">All source code has been generated and is ready for review.</p>
          </div>
        </div>
      )}

      {/* Phase Content */}
      <div className="card p-6 mb-6">
        <h2 className="text-h2 font-bold text-text mb-4">💾 Generated Artifacts</h2>
        <p className="text-text-secondary mb-4">
          The Implementation team uses AI to generate working source code directly from the design pack.
        </p>
      </div>

      {/* Artifacts */}
      {phaseStatus !== 'pending' && (
        <ArtifactList artifacts={artifacts} title="Code Artifacts" />
      )}

      {/* Approval Panel */}
      {phaseStatus === 'completed' && (
        <ApprovalPanel
          phaseTitle="Implementation"
          isAwaitingApproval={isAwaitingApproval}
          onApprove={handleApprove}
          onReject={handleReject}
        />
      )}

      {phaseStatus === 'completed' && !isAwaitingApproval && approvalStatus === 'none' && (
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
