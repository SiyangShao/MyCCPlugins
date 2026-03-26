# Commit

Create a conventional commit message for staged changes.

1. Run `git diff --staged` to understand the changes.
2. Write a conventional commit message: `<type>(<scope>): <summary>`.
   - Types: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`, `style`.
   - Keep the summary under 72 characters.
3. Run `git commit -m "<message>"`.

Do not add a trailing period. Do not add `Co-Authored-By` unless the user asks.
