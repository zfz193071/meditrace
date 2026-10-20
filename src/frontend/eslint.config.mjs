import nextPlugin from "@next/eslint-plugin-next";
import hooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

export default [
  { ignores: [".next/**", "next-env.d.ts", "lib/referral-api/generated.d.ts"] },
  ...tseslint.configs.recommended,
  {
    plugins: { "@next/next": nextPlugin, "react-hooks": hooks },
    rules: {
      ...nextPlugin.configs.recommended.rules,
      ...nextPlugin.configs["core-web-vitals"].rules,
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
    },
  },
  {
    // Legacy routes are retired in MT-21; do not mix a chat rewrite into MT-01.
    files: ["app/page.tsx", "app/chat/**/*.tsx", "app/history/**/*.tsx", "app/verify/**/*.tsx", "lib/api.ts", "components/**/*.tsx", "__tests__/**/*.tsx", "__tests__/lib/api.test.ts"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unused-vars": "warn",
    },
  },
  {
    files: ["*.config.js"],
    rules: { "@typescript-eslint/no-require-imports": "off" },
  },
];
