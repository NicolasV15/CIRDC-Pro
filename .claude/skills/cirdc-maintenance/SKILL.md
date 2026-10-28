---
name: cirdc-maintenance
description: Set up CIRDC-Pro on a new computer, validate a private local or SSH database target, and run resumable IEEE metadata updates and recovery.
---

Read and follow the [shared workflow](../../../.agents/skills/cirdc-maintenance/SKILL.md)
before acting. It is the canonical workflow used by both Codex and Claude Code.
Read the repository [agent contract](../../../AGENTS.md) as well.
For new-computer setup or target selection, use the shared
[onboarding procedure](../../../.agents/skills/cirdc-maintenance/references/new-computer.md).
Use the project `sh tools/cirdc` interface. Deployment values stay in private
configuration outside Git; never suppress database recognition or identity checks.
