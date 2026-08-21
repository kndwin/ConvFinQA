import * as cloudflare from "@pulumi/cloudflare";
import * as pulumi from "@pulumi/pulumi";

const config = new pulumi.Config();
const backendUrl = config.require("backendUrl");
const accountId = "d549a47e154c5803519d3c312cfa6d1c";

const pages = new cloudflare.PagesProject("convfinqa", {
  accountId,
  name: "convfinqa",
  productionBranch: "main",
  source: {
    type: "github",
    config: {
      owner: "kndwin",
      ownerId: "22161029",
      repoName: "ConvFinQA",
      repoId: "1334933457",
      productionBranch: "main",
      productionDeploymentsEnabled: true,
      previewDeploymentSetting: "all",
      pathIncludes: ["client/browser/*", "infra/prod/cloudflare.ts"],
      prCommentsEnabled: false,
    },
  },
  buildConfig: {
    buildCommand: "pnpm build",
    destinationDir: "dist",
    rootDir: "client/browser",
    buildCaching: true,
  },
  deploymentConfigs: {
    preview: {
      envVars: {
        VITE_API_BASE_URL: { type: "plain_text", value: backendUrl },
        NODE_VERSION: { type: "plain_text", value: "22" },
        PNPM_VERSION: { type: "plain_text", value: "10.14.0" },
      },
    },
    production: {
      envVars: {
        VITE_API_BASE_URL: { type: "plain_text", value: backendUrl },
        NODE_VERSION: { type: "plain_text", value: "22" },
        PNPM_VERSION: { type: "plain_text", value: "10.14.0" },
      },
    },
  },
});

export const pagesName = pages.name;
export const pagesUrl = pulumi.interpolate`https://${pages.name}.pages.dev`;
