import json
from multiprocessing import Pool
import requests
from fastapi import HTTPException
from src.models.agent import Agent
from src.utilities.general import manifest, llm_url
from src.utilities.git import show_file_contents


async def file_list_chunker(file_list, user_prompt, chunk_size=10):
    prompts = []
    for i in range(0, len(file_list), chunk_size):
        chunk = file_list[i:i+chunk_size]
        prompt = (
            "Please review the User Prompt and identify the relevant files from the following list based on the "
            "criteria provided. If no files in the list are relevant, return N/A. Do not provide an explanation, "
            "simply return a list containing the files or N/A if no relevant files are present:\n\n"
            f"User Prompt: {user_prompt}.\n\n"
            f"FILE_LIST: {chunk}\n"
            f"RESPONSE: 'Return a comma-separated list containing all the relevant files like example [\"\",\"\",\"\",\"\"]'"
        )
        prompts.append(prompt)
    return prompts


async def identify_relevant_files(prompts):
    try:
        with Pool() as p:
            responses = p.map(call_llm, prompts)
        full_list = [file.strip() for response in responses if "N/A" not in response for file in response.split(",")]
        return full_list
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error {exc}") from exc


async def refactor(target_guidance, target_code, version, repo_dir):
    manager = Agent('Manager', target_guidance)
    code_file_content = [
        f"###{file}###\n{await show_file_contents(version, file, repo_dir)}\n######"
        for file in target_code
    ]
    manager_manifest = await generate_plan_file(target_guidance, target_code)
    manager.progress = await run_iteration_prompts(
        str(code_file_content),
        topic="Refactor",
        feature_request=target_guidance,
        custom_manifest=manager_manifest
    )
    unreviewed_code_and_test = {
        "Code": manager.progress['Developer 8'],
        "Test": manager.progress['Developer 10']
    }
    final_review = await code_review(unreviewed_code_and_test)
    version_history = {f"{agent} Final": final_review[agent] for agent in final_review.keys()}
    version_history.update(manager.progress)
    return version_history


async def code_review(progress, reviews=2):
    code_response = call_llm(
        prompt=f"Provided Code: '''\n{progress.get('Code', progress.get('Software Developer'))}'''\n",
        rules="You are a code reviewer. Your job is to inspect the Provided Code and make any required changes. "
              "Do not offer any explanation of any kind for the code you produce, simply return the code. "
              "If no changes exist, your response should be only: 'N/A'."
    )
    reviewed_code = await reformat_llm_output(code_response)
    if 'N/A' in reviewed_code:
        return progress
    test_response = call_llm(
        prompt=f"Provided Code: '''{reviewed_code}'''\n"
               f"Provided Test Cases: '''\n{progress.get('Test', progress.get('Code Tester'))}\n'''",
        rules="You are a code reviewer. Your job is to inspect the provided unit tests for the provided code and make "
              "any required changes. Do not include labels and do not offer any explanation of any kind for the code "
              "you produce, simply return the code. If no changes exist, your response should only be 'N/A'."
    )
    reviewed_tests = await reformat_llm_output(test_response)
    if 'N/A' in reviewed_tests or reviews < 1:
        return progress
    new_progress = {
        "Software Developer": reviewed_code,
        "Code Tester": reviewed_tests
    }
    return await code_review(new_progress, reviews - 1)


async def generate_plan_file(target_guidance, target_code):
    manager_response = call_llm(
        prompt=f"Target Guidance: {target_guidance} \n Target Code: {target_code}",
        rules="You are a super intelligent Manager Agent capable of creating a development plan that assumes 10 "
              "developers where each developer is tasked sequentially and is able to handle a code pipeline that "
              "adjusts along the way to ensure a successful automatic development sprint. Please assume that you pass "
              "the request and target code to the first agent who then creates a feature, brand new code build, "
              "or correction. The first agent then sends the code back to you and then you send it to the second "
              "developer who is responsible for reviewing and adjusting the code based on the feature or guidance. The "
              "process continues sequentially where the code build is passed to the new developer. These are the "
              "developer roles from Devs 3 - 9: Dev 3, 4, and 5 do the same as Dev 2. Dev 6, 7, and 8 verify code for "
              "security. Dev 9 and 10 only write unit tests. Please ensure that the developer prompts that I can use "
              "for developers 1 - 10. Keys in JSON should be Developer Number, and Values should be the prompt. Please "
              "ensure each prompt is clear, concise and provides enough detail to pass to the next stage.\n"
              "EXAMPLE RESPONSE: { 'Developer 2': 'Revise the code for bugs', 'Developer 3': 'Revise Code for bugs' }"
    )
    return json.loads(manager_response)


async def run_iteration_prompts(
        code_to_revise: str, topic: str, tries: int = 3, feature_request: str = None,
        custom_manifest: dict = None
):
    print("4th")
    try:
        agent_responses = {}
        developer_guidelines = ("Do not include labels, notes, or explanations of any kind, simply return the code. "
                                "Please directly return only the code enclosed in triple quotes and nothing else. If "
                                "no changes exist, your response should only be 'N/A'")
        current_manifest = custom_manifest if custom_manifest else manifest["Iteration Prompts"][topic]
        
        for cur_agent, iteration_prompt in current_manifest.items():
            print(cur_agent)
            developer_rules = iteration_prompt + developer_guidelines
            
            if topic == "Refactor":
                response = call_llm(
                    prompt=f"Target Code: '''\n{code_to_revise}'''\n",
                    rules=developer_rules
                )
            elif topic == "Add Feature":
                if cur_agent == 'Developer 1':
                    response = call_llm(
                        prompt=f"Target Guidance: {feature_request}\n"
                               f"Target Code: '''\n{code_to_revise}'''\n",
                        rules=developer_rules
                    )
                else:
                    response = call_llm(
                        prompt=f"Target Code: '''\n{code_to_revise}'''\n",
                        rules=developer_rules
                    )
            else:
                response = code_to_revise

            if 'N/A' not in response:
                code_to_revise = await reformat_llm_output(response)
            
            agent_responses[cur_agent] = code_to_revise
        
        return agent_responses
    
    except Exception as exc:
        print(f"Error: {exc}")
        if tries > 0:
            return await run_iteration_prompts(code_to_revise, topic, tries - 1)
        raise HTTPException(status_code=500, detail=f"Iteration Failure: {exc}")


async def reformat_llm_output(llm_output: str):
    print("5th")
    reformat_response = call_llm(
        prompt=f"{llm_output}",
        rules="You are a code cleaner. Your job is to clean the input to ensure there is nothing other than code. "
              "Please remove all explanations, notes, labels, and remarks of any kind. There should be nothing in the "
              "output except for the code enclosed in triple quotes. Respond with only the cleaned code. If no "
              "cleaning needs to be done, respond with only 'A/N'."
    )
    reformat_output = reformat_response
    print("Reformatted output:")
    print(reformat_output)
    
    if 'A/N' not in reformat_output:
        llm_output = reformat_output
    
    return llm_output.strip()


def call_llm(prompt, rules="You are a Digital Assistant.", url=llm_url):
    print("6th")
    try:
        response = requests.post(
            url,
            data={
                "prompt": '[{"role": "system", "content":' + rules + '}, {"role": "user", "content":' + prompt + '}]',
                "temperature": 0.05
            }
        )
        response = response.json()
        return response["choices"][0]["message"]["content"]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to reach {url}\n{exc}")

