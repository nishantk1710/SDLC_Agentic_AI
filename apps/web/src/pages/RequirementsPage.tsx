import { useState } from 'react'
import ApprovalPanel from '@/components/ApprovalPanel'
import ArtifactList from '@/components/ArtifactList'
import AgentList from '@/components/AgentList'

export default function RequirementsPage() {
  const [isAwaitingApproval, setIsAwaitingApproval] = useState(false)
  const [approvalStatus, setApprovalStatus] = useState<'none' | 'approved' | 'rejected'>('none')

  const agents = [
    { id: '1', name: 'Extraction Agent', description: 'Reads every source piece and pulls out the individual requirements, rewriting each as a clear "the system shall…" statement — and attaches the exact source sentence it came from.', status: 'completed' as const },
    { id: '2', name: 'Critic Agent', description: "Re-checks each extracted requirement against the original source and removes anything the documents don't actually support. The anti-hallucination guardrail; also flags anything that may have been missed.", status: 'completed' as const },
    { id: '3', name: 'Clarity Agent', description: 'Flags vague or untestable wording (e.g. "fast", "user-friendly"), explains why it\'s a problem, and proposes a precise, testable rewrite.', status: 'completed' as const },
    { id: '4', name: 'Narrative Writer', description: 'Drafts the plain-English sections of the specification (purpose, scope, overview) — from approved requirements only, marking anything unsupported as "to be confirmed".', status: 'completed' as const },
  ]

  const artifacts = [
    { id: '1', name: 'extracted-requirements.md', type: 'document' as const, size: '12 KB', status: 'generated' as const },
    { id: '2', name: 'user-features.md', type: 'document' as const, size: '8 KB', status: 'generated' as const },
    { id: '3', name: 'glossary.md', type: 'document' as const, size: '5 KB', status: 'generated' as const },
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
        <h1 className="text-h1 font-bold text-text mb-2">Phase 1: Requirements</h1>
        <p className="text-text-secondary">Define scope, features, and acceptance criteria</p>
      </div>

      {/* Status Banner */}
      {approvalStatus === 'approved' && (
        <div className="card bg-success/5 border-success border-2 p-4 mb-6 flex items-start gap-3">
          <span className="text-2xl">✓</span>
          <div>
            <p className="font-semibold text-text">Approved</p>
            <p className="text-small text-text-secondary">This phase has been approved. Proceeding to next phase.</p>
          </div>
        </div>
      )}

      {approvalStatus === 'rejected' && (
        <div className="card bg-error/5 border-error border-2 p-4 mb-6 flex items-start gap-3">
          <span className="text-2xl">✗</span>
          <div>
            <p className="font-semibold text-text">Changes Requested</p>
            <p className="text-small text-text-secondary">The Requirements team will review your feedback and make updates.</p>
          </div>
        </div>
      )}

      {/* Phase Content */}
      <div className="card p-6 mb-6">
        <h2 className="text-h2 font-bold text-text mb-4">📋 Scope & Features</h2>
        <div className="space-y-4 text-text-secondary">
          <p>The Requirements phase establishes the foundation for the entire project:</p>
          <ul className="list-disc list-inside space-y-2 ml-4">
            <li>Define functional and non-functional requirements</li>
            <li>Create user stories and acceptance criteria</li>
            <li>Establish glossary of terms</li>
            <li>Document business rules</li>
          </ul>
          <p className="mt-4">
            All downstream teams (Design, Implementation, Testing) depend on these requirements. Ensure completeness and clarity.
          </p>
        </div>
      </div>

      {/* Agents */}
      <AgentList agents={agents} title="Requirement & Analysis Agents" />

      {/* Artifacts */}
      <ArtifactList artifacts={artifacts} title="Generated Artifacts" />

      {/* Approval Panel */}
      <ApprovalPanel
        phaseTitle="Requirements"
        isAwaitingApproval={isAwaitingApproval}
        onApprove={handleApprove}
        onReject={handleReject}
      />

      {/* Start Approval Button */}
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
