# Batch

The `batch` command group manages Gemini batch prediction jobs. It lets you submit many prompts at once, monitor progress, and export results.

!!! note
    Batch operations use the Gemini API exclusively. A valid `GEMINI_API_KEY` is required.

## `batch create`

Create a new batch job from inline prompts or a file.

```bash
# Inline prompts
padwan-cli batch create -p "Summarize quantum computing" -p "Explain CRISPR"

# From a JSON file
padwan-cli batch create -f prompts.json -m gemini-2.0-flash -n my-batch
```

| Option | Default | Description |
|---|---|---|
| `-p`, `--prompt` | | Inline prompt (can be repeated) |
| `-f`, `--file` | | Path to a JSON or text file containing prompts |
| `-m`, `--model` | `gemini-2.0-flash` | Model to use |
| `-n`, `--name` | `cli-batch` | Display name for the batch job |

### Input file formats

=== "JSON (string array)"

    ```json
    [
      "What is photosynthesis?",
      "Explain gravity",
      "Summarize the French Revolution"
    ]
    ```

=== "JSON (objects with keys)"

    ```json
    [
      {"prompt": "What is photosynthesis?", "key": "bio-1"},
      {"prompt": "Explain gravity", "key": "physics-1"}
    ]
    ```

=== "Text (one per line)"

    ```text
    What is photosynthesis?
    Explain gravity
    Summarize the French Revolution
    ```

## `batch status`

Check the current status of a batch job.

```bash
padwan-cli batch status -j <job-name>

# Include results if the job is complete
padwan-cli batch status -j <job-name> -r
```

| Option | Default | Description |
|---|---|---|
| `-j`, `--job` | *required* | Batch job name |
| `-r`, `--results` | `false` | Show results if the job has completed |

## `batch list`

List recent batch jobs.

```bash
padwan-cli batch list
padwan-cli batch list -l 20
```

| Option | Default | Description |
|---|---|---|
| `-l`, `--limit` | `10` | Maximum number of jobs to show |

Output is a table with columns: Name, State, Display Name, Model, and Stats (succeeded/total).

## `batch poll`

Poll a batch job until it reaches a terminal state, with a live progress widget in TUI mode.

```bash
padwan-cli batch poll -j <job-name>

# Custom interval and timeout
padwan-cli batch poll -j <job-name> -i 10 -t 300

# Save results to file on completion
padwan-cli batch poll -j <job-name> -o results.json
```

| Option | Default | Description |
|---|---|---|
| `-j`, `--job` | *required* | Batch job name |
| `-i`, `--interval` | `5` | Poll interval in seconds |
| `-t`, `--timeout` | *none* | Maximum wait time in seconds |
| `-r`, `--results` | `true` | Show results on completion |
| `-o`, `--output` | | Save results to file (format inferred from extension) |

## `batch cancel`

Cancel a pending or running batch job.

```bash
padwan-cli batch cancel -j <job-name>
```

| Option | Default | Description |
|---|---|---|
| `-j`, `--job` | *required* | Batch job name to cancel |

## `batch retry`

Identify failed requests from a completed batch and report them for retry.

```bash
padwan-cli batch retry -j <job-name>
```

| Option | Default | Description |
|---|---|---|
| `-j`, `--job` | *required* | Original job name |

The command inspects the original job's responses, identifies requests that returned errors or had no candidates, and lists their keys.

!!! warning
    Retry requires the original prompts to be available. Currently this command reports failed keys but does not automatically re-submit them.

## `batch export`

Export completed batch results to a file.

```bash
padwan-cli batch export -j <job-name> -o results.json
padwan-cli batch export -j <job-name> -o results.csv -f csv
```

| Option | Default | Description |
|---|---|---|
| `-j`, `--job` | *required* | Batch job name |
| `-o`, `--output` | *required* | Output file path |
| `-f`, `--format` | `json` | Output format: `json`, `csv`, or `txt` |

### Export formats

- **json** — structured array with `key`, `content`, `input_tokens`, `output_tokens`, `total_tokens`
- **csv** — tabular with the same fields as columns
- **txt** — plain text with `[key]` headers followed by content
