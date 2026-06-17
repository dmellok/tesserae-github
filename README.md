# Tesserae GitHub widgets

CI status, PR queue, contributions, release feed, and activity widgets for [Tesserae](https://github.com/dmellok/tesserae), the e-ink dashboard companion.

Bundle of 7 widgets:

- **GitHub Core** (`github_core`), shared token + repo settings. No cell of its own; the other widgets read from it.
- **GitHub Actions** (`github_actions`), CI run status for a repo's recent workflows.
- **GitHub Activity** (`github_activity`), commit / PR / issue activity feed.
- **GitHub Contributions** (`github_contributions`), contributor's contribution graph.
- **GitHub PR Queue** (`github_pr_queue`), open PRs for review.
- **GitHub Releases** (`github_releases`), latest releases for tracked repos.
- **GitHub Repo** (`github_repo`), repo summary card (stars, forks, recent activity).

## Install

Settings → Widgets → Browse community widgets → Install. After restart, paste a GitHub personal access token (PAT) under Settings → Widgets → GitHub Core. A PAT with `repo` and `read:user` scopes is enough for most widgets; `read:org` lets you read org repos.

## Why these moved out of the bundle

Developer-focused widgets that need a personal access token. The typical Tesserae user, especially a non-dev HA user, never enables them. Bundling 7 widgets per install was inflating the picker. Marketplace is the right home.

## License

AGPL-3.0-or-later. See [LICENSE](./LICENSE).
