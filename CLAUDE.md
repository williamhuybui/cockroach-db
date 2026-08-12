# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

This is **not** the CockroachDB source code. It is a team repo for the [CockroachDB × AWS Hackathon — Build with Agentic Memory](https://cockroachdb-ai.devpost.com/) (deadline Aug 18, 2026).

**Hackathon requirement:** build an agentic app using CockroachDB as the persistent memory layer, deployed on AWS. Submissions must use **≥2 CockroachDB tools** (Managed MCP Server, Distributed Vector Indexing, ccloud CLI, or the open-source Agent Skills Repo) and **≥1 AWS service** (e.g. Bedrock, Lambda, ECS/EKS, S3, SageMaker). Judging weighs agentic memory design, technical implementation, real-world impact, production readiness, and creativity — so pitches and the eventual build should foreground CockroachDB doing real memory work, not toy queries.

Currently the repo holds pitch/ideation docs, meeting notes, and a placeholder FastAPI backend (`src/`) — the real agent + CockroachDB integration is not yet built.

## Structure

- `ideation/` — one Markdown pitch doc per candidate hackathon idea (problem statement, target user, solution flow, UI mockup in ASCII, agent architecture, CockroachDB data model, AWS technology mapping, safety boundaries).
- `meeting/` — meeting notes (`MM-DD-YYYY.md`) and `role-responsibility.md`, which defines team roles and the driver/passenger ownership model per focus area (PM, ideation, frontend, backend, infra, research, presentation).


## Code style

- Every source file should start with a module-level docstring summarizing what the file does.

## Team context

Roles are defined in `meeting/role-responsibility.md`: Huy (Captain/Fullstack), Hieu (Solution Architect/Data Admin), Ha (R&D Lead), Tri (PM/Coordinator). When updating meeting notes, follow the existing format in `meeting/07-17-2026.md` (agenda with time-boxed sections, per-person idea summaries linking to their `ideation/` doc).
