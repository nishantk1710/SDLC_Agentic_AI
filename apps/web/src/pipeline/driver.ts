import type { PhaseKey } from './phases'

// ---------------------------------------------------------------------------
// Pipeline driver — the ONE place the demo simulation lives.
//
// The dashboard UI never calls timers directly; it goes through this driver.
// Today the default `simulationDriver` reproduces the reference demo using
// fixed timers. To wire the real backend (see CLAUDE_CODE_CONTEXT.md → "Wiring
// to my real backend"), replace each method below with real calls — the UI and
// its state machine do not change:
//
//   runPhase(key)                  -> POST /phases/:key/run
//   advanceAgent(key, i, onDone)   -> subscribe to real per-agent status
//                                     (websocket / poll); call onDone() when the
//                                     agent at index i reports 'done'. Return a
//                                     function that cancels the subscription.
//   approvePhase(key)              -> POST /phases/:key/approve
//   awaitHandoff(nextKey, onReady) -> resolve when the next phase reports 'ready'
//                                     from the backend (not a fixed delay).
//   openArtifact(key, name)        -> open/download the real artifact.
//
// Every method that starts async work returns a `Cancel` so the UI can tear it
// down on unmount, exactly as the demo clears its timers.
// ---------------------------------------------------------------------------

export type Cancel = () => void

export interface PipelineDriver {
  /** User pressed "Run <phase> agents". Fire-and-forget notification. */
  runPhase(key: PhaseKey): void
  /** Drive the agent at `agentIndex` in `key`; call `onDone` when it finishes. */
  advanceAgent(key: PhaseKey, agentIndex: number, onDone: () => void): Cancel
  /** User pressed "Approve and continue". Fire-and-forget notification. */
  approvePhase(key: PhaseKey): void
  /** Wait for the handoff to `nextKey` to complete, then call `onReady`. */
  awaitHandoff(nextKey: PhaseKey, onReady: () => void): Cancel
  /** User pressed "View" on an artifact. */
  openArtifact(key: PhaseKey, artifactName: string): void
}

// Demo timings from the reference component. Kept here so the simulation is
// the only thing referencing them.
const AGENT_DURATION_MS = 1600
export const PHASE_HANDOFF_MS = 1900

/**
 * Default driver: reproduces the reference demo exactly (fixed timers, no
 * network). Swap this out for a real implementation of `PipelineDriver` when
 * the backend endpoints exist.
 */
export const simulationDriver: PipelineDriver = {
  runPhase(_key) {
    // TODO(real backend): POST /phases/:key/run
  },

  advanceAgent(_key, _agentIndex, onDone) {
    // TODO(real backend): replace the timer with real per-agent status.
    // Subscribe to status updates and call onDone() when this agent is 'done'.
    const t = setTimeout(onDone, AGENT_DURATION_MS)
    return () => clearTimeout(t)
  },

  approvePhase(_key) {
    // TODO(real backend): POST /phases/:key/approve
  },

  awaitHandoff(_nextKey, onReady) {
    // TODO(real backend): resolve when `nextKey` reports 'ready' from the
    // backend (await a callback/promise) instead of this fixed delay.
    const t = setTimeout(onReady, PHASE_HANDOFF_MS)
    return () => clearTimeout(t)
  },

  openArtifact(_key, _artifactName) {
    // TODO(real backend): open in a modal / download URL / link to artifact store.
  },
}

// The driver the dashboard uses. Point this at a real implementation later.
export const driver: PipelineDriver = simulationDriver
