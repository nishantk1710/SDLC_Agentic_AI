import {
  ClipboardList, PencilRuler, Code2, ListChecks,
  FileCode, FileText, FileSpreadsheet, Database, Network, LayoutTemplate,
  GitBranch, BookOpen, ShieldCheck, Bug, PieChart, FolderGit2, TestTube,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

// ---------------------------------------------------------------------------
// Pipeline definition — the single config source.
// Each phase runs its agents strictly in order. A phase can only be started
// once the previous phase has been human-approved. An agent only begins once
// the previous agent in the same phase has finished. When every agent in a
// phase is done, the phase reveals its Generated Artifacts, then asks for
// human approval before the next phase unlocks.
//
// Edit agent names, descriptions, artifacts, and colors HERE. If real data
// supplies these, map the API response into this same shape rather than
// hardcoding elsewhere.
// ---------------------------------------------------------------------------

export type PhaseKey = 'requirement' | 'design' | 'implementation' | 'testing'

// Phase lifecycle: 'locked' -> 'ready' -> 'running' -> 'awaiting' -> 'approved'
export type PhaseStatus = 'locked' | 'ready' | 'running' | 'awaiting' | 'approved'

export interface Agent {
  name: string
  desc: string
}

export interface Artifact {
  name: string
  desc: string
  Icon: LucideIcon
}

export interface Phase {
  key: PhaseKey
  name: string
  short: string
  Icon: LucideIcon
  color: string
  tint: string
  text: string
  agents: Agent[]
  artifacts: Artifact[]
}

export interface PhaseState {
  status: PhaseStatus
  running: number
  done: number
  approved: boolean
}

export const PHASES: Phase[] = [
  {
    key: 'requirement',
    name: 'Requirement & Analysis',
    short: 'Requirement',
    Icon: ClipboardList,
    color: '#7c3aed',
    tint: '#f5f3ff',
    text: '#6d28d9',
    agents: [
      { name: 'Extraction Agent', desc: 'Pulls candidate requirements out of the source documents.' },
      { name: 'Critic Agent', desc: 'Re-checks each requirement against the source and removes anything the documents do not support. The anti-hallucination guardrail; also flags gaps.' },
      { name: 'Clarity Agent', desc: 'Flags vague or untestable wording ("fast", "user-friendly"), explains why, and proposes a precise, testable rewrite.' },
      { name: 'Narrative Writer', desc: 'Drafts the plain-English spec sections (purpose, scope, overview) from approved requirements only, marking anything unsupported as "to be confirmed".' },
    ],
    artifacts: [
      { name: 'requirements.json', desc: 'Structured requirements', Icon: FileCode },
      { name: 'traceability-matrix.csv', desc: 'Source-to-requirement map', Icon: FileSpreadsheet },
      { name: 'clarity-report.md', desc: 'Reworded ambiguous items', Icon: FileText },
      { name: 'specification.md', desc: 'Draft SRS narrative', Icon: FileText },
    ],
  },
  {
    key: 'design',
    name: 'Design',
    short: 'Design',
    Icon: PencilRuler,
    color: '#0d9488',
    tint: '#f0fdfa',
    text: '#0f766e',
    agents: [
      { name: 'SRS Parser', desc: 'Extract requirements, glossary, and user features from the SRS document.' },
      { name: 'Frontend Initializer', desc: 'Create route list, state transitions, and design tokens.' },
      { name: 'Schema Generator', desc: 'Generate the database schema.' },
      { name: 'Repo Creator', desc: 'Initialize the repository with an .env.example.' },
      { name: 'Coding Guidelines', desc: 'Create SKILL.md with tech-stack guidelines.' },
      { name: 'FE Structure Generator', desc: 'Generate the frontend project folder structure.' },
      { name: 'BE Structure Generator', desc: 'Generate the backend project folder structure.' },
      { name: 'API Contract Generator', desc: 'Create the OpenAPI contract and sample payloads.' },
      { name: 'Validation Rules', desc: 'Create validation rules matching schema and API contract.' },
      { name: 'HTML Mockup Generator', desc: 'Build a functional HTML mockup with all UI components.' },
      { name: 'API-to-UI Mapping', desc: 'Map API endpoints to UI components (CSV).' },
      { name: 'Index / Manifest', desc: 'Create the manifest and validate all artifacts are present.' },
      { name: 'Validation Agent', desc: 'Check artifacts for consistency; trigger re-runs on failure.' },
      { name: 'Diagram Creator Agent', desc: 'Generate Mermaid diagrams (use-case, ER, architecture).' },
    ],
    artifacts: [
      { name: 'schema.sql', desc: 'Database schema', Icon: Database },
      { name: 'openapi.yaml', desc: 'API contract', Icon: Network },
      { name: 'design-tokens.json', desc: 'Routes, states, tokens', Icon: FileCode },
      { name: 'mockup/index.html', desc: 'Functional UI mockup', Icon: LayoutTemplate },
      { name: 'api-ui-map.csv', desc: 'Endpoint-to-component map', Icon: FileSpreadsheet },
      { name: 'diagrams.mmd', desc: 'Use-case, ER, architecture', Icon: GitBranch },
      { name: 'manifest.json', desc: 'Validated artifact index', Icon: ListChecks },
    ],
  },
  {
    key: 'implementation',
    name: 'Implementation',
    short: 'Implementation',
    Icon: Code2,
    color: '#2563eb',
    tint: '#eff6ff',
    text: '#1d4ed8',
    agents: [
      { name: 'Code Generation', desc: 'Generates the initial source code from the design package.' },
      { name: 'Code Review', desc: 'Reviews the code and identifies quality issues without modifying it.' },
      { name: 'Refactoring', desc: 'Improves the code by applying the review suggestions.' },
      { name: 'Debugging', desc: 'Runs the application, fixes errors, and ensures it executes successfully.' },
      { name: 'Unit Test Generation', desc: 'Creates and runs unit tests to verify the application functionality.' },
      { name: 'Documentation', desc: 'Generates the README, API documentation, and code documentation.' },
      { name: 'Security', desc: 'Scans the application for vulnerabilities and generates a security report.' },
    ],
    artifacts: [
      { name: '/src', desc: 'Generated source code', Icon: FolderGit2 },
      { name: 'review-notes.md', desc: 'Code review findings', Icon: FileText },
      { name: 'tests/', desc: 'Unit test suite', Icon: TestTube },
      { name: 'README.md', desc: 'Project + API docs', Icon: BookOpen },
      { name: 'security-report.pdf', desc: 'Vulnerability scan', Icon: ShieldCheck },
    ],
  },
  {
    key: 'testing',
    name: 'Testing',
    short: 'Testing',
    Icon: ListChecks,
    color: '#65a30d',
    tint: '#f7fee7',
    text: '#4d7c0f',
    agents: [
      { name: 'Testing Agent', desc: 'Runs the full test suite and reports coverage and defects.' },
    ],
    artifacts: [
      { name: 'test-results.xml', desc: 'Pass / fail results', Icon: FileText },
      { name: 'coverage-report.html', desc: 'Coverage summary', Icon: PieChart },
      { name: 'defects.csv', desc: 'Logged defects', Icon: Bug },
    ],
  },
]

export const initPhaseState = (): Record<PhaseKey, PhaseState> =>
  PHASES.reduce((acc, p, i) => {
    acc[p.key] = {
      status: i === 0 ? 'ready' : 'locked',
      running: -1,
      done: -1,
      approved: false,
    }
    return acc
  }, {} as Record<PhaseKey, PhaseState>)
