#!/usr/bin/env python3
"""
Git Commit Date Rewriter - Optimized Version

This script modifies the dates of recent Git commits to make them appear as if they were made:
1. Within a specific date range (configurable start/end dates)
2. During work hours (configurable daily time window)
3. With realistic randomness (±15 minute jitter)

Usage:
    python git_rewriter.py --commits 10 --start-date 2024-01-01 --end-date 2024-01-31
    python git_rewriter.py --help

Requirements:
    - Git repository
    - Python 3.6+
"""

import subprocess
import argparse
import random
import sys
from datetime import datetime, timedelta, time
from typing import List, Tuple, Dict
import re


class GitCommitRewriter:
    def __init__(self, start_date: str, end_date: str, repo_path: str = ".",
                 work_start: str = "09:00", work_end: str = "17:00", jitter_minutes: int = 15,
                 author_name: str = None, author_email: str = None):
        """
        Initialize the Git commit rewriter.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            repo_path: Path to the Git repository (default: current directory)
            work_start: Work day start time in HH:MM format
            work_end: Work day end time in HH:MM format
            jitter_minutes: Random variation in minutes (±)
            author_name: New author name (optional)
            author_email: New author email (optional)
        """
        import os

        self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d")
        self.repo_path = os.path.abspath(repo_path)
        self.work_start = datetime.strptime(work_start, "%H:%M").time()
        self.work_end = datetime.strptime(work_end, "%H:%M").time()
        self.jitter_minutes = jitter_minutes
        self.author_name = author_name
        self.author_email = author_email

        # Validate date range
        if self.start_date >= self.end_date:
            raise ValueError("Start date must be before end date")

        # Validate repository path
        if not os.path.exists(self.repo_path):
            raise ValueError(f"Repository path does not exist: {self.repo_path}")

        # Store original working directory
        self.original_cwd = os.getcwd()

    def _run_git_command(self, cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
        """Run a git command in the repository directory."""
        return subprocess.run(cmd, cwd=self.repo_path, **kwargs)

    def check_git_repo(self) -> bool:
        """Check if the specified path is a Git repository."""
        try:
            self._run_git_command(["git", "rev-parse", "--git-dir"],
                                check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def get_recent_commits(self, count: int) -> List[str]:
        """Get the hash of recent commits in reverse chronological order (newest first)."""
        try:
            result = self._run_git_command(
                ["git", "log", f"--max-count={count}", "--format=%H"],
                check=True, capture_output=True, text=True
            )
            return result.stdout.strip().split('\n') if result.stdout.strip() else []
        except subprocess.CalledProcessError as e:
            print(f"Error getting commits: {e}")
            return []

    def generate_random_work_datetime(self) -> datetime:
        """Generate a random datetime within the specified date range and work hours."""
        # Random date within range
        date_range = (self.end_date - self.start_date).days
        random_days = random.randint(0, date_range)
        random_date = self.start_date + timedelta(days=random_days)

        # Skip weekends (Monday=0, Sunday=6)
        while random_date.weekday() >= 5:  # Saturday=5, Sunday=6
            random_date = self.start_date + timedelta(days=random.randint(0, date_range))

        # Random time within work hours
        work_start_minutes = self.work_start.hour * 60 + self.work_start.minute
        work_end_minutes = self.work_end.hour * 60 + self.work_end.minute
        random_minutes = random.randint(work_start_minutes, work_end_minutes)

        # Add jitter
        jitter = random.randint(-self.jitter_minutes, self.jitter_minutes)
        random_minutes += jitter

        # Ensure we don't go outside work hours with jitter
        random_minutes = max(work_start_minutes, min(work_end_minutes, random_minutes))

        # Convert back to time
        random_hour = random_minutes // 60
        random_minute = random_minutes % 60

        return random_date.replace(hour=random_hour, minute=random_minute, second=0, microsecond=0)

    def build_env_filter_script(self, commit_date_map: Dict[str, datetime]) -> str:
        """Build a comprehensive env-filter script for all commits."""
        script_parts = []
        
        # Start with the main conditional structure
        for i, (commit_hash, new_date) in enumerate(commit_date_map.items()):
            git_date = new_date.strftime("%Y-%m-%d %H:%M:%S")
            
            # Use if/elif/else structure for better performance
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
        
        # Close the conditional structure
        script_parts.append('fi')
        
        return '\n'.join(script_parts)

    def rewrite_commits_batch(self, commit_count: int) -> bool:
        """Rewrite all commits in a single git filter-branch operation."""
        commits = self.get_recent_commits(commit_count)
        if not commits:
            print("No commits found to rewrite")
            return False

        print(f"Found {len(commits)} commits to rewrite")

        # Generate new dates (chronologically ordered, earliest first)
        new_dates = []
        for _ in range(len(commits)):
            new_dates.append(self.generate_random_work_datetime())
        new_dates.sort()  # Sort so earliest date is first

        # Create commit-to-date mapping
        commit_date_map = {}
        for i, commit_hash in enumerate(commits):
            # Reverse the date assignment: newest commit gets latest date
            date_index = len(commits) - 1 - i
            new_date = new_dates[date_index]
            commit_date_map[commit_hash] = new_date

        print("\nDate assignment plan:")
        for i, commit_hash in enumerate(commits):
            original_date = self.get_commit_original_date(commit_hash)
            new_date = commit_date_map[commit_hash]
            commit_order = "newest" if i == 0 else ("oldest" if i == len(commits) - 1 else f"#{i+1}")
            print(f"{commit_hash[:8]} ({commit_order}) | Original: {original_date.strftime('%Y-%m-%d %H:%M:%S') if original_date else 'Unknown'} -> New: {new_date.strftime('%Y-%m-%d %H:%M:%S')}")

        # Build the env-filter script
        env_filter_script = self.build_env_filter_script(commit_date_map)
        
        print(f"\nExecuting single git filter-branch operation for {len(commits)} commits...")
        
        try:
            # Use git filter-branch with the comprehensive env-filter
            self._run_git_command(
                ["git", "filter-branch", "-f", "--env-filter", env_filter_script],
                check=True,
                capture_output=True,
                text=True
            )
            
            print("Successfully completed batch rewrite operation!")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"Error during batch rewrite: {e}")
            if e.stderr:
                print(f"Error details: {e.stderr}")
            return False

    def backup_branch(self) -> str:
        """Create a backup branch before making changes."""
        try:
            # Get current branch name
            result = self._run_git_command(
                ["git", "branch", "--show-current"],
                check=True, capture_output=True, text=True
            )
            current_branch = result.stdout.strip()

            # Create backup branch
            backup_name = f"backup-{current_branch}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            self._run_git_command(
                ["git", "branch", backup_name],
                check=True, capture_output=True
            )

            print(f"Created backup branch: {backup_name}")
            return backup_name

        except subprocess.CalledProcessError as e:
            print(f"Warning: Could not create backup branch: {e}")
            return ""

    def get_commit_original_date(self, commit_hash: str) -> datetime | None:
        """Get the original date of a commit."""
        try:
            result = self._run_git_command(
                ["git", "show", "-s", "--format=%ad", "--date=iso-strict", commit_hash],
                check=True, 
                capture_output=True, 
                text=True
            )
            date_str = result.stdout.strip()
            return datetime.fromisoformat(date_str)
        except subprocess.CalledProcessError as e:
            print(f"Error getting original date for commit {commit_hash[:8]}: {e}", file=sys.stderr)
            return None
        except ValueError as e:
            print(f"Error parsing date for commit {commit_hash[:8]}: {e}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"Unexpected error getting date for commit {commit_hash[:8]}: {e}", file=sys.stderr)
            return None

    def clean_filter_branch_refs(self):
        """Clean up filter-branch backup refs to avoid conflicts."""
        try:
            # Remove the refs/original/* references that filter-branch creates
            self._run_git_command(
                ["git", "for-each-ref", "--format=%(refname)", "refs/original/"],
                check=True, capture_output=True, text=True
            )
            
            # Delete the refs/original namespace
            self._run_git_command(
                ["git", "update-ref", "-d", "refs/original/refs/heads/master"],
                capture_output=True  # Don't fail if this doesn't exist
            )
            
            # Run garbage collection to clean up
            self._run_git_command(
                ["git", "reflog", "expire", "--expire=now", "--all"],
                capture_output=True
            )
            self._run_git_command(
                ["git", "gc", "--prune=now", "--aggressive"],
                capture_output=True
            )
            
        except subprocess.CalledProcessError:
            # These cleanup operations are optional
            pass

    def rewrite_commits(self, commit_count: int, create_backup: bool = True) -> None:
        """Rewrite the specified number of recent commits using optimized batch processing."""
        if not self.check_git_repo():
            print(f"Error: Not a Git repository: {self.repo_path}")
            return

        print(f"Working with repository: {self.repo_path}")

        # Clean up any previous filter-branch operations
        self.clean_filter_branch_refs()

        # Create backup
        if create_backup:
            self.backup_branch()

        print("Using optimized batch processing method...")
        success = self.rewrite_commits_batch(commit_count)

        if success:
            print(f"\nSuccessfully rewrote {commit_count} commits in a single operation!")
            print("\nWarning: Git history has been modified!")
            print("If you've already pushed these commits, you'll need to force push:")
            print("git push --force-with-lease")
        else:
            print("\nCommits could not be rewritten. Check the output above for details.")


def main():
    parser = argparse.ArgumentParser(
        description="Rewrite Git commit dates to appear within specified parameters (Optimized Version)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --repo /path/to/repo --commits 5 --start-date 2024-01-01 --end-date 2024-01-31
  %(prog)s --commits 10 --start-date 2024-02-01 --end-date 2024-02-28 --work-start 10:00 --work-end 16:00
  %(prog)s --repo ../other-project --commits 3 --start-date 2024-03-01 --end-date 2024-03-15 --no-backup
  %(prog)s --commits 5 --start-date 2024-01-01 --end-date 2024-01-31 --author-name "John Doe" --author-email "john@example.com"
        """)

    parser.add_argument("--author-name", type=str,
                       help="New author name for commits")
    parser.add_argument("--author-email", type=str,
                       help="New author email for commits")
    parser.add_argument("--repo", "-r", type=str, default=".",
                       help="Path to Git repository (default: current directory)")
    parser.add_argument("--commits", "-c", type=int, default=5,
                       help="Number of recent commits to rewrite (default: 5)")
    parser.add_argument("--start-date", "-s", required=True,
                       help="Start date in YYYY-MM-DD format")
    parser.add_argument("--end-date", "-e", required=True,
                       help="End date in YYYY-MM-DD format")
    parser.add_argument("--work-start", default="09:00",
                       help="Work day start time in HH:MM format (default: 09:00)")
    parser.add_argument("--work-end", default="17:00",
                       help="Work day end time in HH:MM format (default: 17:00)")
    parser.add_argument("--jitter", type=int, default=15,
                       help="Random time variation in minutes (default: 15)")
    parser.add_argument("--no-backup", action="store_true",
                       help="Skip creating backup branch")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be done without making changes")

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

        if args.dry_run:
            print("DRY RUN MODE - No changes will be made")
            commits = rewriter.get_recent_commits(args.commits)
            print(f"Would rewrite {len(commits)} commits in a single batch operation:")

            # Generate dates for preview
            new_dates = []
            for _ in range(len(commits)):
                new_dates.append(rewriter.generate_random_work_datetime())
            new_dates.sort()  # Sort so earliest date is first

            # Create commit-to-date mapping for preview
            commit_date_map = {}
            for i, commit_hash in enumerate(commits):
                date_index = len(commits) - 1 - i
                new_date = new_dates[date_index]
                commit_date_map[commit_hash] = new_date

            print("\nOptimized env-filter script preview:")
            env_filter_script = rewriter.build_env_filter_script(commit_date_map)
            print(env_filter_script)

            print("\nDate assignment plan:")
            for i, commit in enumerate(commits):
                new_date = commit_date_map[commit]
                commit_order = "newest" if i == 0 else ("oldest" if i == len(commits) - 1 else f"#{i+1}")
                author_info = ""
                if args.author_name or args.author_email:
                    author_info = f" by {args.author_name or 'current'} <{args.author_email or 'current'}>"
                print(f"  {commit[:8]} ({commit_order}) -> {new_date}{author_info}")
        else:
            print("WARNING: This will modify Git history!")
            response = input("Are you sure you want to continue? (yes/no): ")
            if response.lower() in ['yes', 'y']:
                rewriter.rewrite_commits(args.commits, not args.no_backup)
            else:
                print("Operation cancelled")

    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)


if __name__ == "__main__":
    main()
    