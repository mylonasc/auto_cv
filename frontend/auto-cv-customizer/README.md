# Auto CV Frontend

React + TypeScript + Vite frontend for the CV customization workflow.

## Development

From this directory:

```bash
npm install
npm run dev
```

The dev server runs on `http://localhost:5173`.

## Quality checks

```bash
npm run lint
npm run build
```

## End-to-end tests

```bash
npm run test:e2e
```

## Backend API base

The app expects API routes under `/api/v1` (proxied by nginx in Docker and configured in `src/services/api.ts`).
