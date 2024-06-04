from fastapi import APIRouter, Form
from src.services.tasks import repo_ops

tasks = APIRouter(
    prefix="/Tasks",
    responses={
        200: {
            "description": "Successful"
        },
        400: {
            "description": "Bad Request"
        },
        403: {
            "description": "Unauthorized"
        },
        500: {
            "description": "Internal Server Error"
        }
    },
    tags=["Agent Tasking"]
)


@tasks.post("/RunTask")
async def run_task(
        user_prompt: str = Form(
            description="What you want the agent to do.",
            default="Refactor the provided code for any vulnerabilities, optimizations, and mistakes."
        ),
        https_clone_link: str = Form(
            description="HTTPs URL to clone your repo."
        ),
        original_code_branch: str = Form(
            default="master",
            description="The branch you want to work on."
        ),
        new_branch_name: str = Form(
            default="feature/digitalstaff",
            description="Name for the new branch where changes will be reflected."
        )
):
    return await repo_ops(user_prompt, https_clone_link, original_code_branch, new_branch_name)
