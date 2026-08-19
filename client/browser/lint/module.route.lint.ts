import { definePlugin, defineRule } from "@oxlint/plugins";

const guide = "lint/module.route.md";
const forbidden = ["openapi-fetch", "@/platform/api", "@/platform/query"];

function isForbidden(source: string) {
  return forbidden.some((item) => source === item || source.startsWith(`${item}/`));
}

const rule = defineRule({
  create(context) {
    return {
      Program(node: any) {
        if (!context.filename.endsWith(".route.ts") && !context.filename.endsWith(".route.tsx"))
          return;
        const uiImports = new Set<string>();
        let routeFound = false;
        let delegated = false;
        for (const statement of node.body) {
          if (statement.type === "ImportDeclaration") {
            const source = statement.source.value as string;
            if (isForbidden(source))
              context.report({
                node: statement,
                message: `Routes must not import ${source}; read ${guide}. Routes delegate data access to page boundaries.`,
              });
            if (/\.(?:page|ui)(?:\.[^/]*)?$/.test(source)) {
              for (const specifier of statement.specifiers ?? [])
                uiImports.add(specifier.local.name);
            }
          }
          if (statement.type !== "ExportNamedDeclaration") continue;
          const declaration = statement.declaration;
          if (declaration?.type !== "VariableDeclaration") continue;
          for (const declarator of declaration.declarations) {
            if (declarator.id?.name !== "Route") continue;
            const call = declarator.init;
            if (call?.type !== "CallExpression") continue;
            const callee = call.callee?.name ?? call.callee?.callee?.name;
            if (callee !== "createFileRoute" && callee !== "createRootRoute") continue;
            routeFound = true;
            const options = call.arguments?.[0];
            for (const property of options?.properties ?? []) {
              if (property.key?.name === "component" && uiImports.has(property.value?.name))
                delegated = true;
            }
          }
        }
        if (!routeFound)
          context.report({
            node,
            message: `Route modules must export Route initialized by createFileRoute or createRootRoute; read ${guide}. This keeps route discovery and typing explicit.`,
          });
        else if (!delegated)
          context.report({
            node,
            message: `Route rendering must delegate to an imported page or UI component; read ${guide}. Keep JSX and page behavior out of route modules.`,
          });
      },
    };
  },
});

export default definePlugin({ meta: { name: "module-route" }, rules: { boundary: rule } });
