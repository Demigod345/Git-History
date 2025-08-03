# Git Commit Rewriter

A Python tool for rewriting Git commit dates to simulate realistic work patterns within specified time ranges.

## Features

- Rewrite commit dates to fall within business hours
- Configurable work hours and date ranges
- Skip weekends automatically
- Add time jitter for realistic patterns
- Change author name and email
- Automatic backup creation
- Progress tracking during rewrite operations

## Installation

No installation required. Simply download the script and ensure you have Python 3.6+ installed.

## Usage

### Basic Usage

```bash
# Rewrite the last 10 commits to dates between Jan 1-31, 2024
./git_commit_rewritte.py --commits 10 --start-date 2024-01-01 --end-date 2024-01-31
```

### Advanced Usage

```bash
# Rewrite with custom work hours, author info, and time variation
./git_commit_rewritte.py \
  --repo /path/to/repo \
  --commits 5 \
  --start-date 2024-01-01 \
  --end-date 2024-01-31 \
  --work-start 10:00 \
  --work-end 16:00 \
  --jitter 30 \
  --author-name "John Doe" \
  --author-email "john@example.com"
```

### Rewrite All Commits

```bash
# Rewrite all commits in the repository
./git_commit_rewritte.py --all --start-date 2024-01-01 --end-date 2024-12-31
```

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `--repo`, `-r` | Git repository path | Current directory |
| `--commits`, `-c` | Number of recent commits to rewrite | Required (or --all) |
| `--all` | Rewrite all commits in repository | - |
| `--start-date`, `-s` | Start date (YYYY-MM-DD) | Required |
| `--end-date`, `-e` | End date (YYYY-MM-DD) | Required |
| `--work-start` | Work start time (HH:MM) | 09:00 |
| `--work-end` | Work end time (HH:MM) | 17:00 |
| `--jitter` | Time variation in minutes | 15 |
| `--author-name` | New author name | Current author |
| `--author-email` | New author email | Current email |
| `--no-backup` | Skip backup creation | Creates backup |

## Important Notes

⚠️ **Warning**: This tool modifies Git history. Always create backups before use.

- The tool automatically creates a backup branch before rewriting
- Commits are distributed randomly within the specified date range
- Only weekdays are used (weekends are skipped)
- Time jitter adds realistic variation to commit times
- Use `git push --force-with-lease` if commits were already pushed to remote
- If `git push --force-with-lease` fails, try `git push --force` as a last resort, but be aware this may overwrite changes on the remote. Always coordinate with your team before using force push.

## Requirements

- Python 3.6+
- Git repository
- Unix-like environment (Linux, macOS, WSL)

## License

This tool is provided as-is for educational and development purposes. Use responsibly and in accordance with your organization's policies.