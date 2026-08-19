import { definePlugin, defineRule } from "@oxlint/plugins";

const guide = "lint/module.ui.md";
const forbidden = ["openapi-fetch", "@/platform/api", "@/platform/query"];
const forbiddenNames = new Set(["openapiClient", "queryClient"]);

function isForbidden(source: string) {
  return forbidden.some((item) => source === item || source.startsWith(`${item}/`));
}

const rule = defineRule({
  create(context) {
    return {
      Program(node: any) {
        if (!context.filename.includes("/src/module/") || !context.filename.endsWith(".ui.tsx"))
          return;
        for (const statement of node.body) {
          if (statement.type === "ImportDeclaration") {
            const source = statement.source.value as string;
            if (isForbidden(source)) {
              context.report({
                node: statement,
                message: `UI modules must not import ${source}; read ${guide}. This couples rendering to platform data access.`,
              });
            }
            for (const specifier of statement.specifiers ?? []) {
              if (forbiddenNames.has(specifier.imported?.name ?? "")) {
                context.report({
                  node: specifier,
                  message: `UI modules must not import ${specifier.imported.name}; read ${guide}. Use a feature query boundary instead.`,
                });
              }
            }
          }
          if (statement.type !== "ExportNamedDeclaration" || statement.exportKind === "type")
            continue;
          const declaration = statement.declaration;
          const declarations =
            declaration?.type === "VariableDeclaration"
              ? declaration.declarations
              : declaration?.type === "FunctionDeclaration" ||
                  declaration?.type === "ClassDeclaration"
                ? [declaration]
                : [];
          for (const item of declarations) {
            const id = item.id;
            const name = id?.type === "Identifier" ? id.name : null;
            if (name && !/^[A-Z][A-Za-z0-9]*$/.test(name)) {
              context.report({
                node: id,
                message: `UI component export ${name} must use PascalCase; read ${guide}. Components are named exports and should be recognizable as components.`,
              });
            }
          }
        }
      },
    };
  },
});

export default definePlugin({ meta: { name: "module-ui" }, rules: { boundary: rule } });
