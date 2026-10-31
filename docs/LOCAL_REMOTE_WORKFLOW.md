# Local development, collection and remote storage

This project uses three independent choices: where source is edited, where
HTTP runs, and where data is stored. Keep the local source checkout for local
network access and debugging. It is not a remote-only materials directory.

## One repository for backend and frontend

The repository root is the shared development entrypoint. `src/cirdc/` owns the
maintained metadata backend; `website/src/cirdc/web/` owns website APIs and
`website/web/` owns the React frontend. `website/` has no nested Git repository:
review and commit both components from the root. The website retains a separate
Python package and lockfile because its compatibility engine and the maintenance
engine currently have different versions. Install them into separate environments.

For a fresh website development environment, run these commands from the root:

```sh
sh tools/web setup
sh tools/web test
sh tools/web build
```

Reuse an existing development environment when present; do not recreate it or
follow a runtime-environment link for setup. Root maintenance setup remains
`sh tools/setup.sh`. Run its tests with `.venv/bin/python -m pytest` from the root.
Keep the two pytest runs separate because both packages use the `cirdc` namespace.
Refresh regular installed packages after source changes; editable development
installs read their corresponding source tree directly.

`tools/web` always selects the website directory and its `.venv-dev`; it does not
install into the maintenance environment or a service environment. `test` runs
both frontend and website API tests, forwarding extra arguments to pytest. `build`
builds frontend assets followed by wheel and source distribution in `website/dist`.
For development serving, `sh tools/web serve --interface reader --host
127.0.0.1 --port 18090` invokes the website CLI with the chosen private config.
A root package build remains the maintenance distribution and does not bundle
the website.

Existing website releases, service environments and private state remain at their
configured deployment locations. A former source path may remain as a compatibility
link to this checkout; edit the canonical source here. The ignored machine context
and `website/.workspace/` locate the existing deployment and verification records.
For an authorized website deployment, set `CIRDC_WEB_ROOT` to that existing deployment
root before calling `sh tools/web deploy RELEASE_ID`. Publication requires an
existing environment, account/index state and a previous wheel for rollback.
The existing configuration must load within the bounded startup check; unavailable
remote storage stops publication before any service is stopped.
It locks the deployment, builds a source snapshot before stopping services, and
installs only that wheel offline without changing dependency or private-provider
versions. Existing service units and drop-ins are retained. Failed activation
restores the previous wheel and release link and checks both listeners.
Moving source
does not itself publish a release, replace a running environment or resume collection.

## Local files

Keep source, tests, Git history and existing package tools in place.
The ignored materials/, artifacts/ and work/ directories hold supplied reference
material, user-facing outputs and temporary work respectively. They do not hold
database credentials, target profiles or collection checkpoints.

The ignored .cirdc/local-workspace file, when present, contains only an absolute
path to private machine context outside Git. That context locates the selected
runtime, target profiles and current task records. .cirdc/active-target continues
to select the existing development CLI/MCP target; do not silently replace it.

## Development and fixed runtimes

- Identify the executable and actual imported package path, not only a version
  string. An editable installation reads the checkout and is for development.
- A fixed collection runtime installs a built wheel in an independent environment.
  Record the wheel digest, source digest, dependencies and interpreter. Prepare
  a new runtime for a changed release instead of reinstalling the old one.
- A worker already running from a normal installed package may remain in its
  current environment until its task stops. Mark that environment with
  .cirdc-runtime-protected and leave its Python, installed package and profile
  unchanged. This is a setup guard, not a scheduler or a process-status marker.
- The existing setup.sh refuses to overwrite a marked environment. For a separate
  development environment, use the project's environment setup facilities with
  a different environment path, or uv venv --python 3.12 .venv-dev followed by
  uv pip install --python .venv-dev/bin/python -e '.[dev]'. Follow the platform's
  interpreter paths. Check existing environments before installing.
- A source-only or documentation change does not require reinstalling the
  environment of a live worker. If application code changes, test the new package
  in isolation and choose a deliberate transition point.
- The existing tools/cirdc and project MCP still use their configured .venv.
  For a separate development environment, invoke its Python with -m cirdc.cli
  and run tests with that interpreter. Do not assume the legacy launcher follows
  a newly created development environment.

## Run a configured local node

Use sh tools/node ROLE with the normal CIRDC arguments. The role resolves the
ignored .cirdc/node-ROLE path pointer to an executable private launcher outside
Git. That launcher selects a fixed Python/package and a private target profile.
It starts the CLI on this computer; its target may store data over SSH.

The launcher is not a new queue or scheduler. Use the existing update/status/resume
workflow for normal maintenance. Existing historical selections use their frozen
repair runtime until verified retirement. Never replace a current task with a newly
created job merely to switch entrypoints.

A role is not an independent network exit. Before starting another local job,
inspect work already using that route and keep its aggregate request budget;
two local processes do not acquire two independent rate allowances.

For a requested local network exit, start the collector locally and use SSH only
for storage or explicit remote work. Route labels do not change public addresses;
verify actual source access when setting up or changing the exit. Keep the
computer awake and connected while its worker runs.

## Preserve a running task

Before a runtime transition, establish the exact process, start time, task or
manifest, profile and checkpoint paths. Inspect the existing status and pending
exports. Do not use an observation timeout as evidence that the worker stopped.

Prefer leaving a healthy job in its verified environment. When a change requires
a restart and the user has authorized it, stop gracefully, confirm termination and
saved progress, then resume the same job or collector manifest/output through
the new runtime. Preserve existing scope, budgets, attempts and network settings.
Confirm the new process and advancing progress before claiming recovery.

Use database identity checks and the applicable cooperative locks. Separate local
fetch progress, shared applied counts and pending JSON publication; completion of
one does not prove completion of the others. Do not copy whole shared datasets
into the local source checkout.

## Cross-node development

For each change, select a primary development checkout. Use Git commits or a
versioned package to deliver the change to other nodes, preserving their private
configuration. A running collector keeps its existing release until an explicit
transition. Test backend changes on their intended server and deployment target;
changing source does not itself authorize replacing a running shared service.
