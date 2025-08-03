#!/usr/bin/env python3

import subprocess
import argparse
import random
import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict


class GitCommitRewriter:
    def __init__(self, start_date: str, end_date: str, repo_path: str = ".",
                 work_start: str = "09:00", work_end: str = "17:00", jitter_minutes: int = 15,
                 author_name: str = None, author_email: str = None):
        
        self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d")
        self.repo_path = os.path.abspath(repo_path)
        self.work_start = datetime.strptime(work_start, "%H:%M").time()
        self.work_end = datetime.strptime(work_end, "%H:%M").time()
        self.jitter_minutes = jitter_minutes
        self.author_name = author_name
        self.author_email = author_email

        if self.start_date >= self.end_date:
            raise ValueError("Start date must be before end date")
        if not os.path.exists(self.repo_path):
            raise ValueError(f"Repository path does not exist: {self.repo_path}")

    def _run_git_command(self, cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, cwd=self.repo_path, **kwargs)

    def check_git_repo(self) -> bool:
        try:
            self._run_git_command(["git", "rev-parse", "--git-dir"], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def get_recent_commits(self, count: int = None) -> List[str]:
        try:
            cmd = ["git", "log", "--format=%H"]
            if count is not None:
                cmd.insert(2, f"--max-count={count}")
            
            result = self._run_git_command(cmd, check=True, capture_output=True, text=True)
            return result.stdout.strip().split('\n') if result.stdout.strip() else []
        except subprocess.CalledProcessError:
            return []

    def generate_random_work_datetime(self) -> datetime:
        date_range = (self.end_date - self.start_date).days
        random_days = random.randint(0, date_range)
        random_date = self.start_date + timedelta(days=random_days)

        while random_date.weekday() >= 5:
            random_date = self.start_date + timedelta(days=random.randint(0, date_range))

        work_start_minutes = self.work_start.hour * 60 + self.work_start.minute
        work_end_minutes = self.work_end.hour * 60 + self.work_end.minute
        random_minutes = random.randint(work_start_minutes, work_end_minutes)

        jitter = random.randint(-self.jitter_minutes, self.jitter_minutes)
        random_minutes = max(work_start_minutes, min(work_end_minutes, random_minutes + jitter))

        random_hour = random_minutes // 60
        random_minute = random_minutes % 60

        return random_date.replace(hour=random_hour, minute=random_minute, second=0, microsecond=0)

    def build_env_filter_script(self, commit_date_map: Dict[str, datetime], total_commits: int) -> str:
        progress_file = os.path.join(self.repo_path, ".git", "rewrite_progress")
        
        script_parts = [
            f'PROGRESS_FILE="{progress_file}"',
            f'TOTAL_COMMITS={total_commits}',
            '',
            'if [ ! -f "$PROGRESS_FILE" ]; then',
            '    echo "0" > "$PROGRESS_FILE"',
            'fi',
            'CURRENT_COUNT=$(cat "$PROGRESS_FILE")',
            'CURRENT_COUNT=$((CURRENT_COUNT + 1))',
            'echo "$CURRENT_COUNT" > "$PROGRESS_FILE"',
            '',
            '# Progress bar',
            'BAR_WIDTH=30',
            'FILLED=$((CURRENT_COUNT * BAR_WIDTH / TOTAL_COMMITS))',
            'BAR=$(printf "%0.s#" $(seq 1 $FILLED))',
            'EMPTY=$((BAR_WIDTH - FILLED))',
            'BAR="$BAR$(printf "%0.s-" $(seq 1 $EMPTY))"',
            'PERCENT=$((CURRENT_COUNT * 100 / TOTAL_COMMITS))',
            'printf "\\r[%s] %d%% (%d/%d)" "$BAR" "$PERCENT" "$CURRENT_COUNT" "$TOTAL_COMMITS" > /dev/tty',
            '',
            'if [ "$CURRENT_COUNT" -eq "$TOTAL_COMMITS" ]; then',
            '    printf "\\n" > /dev/tty',
            '    rm -f "$PROGRESS_FILE"',
            'fi',
            '',
            '# Commit date mapping'
        ]
        
        for i, (commit_hash, new_date) in enumerate(commit_date_map.items()):
            git_date = new_date.strftime("%Y-%m-%d %H:%M:%S")
            condition = "if" if i == 0 else "elif"
            
            script_parts.append(f'{condition} [ "$GIT_COMMIT" = "{commit_hash}" ]; then')
            script_parts.append(f'    export GIT_AUTHOR_DATE="{git_date}"')
            script_parts.append(f'    export GIT_COMMITTER_DATE="{git_date}"')
            
            if self.author_name:
                script_parts.append(f'    export GIT_AUTHOR_NAME="{self.author_name}"')
                script_parts.append(f'    export GIT_COMMITTER_NAME="{self.author_name}"')
            
            if self.author_email:
                script_parts.append(f'    export GIT_AUTHOR_EMAIL="{self.author_email}"')
                script_parts.append(f'    export GIT_COMMITTER_EMAIL="{self.author_email}"')
        
        script_parts.append('fi')
        return '\n'.join(script_parts)

    def rewrite_commits(self, commit_count: int = None, create_backup: bool = True) -> bool:
        if not self.check_git_repo():
            print(f"Error: Not a Git repository: {self.repo_path}")
            return False

        commits = self.get_recent_commits(commit_count)
        if not commits:
            print("No commits found to rewrite")
            return False

        print(f"Found {len(commits)} commits to rewrite")

        if create_backup:
            self._create_backup()

        new_dates = [self.generate_random_work_datetime() for _ in range(len(commits))]
        new_dates.sort()

        commit_date_map = {}
        for i, commit_hash in enumerate(commits):
            date_index = len(commits) - 1 - i
            commit_date_map[commit_hash] = new_dates[date_index]

        env_filter_script = self.build_env_filter_script(commit_date_map, len(commits))
        
        # Clean up any existing progress file
        progress_file = os.path.join(self.repo_path, ".git", "rewrite_progress")
        if os.path.exists(progress_file):
            os.remove(progress_file)
        
        print("Rewriting commits...")
        try:
            self._run_git_command(
                ["git", "filter-branch", "-f", "--env-filter", env_filter_script],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True
            )
            print(f"Successfully rewrote {len(commits)} commits!")
            return True
        except subprocess.CalledProcessError as e:
            print(f"\nError during rewrite: {e}")
            # Clean up progress file on error
            if os.path.exists(progress_file):
                os.remove(progress_file)
            return False

    def _create_backup(self):
        try:
            result = self._run_git_command(
                ["git", "branch", "--show-current"],
                check=True, capture_output=True, text=True
            )
            current_branch = result.stdout.strip()
            backup_name = f"backup-{current_branch}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            
            self._run_git_command(["git", "branch", backup_name], check=True, capture_output=True)
            print(f"Created backup branch: {backup_name}")
        except subprocess.CalledProcessError:
            print("Warning: Could not create backup branch")


def main():
    parser = argparse.ArgumentParser(description="Rewrite Git commit dates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  %(prog)s --repo /path/to/repo --commits 5 --start-date 2024-01-01 --end-date 2024-01-31 --work-start 10:00 --work-end 16:00 --jitter 6 --author-name "John Doe" --author-email "john@example.com"
        """)

    parser.add_argument("--repo", "-r", default=".", help="Git repository path")

    commit_group = parser.add_mutually_exclusive_group(required=True)
    commit_group.add_argument("--commits", "-c", type=int, help="Number of recent commits to rewrite")
    commit_group.add_argument("--all", action="store_true", help="Rewrite all commits in the repository")

    parser.add_argument("--start-date", "-s", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", "-e", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--work-start", default="09:00", help="Work start time (HH:MM)")
    parser.add_argument("--work-end", default="17:00", help="Work end time (HH:MM)")
    parser.add_argument("--jitter", type=int, default=15, help="Time variation in minutes")
    parser.add_argument("--author-name", help="New author name")
    parser.add_argument("--author-email", help="New author email")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup creation")

    args = parser.parse_args()

    try:
        rewriter = GitCommitRewriter(
            start_date=args.start_date,
            end_date=args.end_date,
            repo_path=args.repo,
            work_start=args.work_start,
            work_end=args.work_end,
            jitter_minutes=args.jitter,
            author_name=args.author_name,
            author_email=args.author_email
        )

        # Determine commit count
        commit_count = None if args.all else args.commits
        
        if args.all:
            print("WARNING: This will modify ALL commits in the repository!")
        else:
            print(f"WARNING: This will modify the last {args.commits} commits!")
        
        print("This will modify Git history!")
        response = input("Continue? (y/n): ")
        if response.lower() in ['y', 'yes']:
            success = rewriter.rewrite_commits(commit_count, not args.no_backup)
            if success:
                print("Warning: Use 'git push --force-with-lease' if commits were already pushed")
        else:
            print("Cancelled")

    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCancelled")
        sys.exit(1)


if __name__ == "__main__":
    main()
