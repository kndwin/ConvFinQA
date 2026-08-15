# Route module guide

Route modules are thin adapters. Export `Route` from `createFileRoute` or
`createRootRoute`, delegate rendering to an imported `.page` or `.ui` component,
and keep API and query imports out of routes. Use a
`.page` component when orchestration is needed and keep `.ui` components props-only.
