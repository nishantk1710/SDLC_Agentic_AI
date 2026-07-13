import { useState } from 'react'
import ApprovalPanel from '@/components/ApprovalPanel'
import ArtifactList from '@/components/ArtifactList'

export default function TestingPage() {
  const [isAwaitingApproval, setIsAwaitingApproval] = useState(false)
  const [approvalStatus, setApprovalStatus] = useState<'none' | 'approved' | 'rejected'>('none')
  const [phaseStatus, setPhaseStatus] = useState<'pending' | 'in-progress' | 'completed'>('pending')

  const artifacts = [
    { id: '1', name: 'test-report.html', type: 'document' as const, size: '250 KB', status: 'pending' as const },
    { id: '2', name: 'unit-tests.ts', type: 'code' as const, size: '45 KB', status: 'pending' as const },
    { id: '3', name: 'integration-tests.ts', type: 'code' as const, size: '32 KB', status: 'pending' as const },
    { id: '4', name: 'coverage-report.json', type: 'config' as const, size: '15 KB', status: 'pending' as const },
  ]

  const handleApprove = () => {
    setApprovalStatus('approved')
    setIsAwaitingApproval(false)
  }

  const handleReject = () => {
    setApprovalStatus('rejected')
    setIsAwaitingApproval(false)
  }

  const startTesting = () => {
    setPhaseStatus('in-progress')
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-h1 font-bold text-text mb-2">Phase 4: Testing</h1>
        <p className="text-text-secondary">Validate functionality, quality, and coverage</p>
      </div>

      {/* Status Banner */}
      {approvalStatus === 'approved' && (
        <div className="card bg-success/5 border-success border-2 p-4 mb-6 flex items-start gap-3">
          <span className="text-2xl">✓</span>
          <div>
            <p className="font-semibold text-text">Approved & Complete</p>
            <p className="text-small text-text-secondary">All phases completed successfully. Ready for production.</p>
          </div>
        </div>
      )}

      {approvalStatus === 'rejected' && (
        <div className="card bg-error/5 border-error border-2 p-4 mb-6 flex items-start gap-3">
          <span className="text-2xl">✗</span>
          <div>
            <p className="font-semibold text-text">Issues Found</p>
            <p className="text-small text-text-secondary">The Implementation team will fix the issues you identified.</p>
          </div>
        </div>
      )}

      {phaseStatus === 'pending' && (
        <div className="card bg-warning/5 border-warning border-2 p-6 mb-6">
          <h3 className="text-h3 font-bold text-text mb-2">⏳ Awaiting Start</h3>
          <p className="text-text-secondary mb-4">
            Testing will begin once the Implementation phase is approved. Tests will validate:
          </p>
          <ul className="list-disc list-inside space-y-2 ml-4 text-text-secondary mb-4">
            <li>Unit tests for individual components</li>
            <li>Integration tests for workflows</li>
            <li>API contract compliance</li>
            <li>Database migrations</li>
            <li>Code coverage (&gt;80% target)</li>
          </ul>
          <button onClick={startTesting} className="btn btn-primary">
            Start Testing
          </button>
        </div>
      )}

      {phaseStatus === 'in-progress' && (
        <div className="card bg-primary/5 border-primary border-2 p-6 mb-6">
          <h3 className="text-h3 font-bold text-text mb-4">🧪 Running Tests...</h3>
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <span className="text-2xl">✓</span>
              <div>
                <p className="font-semibold text-text">Unit Tests</p>
                <p className="text-small text-text-secondary">1,250 tests passed in 45s</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-2xl">✓</span>
              <div>
                <p className="font-semibold text-text">Integration Tests</p>
                <p className="text-small text-text-secondary">450 tests passed in 90s</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-2xl">⏳</span>
              <div>
                <p className="font-semibold text-text">End-to-End Tests</p>
                <p className="text-small text-text-secondary">Running smoke tests...</p>
              </div>
            </div>
            <div className="mt-6 p-4 bg-surface rounded-md border border-border">
              <p className="text-small font-semibold text-text mb-2">Code Coverage</p>
              <div className="w-full bg-surface-alt rounded-full h-2">
                <div className="bg-success h-2 rounded-full" style={{ width: '87%' }} />
              </div>
              <p className="text-small text-text-secondary mt-2">87% coverage (target: 80%)</p>
            </div>
          </div>
        </div>
      )}

      {phaseStatus === 'completed' && (
        <div className="card bg-success/5 border-success border-2 p-4 mb-6 flex items-start gap-3">
          <span className="text-2xl">✓</span>
          <div>
            <p className="font-semibold text-text">All Tests Passed</p>
            <p className="text-small text-text-secondary">Ready for final approval and production release.</p>
          </div>
        </div>
      )}

      {/* Phase Content */}
      <div className="card p-6 mb-6">
        <h2 className="text-h2 font-bold text-text mb-4">✅ Quality Assurance</h2>
        <p className="text-text-secondary mb-4">
          The Testing team validates that generated code meets requirements and quality standards.
        </p>
        <div className="grid grid-cols-2 gap-4 mt-4">
          <div className="bg-surface rounded-md p-4 border border-border">
            <p className="font-semibold text-text mb-2">Functional Testing</p>
            <p className="text-small text-text-secondary">Verify all features work as specified</p>
          </div>
          <div className="bg-surface rounded-md p-4 border border-border">
            <p className="font-semibold text-text mb-2">Performance Testing</p>
            <p className="text-small text-text-secondary">Check response times and load capacity</p>
          </div>
          <div className="bg-surface rounded-md p-4 border border-border">
            <p className="font-semibold text-text mb-2">Security Testing</p>
            <p className="text-small text-text-secondary">Identify vulnerabilities and compliance issues</p>
          </div>
          <div className="bg-surface rounded-md p-4 border border-border">
            <p className="font-semibold text-text mb-2">Coverage Analysis</p>
            <p className="text-small text-text-secondary">Ensure adequate code and test coverage</p>
          </div>
        </div>
      </div>

      {/* Artifacts */}
      {phaseStatus !== 'pending' && (
        <ArtifactList artifacts={artifacts} title="Test Artifacts" />
      )}

      {/* Approval Panel */}
      {phaseStatus === 'completed' && (
        <ApprovalPanel
          phaseTitle="Testing"
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
          Request Final Approval
        </button>
      )}

      {approvalStatus === 'approved' && (
        <div className="card bg-success/5 border-success border-2 p-6 mt-8 text-center">
          <h3 className="text-h2 font-bold text-success mb-2">🎉 Project Complete</h3>
          <p className="text-text-secondary">
            All phases completed and approved. Your application is ready for production.
          </p>
        </div>
      )}
    </div>
  )
}
