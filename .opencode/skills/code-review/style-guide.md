---
modified: Sat, 27th December 2025 11:42
---

# Project Style Rules

## General

1. **Async/Await:** Always use `async/await` instead of raw Promises or callbacks.
2. **Error Handling:** All external API calls and database interactions must be wrapped in `try/catch` blocks.
3. **Logging:** Use the project's standardized `Logger` class. Do not use `print()` or `console.log`.

## TypeScript / JavaScript

1. **Types:** Strict typing is required. The use of `any` is strictly forbidden unless absolutely necessary (and must be commented).
2. **Immutability:** Prefer `const` over `let`. Avoid `var` entirely.

## Python

1. **Type Hints:** All function signatures must include type hints (PEP 484).
2. **Docstrings:** Use Google Style docstrings for all public modules, functions, classes, and methods.

---

created: Sat, 27th December 2025 11:40
modified: Sat, 27th December 2025 11:40
