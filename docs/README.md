# Technical Documentation Index

This directory contains version-controlled technical documentation. It is maintained against explicit source commits and must not replace accepted architecture specifications or tests.

## Architecture

- [System overview and request lifecycle](architecture/system-overview.md)
- [Phase 1B metrics: contracts and integration status](architecture/phase-1b-metrics.md)
- [Phase 1C frontend metrics integration](architecture/phase-1c-frontend-integration.md)

## Development

- [Test strategy and verification evidence](development/testing.md)

## API

- [Analysis History API](api/ANALYSIS_HISTORY_API.md)

## Root-level guides

- [Project overview](../README.md)
- [Development and operations](../DEVELOPMENT.md)
- [Contribution workflow](../CONTRIBUTING.md)
- [Security policy](../SECURITY.md)

## Documentation baseline

The technical documentation reflects the canonical repository baseline on `main` at merge commit `e298ebba14b69a5c494e4b07308d3bd40aae1cd5`, integrating Phase 1C Frontend Metrics Integration via PR #27 (feature branch `feat/phase-1c-metrics-overview` final commit `d6160f1983183273f20f29fc0af960236ac20984`, with implementation checkpoint `9f70e57624aca59017fc5b570e42c67340987260`). The previous backend baseline on `main` was commit `c26fdd36837bc0782c9e840b370f478e306857a2`, containing all six units of Phase 1B.2 (`64adf3d256f04ff43796b933875887b2f34d3179` via PR #26). Phase 1C Units 1–4 are fully implemented, verified, and merged.
