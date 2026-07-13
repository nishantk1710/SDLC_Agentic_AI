import React, { useState, useRef, useEffect, useCallback } from 'react'
import {
  Play, Check, Lock, UserCheck, CircleCheck, Loader2, Eye, Package,
  Bolt, ArrowRight,
} from 'lucide-react'
import {
  PHASES, initPhaseState,
  type Phase, type Agent, type Artifact, type PhaseKey, type PhaseState, type PhaseStatus,
} from './phases'
import { driver, type Cancel } from './driver'

// ---------------------------------------------------------------------------
// AutoFlow pipeline dashboard.
// Each phase runs its agents strictly in order. A phase can only be started
// once the previous phase has been human-approved. An agent only begins once
// the previous agent in the same phase has finished. When every agent in a
// phase is done, the phase reveals its Generated Artifacts, then asks for
// human approval before the next phase unlocks.
//
// All timing/side-effects go through `driver` (see ./driver.ts) so the demo
// simulation can be swapped for real backend calls without touching this UI.
// ---------------------------------------------------------------------------

type Transition = { from: number; to: number } | null

export default function SDLCDashboard() {
  const [page, setPage] = useState<'landing' | 'dashboard'>('landing')
  const [state, setState] = useState<Record<PhaseKey, PhaseState>>(initPhaseState)
  const [transition, setTransition] = useState<Transition>(null)
  const timers = useRef<Record<string, Cancel>>({})

  useEffect(() => () => Object.values(timers.current).forEach((cancel) => cancel()), [])

  const runPhase = useCallback((key: PhaseKey) => {
    setState((prev) => {
      if (prev[key].status !== 'ready') return prev
      return { ...prev, [key]: { ...prev[key], status: 'running', running: 0, done: -1 } }
    })
    driver.runPhase(key)
  }, [])

  useEffect(() => {
    const runningPhase = PHASES.find((p) => state[p.key].status === 'running')
    if (!runningPhase) return
    const key = runningPhase.key
    const s = state[key]
    if (s.running < 0) return
    if (timers.current[key]) return

    timers.current[key] = driver.advanceAgent(key, s.running, () => {
      delete timers.current[key]
      setState((prev) => {
        const cur = prev[key]
        const finished = cur.running
        const isLast = finished >= runningPhase.agents.length - 1
        return {
          ...prev,
          [key]: isLast
            ? { ...cur, done: finished, running: -1, status: 'awaiting' }
            : { ...cur, done: finished, running: finished + 1 },
        }
      })
    })
  }, [state])

  const approvePhase = useCallback((key: PhaseKey) => {
    const idx = PHASES.findIndex((p) => p.key === key)
    // Mark the phase approved immediately.
    setState((prev) => {
      if (prev[key].status !== 'awaiting') return prev
      return { ...prev, [key]: { ...prev[key], status: 'approved', approved: true } }
    })
    driver.approvePhase(key)

    if (idx < PHASES.length - 1) {
      // Show the handoff spinner, then unlock the next phase.
      const nextKey = PHASES[idx + 1].key
      setTransition({ from: idx, to: idx + 1 })
      timers.current.handoff = driver.awaitHandoff(nextKey, () => {
        delete timers.current.handoff
        setState((prev) => ({ ...prev, [nextKey]: { ...prev[nextKey], status: 'ready' } }))
        setTransition(null)
      })
    }
  }, [])

  if (page === 'landing') {
    return <Landing onStart={() => setPage('dashboard')} />
  }
  return (
    <Dashboard
      state={state}
      transition={transition}
      onBack={() => setPage('landing')}
      onRun={runPhase}
      onApprove={approvePhase}
    />
  )
}

function Landing({ onStart }: { onStart: () => void }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center px-4 py-16">
      <div className="max-w-3xl w-full text-center space-y-8">
        <div className="inline-flex items-center gap-2 bg-blue-500/10 border border-blue-500/30 rounded-full px-4 py-2">
          <Bolt className="w-4 h-4 text-blue-400" />
          <span className="text-sm font-medium text-blue-300">Automated SDLC Platform</span>
        </div>

        <div className="space-y-4">
          <h1 className="text-6xl md:text-7xl font-bold text-white">AutoFlow</h1>
          <p className="text-lg text-slate-300 max-w-xl mx-auto leading-relaxed">
            Each phase runs its agents in order, then shows the artifacts it generated.
            You review those artifacts and approve before the next phase unlocks.
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-3 py-4">
          {PHASES.map((p, i) => (
            <React.Fragment key={p.key}>
              <div className="flex flex-col items-center gap-1 bg-slate-700/40 border border-slate-600 rounded-xl px-4 py-3 min-w-28">
                <p.Icon className="w-5 h-5" style={{ color: '#c4b5fd' }} />
                <span className="text-xs font-semibold text-white">{p.short}</span>
                <span className="text-[11px] text-slate-400">{p.agents.length} agents</span>
              </div>
              {i < PHASES.length - 1 && <ArrowRight className="w-5 h-5 text-slate-500" />}
            </React.Fragment>
          ))}
        </div>

        <button
          onClick={onStart}
          className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold py-4 px-8 rounded-lg transition-all duration-200 transform hover:scale-105 shadow-lg"
        >
          Get started <ArrowRight className="w-5 h-5" />
        </button>
      </div>
    </div>
  )
}

interface DashboardProps {
  state: Record<PhaseKey, PhaseState>
  transition: Transition
  onBack: () => void
  onRun: (key: PhaseKey) => void
  onApprove: (key: PhaseKey) => void
}

function Dashboard({ state, transition, onBack, onRun, onApprove }: DashboardProps) {
  const approvedCount = PHASES.filter((p) => state[p.key].approved).length

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-6 py-5 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">AutoFlow Pipeline</h1>
            <p className="text-sm text-slate-600 mt-0.5">Project: Modern web application</p>
          </div>
          <button
            onClick={onBack}
            className="px-4 py-2 text-sm text-slate-600 border border-slate-300 hover:bg-slate-100 rounded-lg transition-colors"
          >
            Back
          </button>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-6 py-8">
        <div className="flex items-center gap-1.5 mb-2">
          {PHASES.map((p) => {
            const s = state[p.key]
            const active = s.status === 'running' || s.status === 'awaiting'
            const bg = s.approved ? p.color : active ? p.color : '#e2e8f0'
            return <div key={p.key} className="flex-1 h-1.5 rounded-full" style={{ background: bg }} />
          })}
        </div>
        <p className="text-xs text-slate-500 mb-8">{approvedCount} of {PHASES.length} phases approved</p>

        <div className="space-y-4">
          {PHASES.map((phase, idx) => (
            <React.Fragment key={phase.key}>
              <PhaseCard
                phase={phase}
                idx={idx}
                s={state[phase.key]}
                prevShort={idx > 0 ? PHASES[idx - 1].short : null}
                nextShort={idx < PHASES.length - 1 ? PHASES[idx + 1].short : null}
                isLeaving={transition?.from === idx}
                isIncoming={transition?.to === idx}
                onRun={() => onRun(phase.key)}
                onApprove={() => onApprove(phase.key)}
              />
              {transition?.from === idx && (
                <PhaseTransition from={PHASES[transition.from]} to={PHASES[transition.to]} />
              )}
            </React.Fragment>
          ))}
        </div>
      </div>
    </div>
  )
}

interface PhaseCardProps {
  phase: Phase
  idx: number
  s: PhaseState
  prevShort: string | null
  nextShort: string | null
  isLeaving: boolean
  isIncoming: boolean
  onRun: () => void
  onApprove: () => void
}

function PhaseCard({ phase, s, prevShort, nextShort, isLeaving, isIncoming, onRun, onApprove }: PhaseCardProps) {
  const { Icon } = phase
  const total = phase.agents.length
  const completed = s.done + 1
  const pct = s.approved ? 100 : Math.round((completed / total) * 100)
  const locked = s.status === 'locked'
  const showArtifacts = s.status === 'awaiting' || s.status === 'approved'

  const badge: Record<PhaseStatus, { label: string; cls: string }> = {
    locked: { label: 'Locked', cls: 'bg-slate-100 text-slate-500' },
    ready: { label: 'Ready to run', cls: 'bg-slate-100 text-slate-600' },
    running: { label: 'Running agents', cls: 'bg-blue-100 text-blue-700' },
    awaiting: { label: 'Review artifacts', cls: 'bg-amber-100 text-amber-700' },
    approved: { label: 'Approved', cls: 'bg-green-100 text-green-700' },
  }
  const b = badge[s.status]

  return (
    <div className={`rounded-2xl border bg-white p-5 transition-all ${locked ? 'opacity-70 border-slate-200' : 'border-slate-200'}`}>
      <div className="flex items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-slate-100">
            <Icon className="w-5 h-5" style={{ color: phase.text }} />
          </div>
          <div>
            <p className="font-semibold text-slate-900">{phase.name}</p>
            <p className="text-xs text-slate-500">{total} agents · {phase.artifacts.length} artifacts</p>
          </div>
        </div>
        <span className={`flex-shrink-0 text-xs font-medium px-2.5 py-1 rounded-full ${b.cls}`}>
          {b.label}
        </span>
      </div>

      {locked ? (
        isIncoming ? (
          <div className="flex items-center gap-2 text-sm py-3 font-medium" style={{ color: phase.text }}>
            <Loader2 className="w-4 h-4 animate-spin" />
            Preparing this phase…
          </div>
        ) : (
          <div className="flex items-center gap-2 text-sm text-slate-400 py-3">
            <Lock className="w-4 h-4" />
            Unlocks after {prevShort} is approved
          </div>
        )
      ) : (
        <>
          <div className="flex items-center gap-3 mb-4">
            <div className="flex-1 h-1.5 rounded-full bg-slate-100 overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ width: `${pct}%`, background: phase.color }}
              />
            </div>
            <span className="text-xs font-medium text-slate-600 w-16 text-right">
              {completed} / {total} done
            </span>
          </div>

          <div className="space-y-1.5">
            {phase.agents.map((a, ai) => (
              <AgentRow key={a.name} phase={phase} agent={a} index={ai} s={s} />
            ))}
          </div>

          {showArtifacts && <ArtifactsPanel phase={phase} />}

          <PhaseFooter
            phase={phase}
            s={s}
            nextShort={nextShort}
            isLeaving={isLeaving}
            onRun={onRun}
            onApprove={onApprove}
          />
        </>
      )}
    </div>
  )
}

function AgentRow({ phase, agent, index, s }: { phase: Phase; agent: Agent; index: number; s: PhaseState }) {
  const isDone = index <= s.done
  const isRunning = index === s.running
  const isNext = index === s.done + 1 && s.running < 0 && !isDone
  const isFuture = !isDone && !isRunning && !isNext

  let marker: React.ReactNode
  if (isDone) {
    marker = (
      <span className="rounded-md flex items-center justify-center" style={{ background: phase.color, width: 22, height: 22 }}>
        <Check className="w-3.5 h-3.5 text-white" />
      </span>
    )
  } else if (isRunning) {
    marker = (
      <span className="rounded-md flex items-center justify-center" style={{ background: phase.color, width: 22, height: 22 }}>
        <Loader2 className="w-3.5 h-3.5 text-white animate-spin" />
      </span>
    )
  } else {
    marker = (
      <span className="rounded-md flex items-center justify-center border border-slate-200 bg-slate-50 text-[11px] font-medium text-slate-400" style={{ width: 22, height: 22 }}>
        {index + 1}
      </span>
    )
  }

  const meta = isDone ? (
    <span className="text-[11px] font-medium" style={{ color: phase.text }}>Done</span>
  ) : isRunning ? (
    <span className="text-[11px] font-medium animate-pulse" style={{ color: phase.text }}>Working…</span>
  ) : (
    <span className="text-[11px] text-slate-400">{isNext ? 'Up next' : 'Queued'}</span>
  )

  return (
    <div
      className="flex items-start gap-2.5 rounded-lg border p-2.5 transition-colors"
      style={{
        borderColor: isRunning ? phase.color : '#e2e8f0',
        background: isRunning ? phase.tint : 'transparent',
        opacity: isFuture ? 0.6 : 1,
      }}
    >
      <span className="flex-shrink-0 mt-0.5">{marker}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-medium text-slate-900">{agent.name}</span>
          {meta}
        </div>
        <p className="text-xs text-slate-600 leading-snug mt-0.5">{agent.desc}</p>
        {isRunning && (
          <div className="mt-2 h-[3px] rounded-full overflow-hidden" style={{ background: '#e2e8f0' }}>
            <div className="h-full w-1/2 rounded-full animate-[loading_1.1s_ease-in-out_infinite]" style={{ background: phase.color }} />
          </div>
        )}
      </div>
    </div>
  )
}

function ArtifactsPanel({ phase }: { phase: Phase }) {
  return (
    <div
      className="mt-4 rounded-xl border p-3.5 animate-[reveal_0.35s_ease]"
      style={{ borderColor: phase.color, background: phase.tint }}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
          <Package className="w-4 h-4" style={{ color: phase.text }} />
          Generated artifacts
        </span>
        <span className="text-[11px] font-medium" style={{ color: phase.text }}>
          {phase.artifacts.length} files
        </span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {phase.artifacts.map((f) => (
          <ArtifactCard key={f.name} file={f} phase={phase} />
        ))}
      </div>
    </div>
  )
}

function ArtifactCard({ file, phase }: { file: Artifact; phase: Phase }) {
  const { Icon } = file
  const [opened, setOpened] = useState(false)
  return (
    <div className="flex items-center gap-2.5 rounded-lg border border-slate-200 bg-white p-2.5">
      <span className="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center bg-slate-100">
        <Icon className="w-4 h-4" style={{ color: phase.text }} />
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-slate-900 font-mono truncate">{file.name}</p>
        <p className="text-[11px] text-slate-400">{file.desc}</p>
      </div>
      <button
        onClick={() => {
          setOpened(true)
          driver.openArtifact(phase.key, file.name)
        }}
        className="flex-shrink-0 h-7 px-2.5 inline-flex items-center gap-1.5 text-xs text-slate-600 border border-slate-300 rounded-md hover:bg-slate-50 transition-colors"
      >
        {opened ? <Check className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
        {opened ? 'Opened' : 'View'}
      </button>
    </div>
  )
}

interface PhaseFooterProps {
  phase: Phase
  s: PhaseState
  nextShort: string | null
  isLeaving: boolean
  onRun: () => void
  onApprove: () => void
}

function PhaseFooter({ phase, s, nextShort, isLeaving, onRun, onApprove }: PhaseFooterProps) {
  if (s.status === 'ready') {
    return (
      <button
        onClick={onRun}
        className="w-full h-10 mt-4 flex items-center justify-center gap-2 rounded-lg text-sm font-semibold text-white transition-opacity hover:opacity-90"
        style={{ background: phase.color }}
      >
        <Play className="w-4 h-4" />
        Run {phase.short.toLowerCase()} agents
      </button>
    )
  }
  if (s.status === 'running') {
    return (
      <div className="mt-4 h-10 flex items-center justify-center gap-2 rounded-lg bg-blue-50 text-blue-700 text-sm font-medium">
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
        Agents running — please wait
      </div>
    )
  }
  if (s.status === 'awaiting') {
    // While the handoff spinner is showing, the button is replaced by a
    // confirmation that this phase was approved and is being handed off.
    if (isLeaving) {
      return (
        <div className="mt-3 h-10 flex items-center justify-center gap-2 rounded-lg bg-green-50 text-green-700 text-sm font-medium">
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          Approved — handing off…
        </div>
      )
    }
    return (
      <div className="mt-3">
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-2">
          <p className="text-xs text-amber-800 leading-relaxed flex items-start gap-2">
            <UserCheck className="w-4 h-4 flex-shrink-0 mt-0.5" />
            Review the generated artifacts above. Approve to{' '}
            {nextShort ? `start ${nextShort.toLowerCase()}.` : 'complete the project.'}
          </p>
        </div>
        <button
          onClick={onApprove}
          className="w-full h-10 flex items-center justify-center gap-2 rounded-lg bg-green-600 hover:bg-green-700 text-white text-sm font-semibold transition-colors"
        >
          <Check className="w-4 h-4" />
          Approve and continue
        </button>
      </div>
    )
  }
  if (s.status === 'approved') {
    return (
      <div className="mt-3 flex items-center gap-2 bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-700">
        <CircleCheck className="w-4 h-4" />
        Approved — artifacts handed to next phase
      </div>
    )
  }
  return null
}

// Full-width spinner shown between an approved phase and the next one while the
// pipeline "hands off". Rendered for PHASE_HANDOFF_MS, then removed.
function PhaseTransition({ from, to }: { from: Phase; to: Phase }) {
  const FromIcon = from.Icon
  const ToIcon = to.Icon
  return (
    <div
      className="rounded-2xl border bg-white p-7 flex flex-col items-center text-center gap-4 animate-[reveal_0.35s_ease]"
      style={{ borderColor: to.color }}
    >
      <div className="flex items-center gap-4">
        <div className="flex flex-col items-center gap-1.5 opacity-50">
          <span className="w-10 h-10 rounded-xl flex items-center justify-center bg-slate-100">
            <FromIcon className="w-5 h-5" style={{ color: from.text }} />
          </span>
          <span className="text-[11px] text-slate-400">{from.short}</span>
        </div>

        <div className="flex items-center gap-1.5">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="w-1.5 h-1.5 rounded-full animate-[dotwave_1.2s_ease-in-out_infinite]"
              style={{ background: to.color, animationDelay: `${i * 0.18}s` }}
            />
          ))}
        </div>

        <div className="flex flex-col items-center gap-1.5">
          <span className="relative w-11 h-11">
            <span
              className="absolute inset-0 rounded-full border-[2.5px] border-slate-100 animate-spin"
              style={{ borderTopColor: to.color }}
            />
            <span className="absolute inset-0 flex items-center justify-center">
              <ToIcon className="w-5 h-5" style={{ color: to.text }} />
            </span>
          </span>
          <span className="text-[11px] font-medium" style={{ color: to.text }}>{to.short}</span>
        </div>
      </div>

      <div>
        <p className="text-sm font-medium text-slate-900">Handing off to {to.short.toLowerCase()}</p>
        <p className="text-xs text-slate-500 mt-0.5">Passing approved artifacts to the next phase’s agents…</p>
      </div>
    </div>
  )
}
