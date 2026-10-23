# Contributing to AskLess

AskLess explores how executable evidence can reduce interruptions in agent workflows. The current implementation is a bounded contact CSV adapter. Contributions that make the mechanism clearer, more reliable, or easier to evaluate are welcome.

## Useful starting points

- Add a small adapter with explicit choices, controlled execution, and observable results.
- Contribute synthetic examples where choices interact and a local comparison would miss a meaningful difference.
- Design an evaluation that measures human decision time alongside task quality.
- Improve accessibility, localization, or the evidence inspection experience.

For a new adapter or architectural change, open an issue describing the task, policy contracts, execution limits, and what counts as an observable difference. An example input and expected outcomes help make the design concrete.

## Work locally

Follow [README.md](README.md#develop) for installation and checks. Python uses type hints, Ruff, isort, and ty. The workbench and website use TypeScript and React. Add behavioral tests for changed decision semantics, persistence, API behavior, and stateful UI interactions.

Use synthetic data in examples and tests. Keep API keys, provider response bodies, local databases, and private task descriptions out of patches and screenshots.

## Submit a change

Create a focused branch, explain the user-visible change, and include the checks you ran. Rebase onto the current default branch before submitting a pull request. Keep history linear; repository merges use **Rebase and merge**.

Commit messages use this format (subject at most 50 characters; body lines at most 72):

```text
[feat] Implement descriptive change

Root cause: NA
Solution: Describe the behavior and why it changes.
Risks: Describe material limitations, or NA.
Dependency: List requirements, or NA.
Links: Reference the related issue, or NA.
```

Types include `feat`, `bug`, `doc`, `style`, `refactor`, and `chore`. Use `[bug] Fix ...` for bug fixes.

## Website changes

See [docs/website.md](docs/website.md). Keep product claims tied to implemented behavior and reproducible examples. Changes to the CSV executor may require regenerating the website sample.
