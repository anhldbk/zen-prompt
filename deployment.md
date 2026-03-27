# Deployment Guide

This project is configured to automatically publish to PyPI using GitHub Actions.

## Automatic Publishing

When a new tag (e.g., `v1.2.3`) is pushed to the repository, a GitHub Action is triggered to:

1.  Build the project's wheel and source distributions using `uv`.
2.  Upload the distribution artifacts to PyPI.

### Triggering a Release

To trigger a new release:

1.  Update the version in `pyproject.toml`.
2.  Commit the change.
3.  Create and push a git tag:

```bash
git tag v0.1.0
git push origin v0.1.0
```

## Manual Publishing

If you need to publish manually, you can use `uv`:

```bash
# Build the project
uv build

# Publish to PyPI (requires PyPI credentials or token)
uv publish
```

## GitHub Actions Configuration

The workflow is located at `.github/workflows/publish.yml`. It uses the `pypa/gh-action-pypi-publish` action for secure publishing via Trusted Publishing.

### Prerequisites

To enable Trusted Publishing:

1.  Log in to PyPI and go to your project settings.
2.  Add a new GitHub publisher.
3.  Provide the repository owner, repository name, and the name of the workflow file (`publish.yml`).
4.  Set the environment name to `pypi`.
