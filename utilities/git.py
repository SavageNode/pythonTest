import os.path
import subprocess
from fastapi import HTTPException
from src.utilities.general import USER, USER_PASS


async def clone_repo(repo_link):
    try:
        dest_folder = f'efs/repos/{repo_link.split("/")[-1].split(".git")[0]}'
        if not os.path.exists(dest_folder):
            print(f"https://{USER}:{USER_PASS}@{repo_link.replace('https://', '')}")
            output = subprocess.run(
                [
                    "git",
                    "clone",
                    f"https://{repo_link.replace('https://', '')}",
                    dest_folder
                ],
                capture_output=True
            )
            print(output.stdout)
        return dest_folder
    except Exception as exc:
        print(f"Could not clone repo: {exc}", flush=True)
        raise HTTPException(status_code=500, detail=f"Could not clone repo: {exc}")


async def check_current_branch(repo_dir):
    try:
        output = subprocess.Popen(
            "git branch --show-current".split(),
            cwd=f"./{repo_dir}",
            stdout=subprocess.PIPE
        )
        return output.communicate()[0].decode("utf-8").strip()
    except Exception as exc:
        print(f"Could not identify current branch: {exc}", flush=True)
        raise HTTPException(status_code=500, detail=f"Could not identify current branch: {exc}")


async def checkout_and_rebranch(new_branch_name, branch_to_fork_from, repo_dir):
    try:
        output = subprocess.Popen(
            f"git checkout -b {new_branch_name} origin/{branch_to_fork_from}".split(),
            cwd=f"./{repo_dir}",
            stdout=subprocess.PIPE
        )
        return output.communicate()[0].decode("utf-8")
    except Exception as exc:
        print(f"Could not fork from branch: {exc}")
        raise HTTPException(status_code=500, detail=f"Could not fork from branch: {exc}")


async def repo_file_list(repo_dir):
    try:
        output = subprocess.Popen(
            "git ls-tree -r HEAD --name-only".split(),
            cwd=f"./{repo_dir}",
            stdout=subprocess.PIPE
        )
        return output.communicate()[0].decode("utf-8").strip().split("\n")
    except Exception as exc:
        print(f"Could not get file list: {exc}", flush=True)
        raise HTTPException(status_code=500, detail=f"Could not get file list: {exc}")


async def show_file_contents(version, file_path, repo_dir):
    try:
        output = subprocess.Popen(
            f"git show {version}:{file_path}".split(),
            cwd=f"./{repo_dir}",
            stdout=subprocess.PIPE
        )
        return output.communicate()[0].decode("utf-8")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not read file: {exc}")
