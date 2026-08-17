set quiet
set dotenv-load

# List available recipes
default:
    @just --list

# Interactive chat in the terminal (.env keys loaded automatically)
chat *args:
    uv run python -m padwan_cli chat start {{ args }}

# Run unit tests
[group('dev')]
test *args:
    uv run pytest {{ args }}

# Type check
[group('dev')]
check:
    uv run pyright padwan_cli/

# Lint
[group('dev')]
lint:
    uv run ruff check padwan_cli/ tests/

# Format
[group('dev')]
fmt:
    uv run ruff format padwan_cli/ tests/

# Fix lint issues where possible
[group('dev')]
fix:
    uv run ruff check --fix padwan_cli/ tests/
    uv run ruff format padwan_cli/ tests/

# Lint + type check + test
[group('dev')]
ci: lint check test

# Serve docs locally with hot reload
[group('docs')]
docs:
    uv run --group docs zensical serve -f zensical.toml

# Build docs
[group('docs')]
docs-build:
    uv run --group docs zensical build -f zensical.toml

# Record the VHS demo tape
[group('docs')]
record:
    vhs docs/static/chat.tape

# Bump version (commitizen — updates pyproject.toml and CHANGELOG)
[group('release')]
bump *args:
    uv run --group bump cz bump {{ args }}
