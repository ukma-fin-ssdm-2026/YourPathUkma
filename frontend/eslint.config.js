// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm run lint.
import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import jsxA11y from "eslint-plugin-jsx-a11y";
import security from "eslint-plugin-security";
import { defineConfig, globalIgnores } from "eslint/config";

export default defineConfig([
  globalIgnores(["dist", "src/api/generated", "public/mockServiceWorker.js"]),
  {
    files: ["**/*.{ts,tsx}"],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      jsxA11y.flatConfigs.recommended,
      security.configs.recommended,
    ],
    languageOptions: { globals: globals.browser },
    // `role` на наших компонентах (AppLayout) це роль користувача, а не ARIA-роль.
    rules: { 
      "jsx-a11y/aria-role": ["error", { ignoreNonDOM: true }], 
      "security/detect-object-injection": "off",
    },
  },
]);
