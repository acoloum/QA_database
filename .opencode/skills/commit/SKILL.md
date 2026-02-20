---
name: commit
description: Create well-formatted git commits following conventional commit standards. Use when committing changes, writing commit messages, or asked to commit code.
---

# Commit Skill

## Instructions

1. **Check Current Status**

   ```bash
   git status
   git diff --stat
   ```

2. **Review Changes**

   ```bash
   git diff           # Unstaged changes
   git diff --staged  # Staged changes
   ```

3. **Stage Relevant Files**
   - Only stage related changes
   - Don't mix unrelated changes

4. **Determine Commit Type**

   | Type       | When to Use                           |
   | ---------- | ------------------------------------- |
   | `feat`     | New feature                           |
   | `fix`      | Bug fix                               |
   | `docs`     | Documentation only                    |
   | `style`    | Formatting (no logic change)          |
   | `refactor` | Code restructure (no behavior change) |
   | `perf`     | Performance improvement               |
   | `test`     | Adding/updating tests                 |
   | `build`    | Build system changes                  |
   | `ci`       | CI configuration                      |
   | `chore`    | Other (dependencies, etc.)            |

5. **Determine Scope** (Optional)
   - Feature name: `auth`, `user`, `payment`
   - Module name: `api`, `web`, `core`
   - Component: `button`, `modal`

6. **Write Commit Message**

## Commit Message Format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Rules

- Use imperative mood: "add" not "added"
- Lowercase first letter
- No period at end
- Max 72 characters for first line
- Body explains WHY, not WHAT

## Examples

### Simple Commit

```bash
git add src/auth/login.ts
git commit -m "feat(auth): add Google OAuth login"
```

### With Body

```bash
git commit -m "fix(auth): handle expired token gracefully

The previous implementation threw an unhandled error when tokens expired.
Now we catch the error and redirect to login with a message.

Fixes #123"
```

### Breaking Change

```bash
git commit -m "feat(api)!: change user response structure

BREAKING CHANGE: The 'name' field is now split into 'firstName' and 'lastName'.
Migration guide available in docs/migrations/v2.md"
```

### Multiple Files

```bash
# Stage related files
git add src/auth/login.ts src/auth/types.ts src/auth/login.test.ts

# One commit for related changes
git commit -m "feat(auth): implement email OTP login

- Add sendOTP function
- Add verifyOTP function
- Add input validation
- Add unit tests"
```

## Anti-Patterns

### ❌ Bad Commits

```bash
# Too vague
git commit -m "fix bug"
git commit -m "update"
git commit -m "WIP"

# Too long
git commit -m "Added new login feature with Google OAuth support and also fixed some bugs in the authentication flow and updated the tests"

# Wrong type
git commit -m "feat: fix login bug"  # Should be 'fix'

# Mixed changes
git commit -m "feat: add login and fix navbar and update docs"
```

### ✅ Good Commits

```bash
# Clear and specific
git commit -m "fix(auth): prevent duplicate OTP requests"

# Proper scope
git commit -m "test(auth): add unit tests for login service"

# Atomic changes
git commit -m "refactor(auth): extract validation to separate module"
```

## Verification

After committing:

```bash
# Check commit was created
git log --oneline -1

# Verify files included
git show --stat HEAD
```
