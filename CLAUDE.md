# SLC-SIG Platform

## Skills

- **docker-django-ops** (`.claude/skills/docker-django-ops/SKILL.md`) — Docker + Django + MySQL production operations. Trigger: `/docker-django-ops`

  Activate automatically when the user mentions: Docker builds/rebuilds, docker-compose, container restarts, MySQL volumes, health checks, local↔prod parity, rollback, or any Django+MySQL+Docker operational problem.

  When the user types `/docker-django-ops`, invoke the Skill tool with `skill: "docker-django-ops"` before doing anything else.

## Graphify

Knowledge graph output lives in `graphify-out/`. Run `/graphify query "<question>"` to query the codebase graph.
