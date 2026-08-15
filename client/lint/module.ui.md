# UI module guide

UI modules (`src/module/**/*.ui.tsx`) render feature data and may use feature query
options, but must not import platform API/query clients. Detail views should remain
props-only; keep router and state-machine orchestration in a sibling `.page.tsx`.
Export component names in PascalCase. When this boundary rule fails, fix the
dependency direction rather than adding an ignore.
