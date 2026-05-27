import os
import subprocess
import logging
from github import Github

logger = logging.getLogger(__name__)

class GitPRCreator:
    def __init__(self):
        self.github_token = os.getenv("GITHUB_TOKEN", "").strip()
        self.repo_path = os.getenv("REPO_PATH", ".")
        self.repo_name = os.getenv("REPO_NAME", "").split("#")[0].strip()  # strip inline comments
        # Only use PyGithub if token exists AND repo_name is not a placeholder
        self.use_pygithub = bool(
            self.github_token and self.repo_name 
            and "yourusername" not in self.repo_name
        )

    def _run_cmd(self, cmd: list) -> bool:
        """Helper to run a shell command in the target repo directory."""
        logger.info(f"Running command: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, cwd=self.repo_path, check=True, capture_output=True, text=True)
            logger.info(result.stdout)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {e.stderr}")
            return False

    def create_remediation_pr(self, tf_type: str, tf_name: str, branch_name: str = "finops/optimize-resources") -> bool:
        """Creates a localized branch, commits changes, and opens a PR if possible."""
        
        # 1. Checkout new branch locally
        logger.info(f"Checking out branch {branch_name} locally...")
        if not self._run_cmd(["git", "checkout", "-b", branch_name]):
            # If branch exists, just switch to it
            self._run_cmd(["git", "checkout", branch_name])
            
        # 2. Stage changes
        logger.info("Staging changes...")
        self._run_cmd(["git", "add", "."])
        
        # 3. Commit changes
        commit_msg = f"[FinOps Automation] Cloud Waste Remediation for {tf_type}.{tf_name}"
        logger.info(f"Committing changes with message: {commit_msg}")
        if not self._run_cmd(["git", "commit", "-m", commit_msg]):
            logger.warning("Commit failed. Maybe no changes to commit?")
            return False

        # 4. Push and Create PR via PyGithub if configured
        if self.use_pygithub:
            logger.info("GITHUB_TOKEN found. Attempting to push and create PR via PyGithub...")
            # Push the branch
            if not self._run_cmd(["git", "push", "-u", "origin", branch_name]):
                logger.error("Failed to push branch to origin.")
                return False
                
            try:
                gh = Github(self.github_token)
                repo = gh.get_repo(self.repo_name)
                
                # Check if PR already exists
                pulls = repo.get_pulls(state='open', head=f"{repo.owner.login}:{branch_name}")
                if pulls.totalCount > 0:
                    logger.info("PR already exists for this branch.")
                    return True
                
                pr = repo.create_pull(
                    title=commit_msg,
                    body=f"Automated PR by Cloud Waste Sniper.\nTarget resource: `{tf_type}.{tf_name}`\nAction: Downsized or Removed.",
                    head=branch_name,
                    base="main" # Assuming 'main' is default
                )
                logger.info(f"Successfully created Pull Request: {pr.html_url}")
                return True
            except Exception as e:
                logger.error(f"Failed to create PR via PyGithub: {e}")
                return False
        else:
            logger.info("GITHUB_TOKEN is not configured. Falling back to local git commit only.")
            logger.info(f"Local commit successful on branch: {branch_name}. Ready for manual push.")
            return True
