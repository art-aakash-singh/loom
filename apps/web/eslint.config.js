import js from "@eslint/js";
import boundaries from "eslint-plugin-boundaries";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "src/api/generated/schema.d.ts"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: { globals: globals.browser },
    plugins: { "react-hooks": reactHooks },
    rules: reactHooks.configs.recommended.rules,
  },
  {
    // Dependencies point one way: shared -> features -> app. See apps/web/README or CLAUDE.md.
    files: ["src/**/*.{ts,tsx}"],
    plugins: { boundaries },
    settings: {
      "import/resolver": { node: { extensions: [".ts", ".tsx"] } },
      "boundaries/elements": [
        { type: "app", pattern: "src/app/**" },
        { type: "feature", pattern: "src/features/*", capture: ["name"] },
        { type: "shared", pattern: ["src/api/**", "src/lib/**", "src/config/**", "src/hooks/**", "src/utils/**"] },
      ],
      "boundaries/files": [{ category: "test", pattern: "**/*.test.{ts,tsx}" }],
    },
    rules: {
      "boundaries/dependencies": [
        "error",
        {
          default: "disallow",
          policies: [
            // app composes features, but only through their index.ts.
            { from: { element: { type: "app" } }, allow: { to: { element: { types: { anyOf: ["app", "shared"] } } } } },
            { from: { element: { type: "app" } }, allow: { to: { element: { type: "feature", fileInternalPath: "index.ts" } } } },
            { from: { element: { type: "feature" } }, allow: { to: { element: { types: { anyOf: ["shared"] } } } } },
            { from: { element: { type: "shared" } }, allow: { to: { element: { type: "shared" } } } },
          ],
        },
      ],
    },
  },
);
