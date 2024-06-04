import json
from multiprocessing import Pool
import requests
from fastapi import HTTPException
from src.models.agent import Agent
from src.utilities.general import manifest, llm_url
from src.utilities.git import show_file_contents


async def file_list_chunker(file_list, user_prompt):
    chunk_size = 10
    iterations = len(file_list) // chunk_size
    prompts = []
    lower_bound = 0
    for iteration in range(iterations):
        prompts.append(
            "Please review the User Prompt and identify the relevant files from the following list based on the "
            "criteria provided, if no files in the list are relevant return N/A, do not provide an explation, "
            "simply a list containing the files or N/A if no relevant files are present:\n\n"
            f"User Prompt: {user_prompt}.\n\n"
            f"FILE_LIST: {file_list[lower_bound:chunk_size * iteration]}"
            f"RESPONSE: 'Return a comma seperated list containing all the relevant files'\n"
        )

        lower_bound = chunk_size * iteration
    prompts.append(
        "Please review the User Prompt and identify the relevant files from the following list based on the "
        "criteria provided, if no files in the list are relevant return N/A, do not provide an explation, "
        "simply a list containing the files or N/A if no relevant files are present:\n\n"
        f"User Prompt: {user_prompt}.\n\n"
        f"FILE_LIST: {file_list[lower_bound:]}"
        f"RESPONSE: 'Return a comma seperated list containing all the relevant files'\n"
    )
    return prompts


async def identify_relevant_files(prompts):
    try:
        with Pool() as p:
            responses = p.map(call_llm, prompts)
        p.join()
        full_list = []
        for response in responses:
            if "N/A" not in response:
                full_list.extend(response.split(","))
        sanitized = []
        for file in full_list:
            sanitized.append(file.strip())
        return sanitized
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error {exc}") from exc


async def refactor(target_guidance, target_code, version, repo_dir):
    manager = Agent('Manager', target_guidance)
    code_file_content = [
        f"###{target_code[i]}###\n{await show_file_contents(version, target_code[i], repo_dir)}\n######"
        for i in range(len(target_code))
    ]
    manager_manifest = await generate_plan_file(target_guidance, target_code)
    manager.progress = await run_iteration_prompts(
        str(code_file_content),
        topic="Refactor",
        feature_request=target_guidance,
        custom_manifest=manager_manifest
    )
    print(manager.progress)
    unreviewed_code_and_test = {
        "Code": manager.progress['Developer 8'],
        "Test": manager.progress['Developer 10']
    }
    final_review = await code_review(unreviewed_code_and_test)
    version_history = dict()
    for agent in final_review.keys():
        version_history.update({f"{agent} Final": final_review[agent]})
    version_history.update(manager.progress)
    return version_history


async def code_review(progress, reviews: int = 2):
    print(progress)
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
              "or correction. The first agent then send teh code back to you and the n you send it to the second "
              "developer who is responsible to review and adjust the code based on the feature or guidance. The "
              "process continues sequentially where the code build is passed to the new developer. These are the "
              "developer roles from Devs 3 - 9: Dev 3, 4, and 5 do the same as Dev 2. Dev 6, 7, and 8 verify code for "
              "security. Dev 9 and 10 only write unit tests. Please ensure that the developer prompts that I can use "
              "for developers 1 - 10. Keys in JSON should be Developer Number, and Values should be the prompt. Please "
              "ensure each prompt is clear, concise and provides enough detail to pass to the next stage.\n"
              "EXAMPLE RESPONSE: { 'Developer 2': 'Revise the code for bugs', 'Developer 3': 'Revise Code for bugs' } "
    )
    print(manager_response)
    manager_manifest = json.loads(manager_response)
    return manager_manifest


async def run_iteration_prompts(
        code_to_revise: str, topic: str, tries: int = 3, feature_request: str = None,
        custom_manifest: dict = None
):
    try:
        agent_responses = dict()
        developer_guidelines = ("Do not include labels, notes, or explanations of any kind, simply return the code. "
                                "Please directly return only the code enclosed in triple quotes and nothing else. If "
                                "no changes exist, your response should only be 'N/A'")
        if custom_manifest:
            current_manifest = custom_manifest
        else:
            current_manifest = manifest["Iteration Prompts"][topic]
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
            agent_responses.update({cur_agent: code_to_revise})
        return agent_responses
    except Exception as exc:
        print(f"{exc}")
        if tries > 0:
            return await run_iteration_prompts(code_to_revise, topic, tries - 1)
        raise HTTPException(status_code=500, detail=f"Iteration Failure: {exc}")


async def reformat_llm_output(llm_output: str):
    reformat_response = call_llm(
        prompt=f"{llm_output}",
        rules="You are a code cleaner. Your job is to clean the input to ensure there is nothing other than code. "
              "Please remove all explanations, notes, labels and remarks of any kind. There should be nothing in the "
              "output except for the code enclosed in triple quotes. Respond with only the cleaned code. If no "
              "cleaning needs to be done, response with only 'A/N'"
    )
    reformat_output = reformat_response
    print("reformatted output")
    print(reformat_output)
    if 'A/N' not in reformat_output:
        llm_output = reformat_output
    return llm_output.strip()


def call_llm(prompt, rules="You are a Digital Assistant.", url=llm_url):
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

