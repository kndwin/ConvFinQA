import { defineRailway, github, postgres, project, service } from "railway";

const PROJECT_ID = "97155b4d-6e91-45e6-b6b8-1ea9d826ff06";

export default defineRailway((ctx) => {
  if (ctx.projectId && ctx.projectId !== PROJECT_ID) {
    throw new Error(`Refusing to plan against unexpected Railway project ${ctx.projectId}`);
  }
  if (ctx.projectName && ctx.projectName !== "hospitable-insight") {
    throw new Error(`Refusing to plan against unexpected Railway project ${ctx.projectName}`);
  }

  const database = postgres("Postgres");
  return project("hospitable-insight", {
    environments: ["production"],
    resources: [
      database,
      service("ConvFinQA", {
        source: github("kndwin/ConvFinQA", {
          branch: "main",
          rootDirectory: "server/core",
        }),
        build: {
          buildCommand: "uv sync --frozen --no-dev",
        },
        deploy: {
          preDeployCommand: ["uv run --no-sync alembic upgrade head"],
          startCommand: "uv run --no-sync uvicorn src.main:app --host 0.0.0.0 --port $PORT",
          healthcheckPath: "/health",
          numReplicas: 1,
        },
        variables: {
          DATABASE_URL: database.env.DATABASE_URL,
          OPENAI_API_KEY: { preserveExisting: true },
          LOGFIRE_ENVIRONMENT: "production",
          CORS_ORIGINS: "https://convfinqa.pages.dev",
        },
      }),
    ],
  });
});
