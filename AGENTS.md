# Project Context: Trading Assistant
You are building the Trading Assistant V1. The architecture, business rules, and technical designs are strictly defined in the following files. **You must read these files before making any architectural or data model decisions.**

**1. The Master Narrative (Read This First):**
- `docs/design/HLD.md`: The consolidated High-Level Design linking all architectural decisions together.

**2. Execution & Roadmap:**
- `implementation/delivery_plan.md`: The roadmap, phased approach, and V1/V2 scope boundaries.
- `implementation/Phase1_build_playbook.md`: The exact step-by-step execution guide, constraints, and Definition of Done for Phase 1. Implemented.
- `implementation/Phase2_build_playbook.md`: The exact step-by-step execution guide, constraints, and Definition of Done for Phase 2. Implemented.
- `implementation/Phase3_build_playbook.md`: The exact step-by-step execution guide, constraints, and Definition of Done for Phase 2. Implemented.
- `implementation/Phase4_build_playbook.md`: The exact step-by-step execution guide, constraints, and Definition of Done for Phase 2. Implemented.
- `implementation/IMPLEMENTATION_REPORT.md`: Summary of what have been implemented.
- **Active Playbook**: `implementation/Phase5_phase6_build_playbook.md`


**3. Business & Functional Logic:**
- `docs/manifesto.md`: The investment strategy, wave triggers, and constraints.
- `docs/design/functional_architecture.md`: Service boundaries, UI/API interactions, and traceability.

**4. Data & Technical Models:**
- `docs/design/conceptual_data_model.md`: Domain objects, lifecycles (Stream vs Snapshot), and relationships.
- `docs/design/logical_data_model.md`: Tables, keys, and logical invariants.
- `docs/design/pdm/physical_data_model_v2.md`: JSONB rules, indexing strategy, and migration approach.
- `docs/design/high_level_technical_design.md`: The Docker Compose topology, FastAPI structure, and Postgres stack.

Never guess the database schema, functional requirements, or architectural boundaries. Always refer back to these documents. If a requirement is ambiguous, pause and ask me for clarification before writing code.

# Environment Architecture
OpenCode/OmO runs on an Ubuntu VM. The authoritative runtime (Docker daemon) is on an LXC container reachable as `docker-dev` over SSH. The working tree is shared via NFS at `~/projects` on both hosts.

## Execution Rules
1. **File editing:** Edit files locally in the repo working tree (on the Ubuntu VM path).
2. **Docker commands:** Run `docker` and `docker compose` normally. `DOCKER_HOST` routes them to `docker-dev`.
3. **Build/test/lint:** MUST execute against the docker-dev runtime (prefer containerized execution).
   - Preferred: `docker compose run --rm <service> <command>`
   - If you must run directly on the LXC OS: `ssh docker-dev "cd ~/projects/<repo> && <command>"`

## Examples
- Tests via Compose: `docker compose run --rm app npm test`
- LXC host command: `ssh docker-dev "cd ~/projects/my-app && pytest -q"`