import json
import os
from dotenv import load_dotenv

if os.environ.get("ENV"):
    load_dotenv(f"config/{os.environ['ENV']}")
else:
    load_dotenv("config/.env-dev")

USER = os.environ["USER"]
USER_PASS = os.environ["USER_PASS"]
manifest_path = os.environ["manifest_path"]
llm_url = os.environ["llm_url"]

with open(manifest_path, "r") as manifest_file:
    manifest = json.load(manifest_file)


agent_roles = {
    "Manager": {
        "Background": "You are the Development Manager of a software team."
    },
    "Operations Agent": {
        "Background": "You are an Operations Agent.",
    },
    "Software Developer": {
        "Background": "You are a Software Developer.",
    },
    "Business Analyst": {
        "Background": "You are a Business Analyst.",
    },
    "Content Agent": {
        "Background": "You are a Content Agent.",
    },
    "Product Agent": {
        "Background": "You are a Product Agent.",
    },
    "Code Tester": {
        "Background": "You are a Code Tester."
    }
}
