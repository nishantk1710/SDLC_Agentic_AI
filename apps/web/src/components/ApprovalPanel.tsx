import { useState } from 'react'

interface ApprovalPanelProps {
  phaseTitle: string
  isAwaitingApproval: boolean
  onApprove: () => void
  onReject: () => void
}

export default function ApprovalPanel({ phaseTitle, isAwaitingApproval, onApprove, onReject }: ApprovalPanelProps) {
  const [rejectReason, setRejectReason] = useState('')
  const [showRejectForm, setShowRejectForm] = useState(false)

  if (!isAwaitingApproval) return null

  return (
    <div className="card border-2 border-warning bg-warning/5 p-6 mt-8">
      <div className="flex items-start gap-4">
        <div className="w-10 h-10 rounded-full bg-warning text-on-primary flex items-center justify-center font-bold flex-shrink-0">
          ⚠️
        </div>
        <div className="flex-1">
          <h3 className="text-h3 font-bold text-text mb-2">Human Approval Required</h3>
          <p className="text-text-secondary mb-6">
            The {phaseTitle} phase is complete and awaiting your approval to proceed.
          </p>

          {!showRejectForm ? (
            <div className="flex gap-3">
              <button onClick={onApprove} className="btn btn-primary">
                ✓ Approve & Proceed
              </button>
              <button onClick={() => setShowRejectForm(true)} className="btn btn-secondary">
                ✗ Request Changes
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <label className="block text-small font-semibold mb-2">Feedback (required)</label>
                <textarea
                  className="input min-h-24"
                  placeholder="Describe what needs to be changed..."
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                />
              </div>
              <div className="flex gap-3">
                <button
                  onClick={() => {
                    if (rejectReason.trim()) {
                      onReject()
                      setShowRejectForm(false)
                      setRejectReason('')
                    }
                  }}
                  className="btn btn-danger"
                  disabled={!rejectReason.trim()}
                >
                  Send Feedback
                </button>
                <button
                  onClick={() => {
                    setShowRejectForm(false)
                    setRejectReason('')
                  }}
                  className="btn btn-ghost"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
