---
description: 
---

# Commit Message Conventions (Conventional Commits)

All commit messages must follow the Conventional Commits specification. They are validated via `commitlint.config.js`.

* **Format:** `<type>(<scope>): <subject>` (e.g., `fix(core): resolve db connection leak`)
* **Allowed Types:**
  * `feat`: A new feature
  * `fix`: A bug fix
  * `docs`: Documentation only changes
  * `style`: Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc)
  * `refactor`: A code change that neither fixes a bug nor adds a feature
  * `perf`: A code change that improves performance
  * `test`: Adding missing tests or correcting existing tests
  * `build`: Changes that affect the build system or external dependencies
  * `ci`: Changes to CI configuration files and scripts
  * `chore`: Other changes that don't modify src or test files
  * `revert`: Reverts a previous commit

* **Rules:**
  * The type must be lowercase.
  * The subject must not be empty.
  * Write the subject in the imperative, present tense: "change", not "changed" or "changes".
  * Keep the subject line short (ideally under 72 characters).