# Product Requirements Document: Specs-Driven Development MCP Server

**Version:** 1.0  
**Date:** 2026-03-02  
**Status:** ✅ Complete - Ready for Implementation

---

## 1. Executive Summary

### 1.1 Overview

The Specs-Driven Development (SDD) MCP Server is an opinionated, specification-first development framework tightly integrated with Goose. It enforces a strict workflow where **specs come before code** and all implementation must align with documented requirements.

### 1.2 Problem Statement

Developers often:
- Start coding before defining clear requirements
- Let documentation become stale and disconnected from code
- Skip quality gates due to friction
- Lack structured guidance for complex projects

### 1.3 Solution

An MCP server that:
- **Enforces** spec-driven development (no bypass)
- **Guides** developers through role-based workflows
- **Integrates** seamlessly with Goose for implementation
- **Verifies** code-spec alignment automatically

### 1.4 Target Users

- **Primary:** The user building this tool (opinionated to their workflow)
- **Secondary:** Developers who want structured, spec-first development
- **Experience Level:** Guides beginners, allows experts to tune

---

## 2. Product Overview

### 2.1 Core Philosophy

1. **Specs Before Code:** No implementation without documentation
2. **Strict Enforcement:** Block actions, no bypass option
3. **Role-Based Workflow:** Sequential roles for comprehensive coverage
4. **Living Documentation:** Specs evolve with the project
5. **Goose Integration:** Seamless handoff to Goose for implementation

### 2.2 Key Differentiators

| Feature | SDD Server | Traditional Tools |
|---------|------------|-------------------|
| Enforcement | Strict (no bypass) | Gentle warnings |
| Workflow | Role-based sequence | Ad-hoc |
| Integration | Native Goose | Generic |
| Philosophy | Opinionated | Configurable |

---

## 3. Core MVP Features

### 3.1 Feature A: Specification Management

**Priority:** P0 (Critical)  
**Effort:** Medium

#### A1. Project Initialization

**User Story:**
> As a developer, I want to start a new project with natural language that gets refined into a structured PRD.

**Acceptance Criteria:**
- New project: Accept natural language description → generate structured PRD
- Existing project: Auto-analyze codebase → extract current architecture
- Create `specs/` directory structure with templates
- Generate initial `.goosehints` for Goose context
- Support both interactive and CLI-driven initialization

**Technical Requirements:**
- Natural language processing for PRD generation
- Codebase analysis for existing projects (AST-based)
- Template system for spec files
- Metadata tracking in `.metadata.json`

---

#### A2. Feature Specification

**User Story:**
> As a developer, I want to create feature-specific specs that inherit from the main project specs.

**Acceptance Criteria:**
- Create feature subdirectories: `specs/<feature-name>/`
- Each feature has: `prd.md`, `arch.md`, `tasks.md`
- Features inherit context from parent specs
- System tracks feature relationships
- Feature naming follows conventions

**Technical Requirements:**
- Feature template system
- Context inheritance mechanism
- Feature registry in metadata

---

#### A3. Spec File Operations

**User Story:**
> As a developer, I want to read, update, and append to spec files through MCP tools.

**Acceptance Criteria:**
- MCP tools for CRUD operations on spec files
- Atomic file operations (no partial writes)
- Validation before writes
- Git-based version control (no internal database)

**Technical Requirements:**
- File operation MCP tools
- Atomic write operations
- Markdown validation

---
### 3.2 Feature B: Role-Based Workflow Engine

**Priority:** P0 (Critical)  
**Effort:** High

#### B1. Role Definition System

**User Story:**
> As a developer, I want the system to automatically invoke the right role at the right time so that my specifications are comprehensive and well-architected.

**Acceptance Criteria:**
- System follows a well-defined role sequence:
  1. **Architect:** Define general architecture
  2. **UI/UX Designer:** Define human-software interaction (CLI, GUI, config files, env vars)
  3. **Interface Designer:** Define software-software interaction (REST, protocols, APIs)
  4. **Security Analyst:** Analyze and define security considerations
  5. **Edge Case Analyst:** Identify edge cases in user interactions, data flows, and process flows
  6. **Senior Developer:** Define KISS approach, minimize code duplication, simplify testing
- Roles are invoked automatically based on workflow stage
- Each role MUST review and provide input at least once
- Multiple roles can collaborate on the same task
- User reviews and can modify role outputs
- System tracks which roles have completed their review

**Technical Requirements:**
- Recipe structure (YAML files in `recipes/` directory)
- Default recipes directory: `recipes/` (configurable via `RECIPES_DIR` env var)
- Recipe template system for consistency

---

#### B2. Dynamic Recipe Generation

**User Story:**
> As a developer, I want recipes to be generated based on my project context but allow me to customize them for my specific needs.

**Acceptance Criteria:**
- Recipes are **dynamically generated** based on:
  - Project type (web app, CLI, library, etc.)
  - Tech stack (Python, Rust, JavaScript, etc.)
  - Existing project structure
  - User preferences
- Generated recipes are **written to disk** for user review
- User can **edit and customize** recipes after generation
- System **proposes new roles or role changes** when project context evolves
- Recipe versioning via git (not internal system)

**Technical Requirements:**
- Recipe generation engine that analyzes project context
- Recipe diff/merge system for updates
- User approval workflow for recipe changes
- Recipe validation against Goose recipe schema

---

#### B3. Implementation Review Workflow

**User Story:**
> As a developer, I want enforced quality gates before committing code so that my codebase maintains high quality and alignment with specs.

**Acceptance Criteria:**
- **Enforced checks before commit:**
  1. **Code Quality Review:** Idiomatic code, best practices
  2. **Lint Check:**
     - Python: `ruff check`, `ruff format`
     - TypeScript: `eslint`, `prettier`
     - Rust: `cargo clippy`, `rustfmt`
     - Configurable per project
  3. **Security Review:** Identify potential security issues
  4. **Spec Alignment Check:** Verify code matches specs
  5. **Documentation Update:** Ensure docs reflect changes
  6. **Context Update:** Update AI client context files if needed
- **Enforcement via `sdd_preflight` tool + git pre-commit hook:**
  - `sdd_init` installs a git pre-commit hook that calls `sdd preflight`
  - `sdd preflight` is the canonical enforcement entry point (used by both the hook and CI)
  - If the hook is not installed, `sdd_status` warns the user
  - MCP tools report enforcement results; they do not "block" natively (MCP is request/response)
- **Grace mode:** An action can be bypassed with `--reason "<justification>"`. The bypass is **always logged** to `.metadata.json` with timestamp, actor, and reason. Bypasses are surfaced in `sdd status` output so they are never silent.
- **Parallel execution:** Run independent checks in parallel for speed

**Technical Requirements:**
- `sdd preflight` CLI command and MCP tool (`sdd_preflight`)
- Pre-commit hook template, installed by `sdd init`
- Parallel role execution (where possible)
- Structured feedback format with exit codes for CI/CD
- Configurable lint tools per tech stack
- Bypass audit log appended to `.metadata.json`

---

#### B4. Edge Case Analyst Role

**User Story:**
> As a developer, I want an automated analysis of potential edge cases in my specifications so that I can handle corner cases before implementation.

**Acceptance Criteria:**
- Edge Case Analyst reviews three domains:
  
  **1. User Interaction Edge Cases:**
  - Invalid user inputs (empty, null, malformed, oversized)
  - Unexpected user sequences (skip steps, go back, repeat)
  - Boundary conditions (min/max values, edge formats)
  - Concurrent user actions (race conditions)
  - Permission/state mismatches
  
  **2. Data Flow Edge Cases:**
  - Empty/null/missing data scenarios
  - Data transformation failures
  - Invalid data states (corrupted, partial, stale)
  - Circular references in data
  - Data size limits (overflow, truncation)
  - Encoding/serialization failures
  
  **3. Process Flow Edge Cases:**
  - Interrupted workflows (crash, timeout, cancellation)
  - Out-of-order operations
  - Retry scenarios and idempotency
  - Rollback requirements
  - External dependency failures (APIs, databases, services)
  - Resource exhaustion (memory, disk, connections)

- Outputs structured as test scenarios:
  ```markdown
  ## Edge Case: Empty Email on Registration
  
  **Domain:** User Interaction
  **Trigger:** User submits registration with empty email field
  **Expected Behavior:** Display clear error, prevent submission
  **Test Scenario:** Attempt registration with empty email
  **Priority:** High
  ```

- Integrates with task generation (edge case test tasks)
- Runs after Security Analyst, before Senior Developer
- Can re-run when specs change

**Technical Requirements:**
- Edge case template system
- Pattern library for common edge cases
- Integration with task creation
- Prioritization heuristic for edge cases

---

### 3.3 Feature C: AI Client Integration Layer

**Priority:** P0 (Critical)
**Effort:** High

The integration layer is designed around an **AIClientBridge** abstraction. Goose is the primary implementation, but the interface allows swapping in other AI agents (Claude Code, Cursor, Cline, etc.) without changing higher-level components.

#### C1. Task-to-AI-Client Bridge

**User Story:**
> As a developer, I want tasks defined in specs to be executable by an AI client so that I can implement features incrementally.

**Acceptance Criteria:**
- Tasks in `tasks.md` are formatted as **bite-sized prompts for the AI client**
- Each task has:
  - Unique ID using short UUID format: `t<7hexchars>` (e.g., `ta3f2b1c`) — collision-resistant, sortable, readable
  - Title
  - Description
  - Status (pending, in_progress, complete)
  - Assigned role (optional)
  - Prompt for AI client (executable prompt)
- System can:
  - Pass prompts to the configured AI client (default: Goose CLI)
  - Track task completion status
  - Monitor implementation progress
  - Calculate completion percentage

**Technical Requirements:**
- `AIClientBridge` abstract interface with `GooseClientBridge` as default implementation
- Task status tracking in `tasks.md`
- Progress monitoring system

---

#### C2. Parallel Role Execution

**User Story:**
> As a developer, I want multiple roles to review my work in parallel so that I get comprehensive feedback quickly.

**Acceptance Criteria:**
- Independent roles run in parallel
- Dependent roles run sequentially
- System coordinates role execution
- Feedback consolidated into single report
- User can review all feedback before proceeding

**Technical Requirements:**
- Role dependency graph
- Parallel execution engine
- Result aggregation system
- Conflict resolution (if roles disagree)

---

#### C3. AI Client Context Management

**User Story:**
> As a developer, I want the AI client to have the right context at each directory level so that it makes informed decisions aligned with my specs.

**Acceptance Criteria:**
- Context hint files generated at:
  - Project root level (`specs/.context-hints`)
  - Feature level (`specs/<feature>/.context-hints`)
- For Goose specifically, these are emitted as `.goosehints` (client-specific format handled by `AIClientBridge` implementation)
- Context content includes:
  - Reference to relevant specs
  - Key architectural decisions
  - Constraints and guidelines
  - Tech stack information
- Context files are **version controlled** (git)

**Technical Requirements:**
- Client-agnostic context template system
- `AIClientBridge` translates to client-specific format on write
- Automatic update triggers on spec changes
- Validation that context files reflect current specs

---

#### C4. MCP Resources & Prompts

**User Story:**
> As a developer, I want spec files directly accessible as MCP resources and role definitions available as MCP prompts, so that any MCP-compatible AI client can consume them natively.

**Acceptance Criteria:**
- **MCP Resources** expose spec files:
  - `sdd://specs/prd` → content of `specs/prd.md`
  - `sdd://specs/arch` → content of `specs/arch.md`
  - `sdd://specs/tasks` → content of `specs/tasks.md`
  - `sdd://specs/features/{name}/prd` → feature-level specs
  - Resources are read-only; mutations go through `sdd_spec_write` tool
- **MCP Prompts** expose role definitions:
  - `sdd_role_architect` → Architect role system prompt
  - `sdd_role_security` → Security Analyst role system prompt
  - `sdd_role_edge_case` → Edge Case Analyst role system prompt
  - (one per built-in role)
  - Prompts include embedded current spec context
- Resources automatically refresh when underlying files change

**Technical Requirements:**
- MCP resource handlers in `src/sdd_server/mcp/resources/`
- MCP prompt handlers in `src/sdd_server/mcp/prompts/`
- File-content caching with invalidation on write

---
### 3.4 Feature D: Alignment & Enforcement System

**Priority:** P0 (Critical)  
**Effort:** High

#### D1. Spec-Code Alignment Verification

**User Story:**
> As a developer, I want the system to detect when my code diverges from specs so that I can fix misalignments immediately.

**Acceptance Criteria:**
- System detects misalignment between:
  - Code implementation vs. `arch.md`
  - Implemented features vs. `prd.md`
  - Completed tasks vs. `tasks.md`
- **Action-required warnings:**
  - User must choose: Fix the code OR Update specs
  - System provides a natural-language summary of differences
- Alignment check runs:
  - Before each commit (via `sdd_preflight`)
  - On-demand (user request via `sdd_align_check`)
  - After task completion

**Technical Requirements:**
- **LLM-based semantic alignment** (not AST-based): the relevant spec section and a `git diff` or file listing are passed to the configured AI client, which returns a structured alignment assessment. This approach detects semantic misalignment (wrong behavior, missing requirement coverage) that static AST analysis cannot.
- Spec parser (Markdown) to extract relevant sections
- Structured output: `AlignmentReport` with issues list, severity, and suggested actions
- Diff generation to provide context to the LLM

> **Design Note:** AST-based analysis was considered but is descoped from the MVP. It requires language-specific parsers for each supported language and can only detect structural divergence, not semantic misalignment. The LLM approach is simpler, more accurate for semantic gaps, and language-agnostic.

---

#### D2. Enforcement Mode

**User Story:**
> As a developer, I want the system to block my actions if specs are missing so that I'm forced to maintain proper documentation — with a visible escape hatch for exceptional cases.

**Acceptance Criteria:**
- **Blocked actions:**
  - Implementing code without corresponding spec
  - Committing without completing quality gates
  - Skipping required role reviews
- **Enforcement behavior:**
  - Clear error message explaining what's missing
  - Guided workflow to create missing specs
  - **Grace mode:** Any block can be bypassed with an explicit reason (`--reason "..."`)
    - Bypass is always logged to `.metadata.json` with timestamp and reason
    - `sdd status` highlights active bypasses prominently
    - Useful for hotfixes, prototyping, or bootstrapping
- System provides:
  - Checklist of missing items
  - Templates to accelerate spec creation

**Technical Requirements:**
- Enforcement middleware
- Pre-commit hooks (installed by `sdd init`)
- Checklist generation
- Template injection system
- Bypass audit log (append-only in `.metadata.json`)

---

#### D3. Progress Monitoring & Status Tracking

**User Story:**
> As a developer, I want to see the implementation progress of my project so that I know what's completed and what's remaining.

**Acceptance Criteria:**
- Dashboard shows:
  - Overall project completion percentage
  - Feature-level progress
  - Task-level status (pending/in_progress/complete)
  - Role review completion status
- Progress visualization:
  - Text-based progress bars
  - Summary statistics
  - Blocked items highlighted

**Technical Requirements:**
- Status tracking in `tasks.md` and metadata
- Progress calculation engine
- Status query API (MCP tools)

---

### 3.5 Feature E: Execution Loop & Monitoring System

**Priority:** P0 (Critical)  
**Effort:** High

#### E1. Workflow State Machine

**User Story:**
> As a developer, I want the system to track my project's workflow state automatically so that I always know where I am in the development process and what's next.

**Acceptance Criteria:**
- State is tracked at **two levels**:
  - **Project level** (rollup): overall project status derived from feature states
  - **Feature level** (authoritative): each feature has its own independent state machine
- **Feature workflow states:**
  - `uninitialized` → Feature not yet set up
  - `initializing` → PRD generation in progress
  - `spec_review` → Awaiting role reviews
  - `ready` → Specs complete, ready for implementation
  - `implementing` → Active development
  - `reviewing` → Pre-commit review in progress
  - `blocked` → Enforcement has blocked an action
  - `completed` → Feature complete
- Multiple features can be in different states simultaneously (e.g., Feature A `implementing`, Feature B `spec_review`)
- Project state is a rollup: `all completed → project completed`, `any blocked → project blocked`, etc.
- State transitions are automatic based on user actions and system checks
- Invalid transitions are prevented with clear guidance
- State history is maintained per feature for debugging

**Technical Requirements:**
- Per-feature state machine with transition validation
- Project-level rollup computed from feature states
- State persistence per feature in `.metadata.json`
- Event-driven state transitions

---

#### E2. Continuous Monitoring Loop

**User Story:**
> As a developer, I want the system to continuously monitor my project and proactively alert me when attention is needed.

**Acceptance Criteria:**
- File watcher monitors:
  - Spec file changes (`specs/**/*.md`)
  - Source code changes (configurable paths)
  - Configuration changes (`.goosehints`, `recipes/`)
- Automatic detection of:
  - Spec-code drift (alignment issues)
  - Missing specs for new files
  - Outdated role reviews after spec changes
  - Uncommitted changes requiring review
- Proactive notifications:
  - "Spec drift detected in `auth.py`"
  - "New files lack specs: `payment.py`, `invoice.py`"
  - "Architecture changed, UI Designer review recommended"

**Technical Requirements:**
- File system watcher (watchdog or native)
- Debounced change detection (avoid spam)
- Event queue for processing
- Configurable watch paths and ignore patterns

---

#### E3. Workflow Orchestrator

**User Story:**
> As a developer, I want the system to guide me through the development loop automatically, suggesting next actions and keeping me on track.

**Acceptance Criteria:**
- Orchestrator manages the execution loop:
  1. **Detect** → Monitor current state and changes
  2. **Validate** → Check alignment and compliance
  3. **Trigger** → Invoke appropriate roles/actions
  4. **Guide** → Provide clear next-step suggestions
  5. **Update** → Refresh state and status
- Automatic role invocation when conditions met:
  - After PRD creation → Invoke Architect role
  - After architecture changes → Re-invoke dependent roles
  - Before commit → Run review workflow
- Next-action suggestions always available via `sdd status`
- Background processing doesn't block user

**Technical Requirements:**
- Event-driven orchestrator
- Rule engine for trigger conditions
- Integration with RoleEngine and EnforcementMiddleware
- Async processing for non-blocking operation

---

#### E4. Execution Loop Visualization

**User Story:**
> As a developer, I want to visualize the execution loop and understand what the system is doing so that I trust the automation.

**Acceptance Criteria:**
- Status dashboard shows:
  - Current workflow state with visual indicator
  - Active monitoring status (watching/paused)
  - Recent events and triggered actions
  - Pending automated actions
- Event log shows:
  - File changes detected
  - Automatic validations run
  - Roles triggered automatically
  - State transitions occurred
- Can pause/resume monitoring
- Can trigger manual orchestrator cycle

**Technical Requirements:**
- Event logging system
- Real-time status updates
- CLI visualization with Rich

---

## 4. Non-Functional Requirements

### 4.1 Security Requirements

**SEC-001: Input Validation**
- All user inputs validated
- Prevent path traversal attacks
- Sanitize Markdown content
- Validate file paths stay within allowed directories

**SEC-002: File System Security**
- MCP server write access is restricted to `specs/` and `recipes/` directories
- MCP server **read access** extends to source code directories (required by the AlignmentChecker to compare code against specs)
- Read paths are configured explicitly via `SDD_SOURCE_DIRS` (default: `src/`, `lib/`) and cannot traverse outside the project root
- Secure file permissions
- Atomic file operations

**SEC-003: Git Security**
- No automatic credential handling
- Validate git repository before operations
- Prevent accidental commits of sensitive data

---

### 4.2 Performance Requirements

**PERF-001: Response Time**
- Spec file operations (CRUD): < 100ms for files < 1MB
- Project initialization: < 2s for new, < 10s for existing
- Task status queries: < 50ms
- Progress dashboard: < 200ms
- Alignment verification: < 5s for projects < 1000 files

**PERF-002: Scalability**
- Support projects with 1000+ source files
- Support specs with 100+ features
- Support tasks.md with 500+ tasks

**PERF-003: LLM Cost Awareness**
- Alignment checks pass only a focused diff + relevant spec section to the LLM (not full codebase)
- Role execution reports estimated token usage in the result
- `sdd config` exposes `max_tokens_per_check` to cap alignment check scope
- Parallel role execution respects a configurable concurrency limit (`max_parallel_roles`, default: 3) to avoid runaway API costs

---

### 4.3 Reliability Requirements

**REL-001: Data Integrity**
- Atomic file writes
- No data loss on crash (recover from git)
- Validation before any write operation

**REL-002: Error Handling**
- Graceful degradation
- Clear error messages with actionable guidance
- No silent failures

---

### 4.4 Usability Requirements

**USE-001: Developer Experience**
- Clear, concise CLI output
- Progress indicators for long operations
- Color-coded status (✅ green, ⚠️ yellow, ❌ red)
- Helpful error messages with suggested fixes

**USE-002: Documentation**
- Inline help for all MCP tools
- Example-driven documentation
- Quick start guide (< 5 minutes to first spec)

---

### 4.5 Compatibility Requirements

**COMP-001: Platform Support**
- Linux (Ubuntu 20.04+)
- macOS (11.0+ Big Sur)
- Windows (10+ with WSL2)

**COMP-002: AI Client Version**
- Default client: Goose >= 1.0.0
- Version check on initialization
- Alternative clients selectable via `SDD_AI_CLIENT` environment variable

**COMP-003: Python Version**
- Requires Python >= 3.14 (uses `tomllib` from stdlib, `asyncio.TaskGroup`, and other 3.11+ features)

**COMP-004: Language Support**
- Language-agnostic spec format (Markdown)
- LLM-based alignment analysis works for any language
- Extensible to other languages via plugin architecture

---

### 4.6 Maintainability Requirements

**MAIN-001: Code Quality**
- Python: `ruff check` and `ruff format`
- Type hints for all public APIs
- Docstrings for all modules, classes, and functions
- Test coverage >= 80%

**MAIN-002: Extensibility**
- Plugin system for new roles
- Plugin system for new lint tools
- Plugin system for new code analyzers
- Configurable templates for specs

---
## 5. Technical Architecture Constraints

### 5.1 Technology Stack Decision

**Recommendation:** **Python for MVP**

| Criterion | Python | Rust | Winner |
|-----------|--------|------|--------|
| **MCP Ecosystem** | Mature (official SDK) | Emerging | Python ✅ |
| **Development Speed** | Fast | Slower | Python ✅ |
| **Performance** | Good | Excellent | Rust ✅ |
| **Code Analysis** | Excellent (AST libs) | Good | Python ✅ |
| **Ecosystem** | Massive (PyPI) | Growing | Python ✅ |

**Rationale:**
1. MCP SDK maturity in Python
2. Faster iteration for MVP
3. Rich Python ecosystem for AST analysis
4. Can port hot paths to Rust later if needed

---

### 5.2 Architecture Principles

**ARCH-001: Modular Design**
```
sdd-server/
├── core/              # Core MCP server logic
├── spec_manager/      # Spec file CRUD operations
├── role_engine/       # Role invocation and coordination
├── ai_client/         # AI client bridge (Goose, Claude Code, etc.)
├── alignment/         # Spec-code verification (LLM-based)
├── enforcement/       # Enforcement logic with grace mode
└── utils/             # Shared utilities
```

**ARCH-002: Stateless Design**
- No database (all state in files and git)
- MCP server can be restarted without data loss

**ARCH-003: Event-Driven**
- Spec changes trigger role reviews
- Task completion triggers alignment checks
- File changes trigger `.goosehints` updates

**ARCH-004: Plugin Architecture**
- Roles defined as plugins
- Lint tools defined as plugins
- Code analyzers defined as plugins

---

### 5.3 File System Structure

```
project-root/
├── specs/
│   ├── .metadata.json           # Project metadata
│   ├── prd.md                   # Main product requirements
│   ├── arch.md                  # Main architecture
│   ├── tasks.md                 # Main task list
│   ├── .goosehints              # Project-level Goose context
│   └── feature-*/               # Feature subdirectories
│       ├── prd.md
│       ├── arch.md
│       ├── tasks.md
│       └── .goosehints
├── recipes/                     # Goose recipes (generated)
│   ├── architect.yml
│   ├── ui-designer.yml
│   ├── interface-designer.yml
│   ├── security-analyst.yml
│   ├── edge-case-analyst.yml
│   └── senior-developer.yml
└── README.md
```

**Environment Variables:**
- `SPECS_DIR`: Override default `specs/` directory
- `RECIPES_DIR`: Override default `recipes/` directory
- `SDD_LOG_LEVEL`: Logging level (default: `INFO`)
- `SDD_AI_CLIENT`: AI client backend (`goose` | `claude-code` | custom) (default: `goose`)
- `SDD_SOURCE_DIRS`: Comma-separated source dirs for alignment read access (default: `src,lib`)
- `SDD_MAX_PARALLEL_ROLES`: Max concurrent role executions (default: `3`)

---

## 6. Success Metrics

### 6.1 Primary Success Metric

**Developer Satisfaction:**
- Self-reported satisfaction
- Target: "This tool is useful for me"

### 6.2 Secondary Success Metrics

- **Spec Completeness:** 100% of features with complete specs
- **Spec-Code Alignment:** 95%+ code aligned with specs
- **Review Coverage:** 100% commits with all quality gates passed
- **Time to First Spec:** < 30 minutes from project init

---

## 7. Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Goose API changes break integration | Medium | High | Version pinning, compatibility checks |
| Performance issues with large projects | Medium | Medium | Optimize incrementally, add caching |
| Too opinionated, users feel constrained | Medium | High | Allow recipe customization |
| Enforcement feels annoying | High | Medium | Clear feedback, quick workflows |
| MVP scope creep | High | High | Strict feature freeze |

---

## 8. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-3)
- [ ] Set up Python MCP server skeleton
- [ ] Implement spec file management (CRUD operations)
- [ ] Create basic templates for prd.md, arch.md, tasks.md
- [ ] Implement project initialization (new vs existing)
- [ ] Add metadata tracking

### Phase 2: Role System (Weeks 4-6)
- [ ] Design role definition schema (YAML)
- [ ] Implement role invocation engine
- [ ] Create default roles (architect, security, UI, interface, edge-case-analyst, senior-dev)
- [ ] Implement dynamic recipe generation
- [ ] Add user review workflow

### Phase 3: Goose Integration (Weeks 7-8)
- [ ] Implement Goose CLI bridge
- [ ] Create task-to-Goose prompt converter
- [ ] Implement `.goosehints` management
- [ ] Add parallel role execution
- [ ] Track task completion status

### Phase 4: Enforcement & Alignment (Weeks 9-11)
- [ ] Implement spec-code alignment verification
- [ ] Create pre-commit hooks
- [ ] Add strict enforcement middleware
- [ ] Implement progress monitoring
- [ ] Create status dashboard
- [ ] Implement workflow state machine
- [ ] Add file watcher for continuous monitoring
- [ ] Create workflow orchestrator

### Phase 5: Polish & Testing (Week 12)
- [ ] Comprehensive testing (unit, integration, e2e)
- [ ] Documentation completion
- [ ] Performance optimization
- [ ] Bug fixes and polish
- [ ] Release MVP

---

**Document Status:** ✅ Complete - Ready for Implementation

**Next Steps:**
1. Review PRD with stakeholders
2. Create technical architecture document (`arch.md`)
3. Set up development environment
4. Begin Phase 1 implementation
