#!/usr/bin/env python3

import unittest
from unittest.mock import patch, MagicMock, call
import tempfile
import os
import shutil
from datetime import datetime, timedelta
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from git_rewriter import GitCommitRewriter


class TestGitCommitRewriter(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.start_date = "2024-01-01"
        self.end_date = "2024-01-31"
        
    def tearDown(self):
        """Clean up after each test method."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_init_valid_parameters(self):
        """Test GitCommitRewriter initialization with valid parameters."""
        rewriter = GitCommitRewriter(
            start_date=self.start_date,
            end_date=self.end_date,
            repo_path=self.temp_dir
        )
        
        self.assertEqual(rewriter.start_date, datetime(2024, 1, 1))
        self.assertEqual(rewriter.end_date, datetime(2024, 1, 31))
        self.assertEqual(rewriter.repo_path, os.path.abspath(self.temp_dir))
        self.assertEqual(rewriter.work_start.hour, 9)
        self.assertEqual(rewriter.work_end.hour, 17)
        self.assertEqual(rewriter.jitter_minutes, 15)
        self.assertIsNone(rewriter.author_name)
        self.assertIsNone(rewriter.author_email)
    
    def test_init_invalid_date_range(self):
        """Test initialization with invalid date range."""
        with self.assertRaises(ValueError) as context:
            GitCommitRewriter(
                start_date="2024-01-31",
                end_date="2024-01-01",
                repo_path=self.temp_dir
            )
        self.assertIn("Start date must be before end date", str(context.exception))
    
    def test_init_invalid_repo_path(self):
        """Test initialization with non-existent repository path."""
        with self.assertRaises(ValueError) as context:
            GitCommitRewriter(
                start_date=self.start_date,
                end_date=self.end_date,
                repo_path="/non/existent/path"
            )
        self.assertIn("Repository path does not exist", str(context.exception))
    
    def test_init_custom_parameters(self):
        """Test initialization with custom parameters."""
        rewriter = GitCommitRewriter(
            start_date=self.start_date,
            end_date=self.end_date,
            repo_path=self.temp_dir,
            work_start="10:30",
            work_end="18:45",
            jitter_minutes=30,
            author_name="Test Author",
            author_email="test@example.com"
        )
        
        self.assertEqual(rewriter.work_start.hour, 10)
        self.assertEqual(rewriter.work_start.minute, 30)
        self.assertEqual(rewriter.work_end.hour, 18)
        self.assertEqual(rewriter.work_end.minute, 45)
        self.assertEqual(rewriter.jitter_minutes, 30)
        self.assertEqual(rewriter.author_name, "Test Author")
        self.assertEqual(rewriter.author_email, "test@example.com")


class TestGitCommitRewriterMethods(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.rewriter = GitCommitRewriter(
            start_date="2024-01-01",
            end_date="2024-01-31",
            repo_path=self.temp_dir
        )
    
    def tearDown(self):
        """Clean up after tests."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @patch('subprocess.run')
    def test_check_git_repo_valid(self, mock_run):
        """Test check_git_repo with valid repository."""
        mock_run.return_value = MagicMock()
        
        result = self.rewriter.check_git_repo()
        
        self.assertTrue(result)
        mock_run.assert_called_once_with(
            ["git", "rev-parse", "--git-dir"],
            cwd=self.temp_dir,
            check=True,
            capture_output=True
        )
    
    @patch('subprocess.run')
    def test_check_git_repo_invalid(self, mock_run):
        """Test check_git_repo with invalid repository."""
        mock_run.side_effect = subprocess.CalledProcessError(1, ["git"])
        
        result = self.rewriter.check_git_repo()
        
        self.assertFalse(result)
    
    @patch('subprocess.run')
    def test_get_recent_commits_success(self, mock_run):
        """Test get_recent_commits with successful git log."""
        mock_run.return_value = MagicMock(
            stdout="abc123\ndef456\nghi789\n"
        )
        
        commits = self.rewriter.get_recent_commits(3)
        
        self.assertEqual(commits, ["abc123", "def456", "ghi789"])
        mock_run.assert_called_once_with(
            ["git", "log", "--max-count=3", "--format=%H"],
            cwd=self.temp_dir,
            check=True,
            capture_output=True,
            text=True
        )
    
    @patch('subprocess.run')
    def test_get_recent_commits_empty(self, mock_run):
        """Test get_recent_commits with no commits."""
        mock_run.return_value = MagicMock(stdout="")
        
        commits = self.rewriter.get_recent_commits(5)
        
        self.assertEqual(commits, [])
    
    @patch('subprocess.run')
    def test_get_recent_commits_error(self, mock_run):
        """Test get_recent_commits with git error."""
        mock_run.side_effect = subprocess.CalledProcessError(1, ["git"])
        
        commits = self.rewriter.get_recent_commits(3)
        
        self.assertEqual(commits, [])
    
    def test_generate_random_work_datetime_range(self):
        """Test that generated datetime is within specified range."""
        for _ in range(10):  # Test multiple generations
            dt = self.rewriter.generate_random_work_datetime()
            
            # Check date range
            self.assertGreaterEqual(dt.date(), self.rewriter.start_date.date())
            self.assertLessEqual(dt.date(), self.rewriter.end_date.date())
            
            # Check it's a weekday (0-4, Monday-Friday)
            self.assertLess(dt.weekday(), 5)
            
            # Check work hours (with potential jitter)
            work_start_minutes = self.rewriter.work_start.hour * 60 + self.rewriter.work_start.minute
            work_end_minutes = self.rewriter.work_end.hour * 60 + self.rewriter.work_end.minute
            dt_minutes = dt.hour * 60 + dt.minute
            
            # Should be within work hours +/- jitter
            self.assertGreaterEqual(dt_minutes, work_start_minutes - self.rewriter.jitter_minutes)
            self.assertLessEqual(dt_minutes, work_end_minutes + self.rewriter.jitter_minutes)
    
    def test_build_env_filter_script_basic(self):
        """Test building env-filter script with basic parameters."""
        commit_date_map = {
            "abc123": datetime(2024, 1, 15, 10, 30, 0),
            "def456": datetime(2024, 1, 16, 14, 45, 0)
        }
        
        script = self.rewriter.build_env_filter_script(commit_date_map)
        
        expected_lines = [
            'if [ "$GIT_COMMIT" = "abc123" ]; then',
            '    export GIT_AUTHOR_DATE="2024-01-15 10:30:00"',
            '    export GIT_COMMITTER_DATE="2024-01-15 10:30:00"',
            'elif [ "$GIT_COMMIT" = "def456" ]; then',
            '    export GIT_AUTHOR_DATE="2024-01-16 14:45:00"',
            '    export GIT_COMMITTER_DATE="2024-01-16 14:45:00"',
            'fi'
        ]
        
        self.assertEqual(script, '\n'.join(expected_lines))
    
    def test_build_env_filter_script_with_author(self):
        """Test building env-filter script with author information."""
        rewriter = GitCommitRewriter(
            start_date="2024-01-01",
            end_date="2024-01-31",
            repo_path=self.temp_dir,
            author_name="Test Author",
            author_email="test@example.com"
        )
        
        commit_date_map = {
            "abc123": datetime(2024, 1, 15, 10, 30, 0)
        }
        
        script = rewriter.build_env_filter_script(commit_date_map)
        
        self.assertIn('export GIT_AUTHOR_NAME="Test Author"', script)
        self.assertIn('export GIT_COMMITTER_NAME="Test Author"', script)
        self.assertIn('export GIT_AUTHOR_EMAIL="test@example.com"', script)
        self.assertIn('export GIT_COMMITTER_EMAIL="test@example.com"', script)
    
    @patch('subprocess.run')
    def test_create_backup_success(self, mock_run):
        """Test successful backup creation."""
        mock_run.side_effect = [
            MagicMock(stdout="main\n"),  # git branch --show-current
            MagicMock()  # git branch backup-...
        ]
        
        with patch('builtins.print') as mock_print:
            self.rewriter._create_backup()
        
        self.assertEqual(mock_run.call_count, 2)
        mock_print.assert_called()
        print_call_args = mock_print.call_args[0][0]
        self.assertIn("Created backup branch:", print_call_args)
    
    @patch('subprocess.run')
    def test_create_backup_failure(self, mock_run):
        """Test backup creation failure."""
        mock_run.side_effect = subprocess.CalledProcessError(1, ["git"])
        
        with patch('builtins.print') as mock_print:
            self.rewriter._create_backup()
        
        mock_print.assert_called_with("Warning: Could not create backup branch")


class TestGitCommitRewriterIntegration(unittest.TestCase):
    
    def setUp(self):
        """Set up integration test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.rewriter = GitCommitRewriter(
            start_date="2024-01-01",
            end_date="2024-01-31",
            repo_path=self.temp_dir
        )
    
    def tearDown(self):
        """Clean up after integration tests."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @patch('subprocess.run')
    def test_rewrite_commits_not_git_repo(self, mock_run):
        """Test rewrite_commits when not in a git repository."""
        mock_run.side_effect = subprocess.CalledProcessError(1, ["git"])
        
        with patch('builtins.print') as mock_print:
            result = self.rewriter.rewrite_commits(5)
        
        self.assertFalse(result)
        mock_print.assert_called_with(f"Error: Not a Git repository: {self.temp_dir}")
    
    @patch('subprocess.run')
    def test_rewrite_commits_no_commits(self, mock_run):
        """Test rewrite_commits when no commits are found."""
        mock_run.side_effect = [
            MagicMock(),  # check_git_repo
            MagicMock(stdout="")  # get_recent_commits
        ]
        
        with patch('builtins.print') as mock_print:
            result = self.rewriter.rewrite_commits(5)
        
        self.assertFalse(result)
        mock_print.assert_called_with("No commits found to rewrite")
    
    @patch('subprocess.run')
    def test_rewrite_commits_success(self, mock_run):
        """Test successful commit rewriting."""
        mock_run.side_effect = [
            MagicMock(),  # check_git_repo
            MagicMock(stdout="abc123\ndef456\n"),  # get_recent_commits
            MagicMock(stdout="main\n"),  # backup: git branch --show-current
            MagicMock(),  # backup: git branch backup-...
            MagicMock()   # git filter-branch
        ]
        
        with patch('builtins.print') as mock_print:
            result = self.rewriter.rewrite_commits(2, create_backup=True)
        
        self.assertTrue(result)
        mock_print.assert_any_call("Successfully rewrote 2 commits!")
        
        # Verify filter-branch was called
        filter_branch_call = None
        for call in mock_run.call_args_list:
            if call[0][0][1] == "filter-branch":
                filter_branch_call = call
                break
        
        self.assertIsNotNone(filter_branch_call)
        self.assertEqual(filter_branch_call[0][0][:3], ["git", "filter-branch", "-f"])
    
    @patch('subprocess.run')
    def test_rewrite_commits_filter_branch_error(self, mock_run):
        """Test rewrite_commits when filter-branch fails."""
        mock_run.side_effect = [
            MagicMock(),  # check_git_repo
            MagicMock(stdout="abc123\n"),  # get_recent_commits
            subprocess.CalledProcessError(1, ["git", "filter-branch"])  # filter-branch fails
        ]
        
        with patch('builtins.print') as mock_print:
            result = self.rewriter.rewrite_commits(1, create_backup=False)
        
        self.assertFalse(result)
        mock_print.assert_any_call("Error during rewrite: Command '['git', 'filter-branch']' returned non-zero exit status 1.")


class TestMainFunction(unittest.TestCase):
    
    @patch('sys.argv', ['git_rewriter.py', '--all', '--start-date', '2024-01-01', '--end-date', '2024-01-31'])
    @patch('builtins.input', return_value='n')
    def test_main_user_cancellation(self, mock_input):
        """Test main function when user cancels operation."""
        with patch('builtins.print') as mock_print:
            from git_rewriter import main
            main()
        
        mock_print.assert_any_call("This will modify Git history!")
        mock_print.assert_any_call("Cancelled")
    
    @patch('sys.argv', ['git_rewriter.py', '--all', '--start-date', '2024-01-31', '--end-date', '2024-01-01'])
    def test_main_invalid_date_range(self):
        """Test main function with invalid date range."""
        with patch('builtins.print') as mock_print, \
             patch('sys.exit') as mock_exit:
            from git_rewriter import main
            main()
        
        mock_print.assert_any_call("Error: Start date must be before end date")
        mock_exit.assert_called_with(1)


if __name__ == '__main__':
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestGitCommitRewriter))
    suite.addTests(loader.loadTestsFromTestCase(TestGitCommitRewriterMethods))
    suite.addTests(loader.loadTestsFromTestCase(TestGitCommitRewriterIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestMainFunction))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with non-zero code if tests failed
    if not result.wasSuccessful():
        sys.exit(1)
