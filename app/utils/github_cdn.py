import base64
import logging
from flask import current_app

logger = logging.getLogger(__name__)


def upload_profile_pic(file_bytes: bytes, filename: str) -> str | None:
    """Upload profile picture to GitHub repo. Returns proxy URL or data URI fallback."""
    token = current_app.config.get("GITHUB_TOKEN", "").strip()
    repo_name = current_app.config.get("GITHUB_REPO", "").strip()
    branch = current_app.config.get("GITHUB_BRANCH", "main").strip()

    if not token or not repo_name:
        # Fallback to data URI
        logger.info("GitHub credentials not set; falling back to base64 encoding.")
        b64 = base64.b64encode(file_bytes).decode("utf-8")
        return f"data:image/jpeg;base64,{b64}"

    try:
        from github import Github
        gh = Github(token)
        repo = gh.get_repo(repo_name)
        path = f"profile_pics/{filename}"
        try:
            # Check if file exists to update it
            existing = repo.get_contents(path, ref=branch)
            repo.update_file(path, f"Update {filename}", file_bytes, existing.sha, branch=branch)
        except Exception:
            # Otherwise create it
            repo.create_file(path, f"Upload {filename}", file_bytes, branch=branch)
        return f"/cdn/profile_pics/{filename}"
    except Exception as exc:
        logger.warning("GitHub upload failed: %s; falling back to base64 encoding.", exc)
        b64 = base64.b64encode(file_bytes).decode("utf-8")
        return f"data:image/jpeg;base64,{b64}"


def upload_training_csv(file_bytes: bytes, filename: str) -> str | None:
    """Upload training CSV file to GitHub repo. Returns proxy URL or None."""
    token = current_app.config.get("GITHUB_TOKEN", "").strip()
    repo_name = current_app.config.get("GITHUB_REPO", "").strip()
    branch = current_app.config.get("GITHUB_BRANCH", "main").strip()

    if not token or not repo_name:
        logger.info("GitHub CSV upload skipped because credentials are not configured.")
        return None

    try:
        from github import Github
        gh = Github(token)
        repo = gh.get_repo(repo_name)
        path = f"training_csv/{filename}"
        try:
            existing = repo.get_contents(path, ref=branch)
            repo.update_file(path, f"Update training CSV {filename}", file_bytes, existing.sha, branch=branch)
        except Exception:
            repo.create_file(path, f"Upload training CSV {filename}", file_bytes, branch=branch)
        return f"/cdn/training_csv/{filename}"
    except Exception as exc:
        logger.warning("GitHub CSV upload failed: %s", exc)
        return None


def rewrite_pic_url(url: str | None) -> str | None:
    """Convert raw GitHub content URLs to secure local CDN proxy URLs."""
    if url and "raw.githubusercontent.com" in url:
        fname = url.split("/profile_pics/")[-1] if "/profile_pics/" in url else url.split("/")[-1]
        return f"/cdn/profile_pics/{fname}"
    return url
