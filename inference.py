"""
Inference Script for Data Extraction Environment
===================================
MANDATORY VARIABLES:
    API_BASE_URL   The API endpoint for the LLM.
    MODEL_NAME     The model identifier to use for inference.
    HF_TOKEN       Your Hugging Face / API key.
    LOCAL_IMAGE_NAME  Docker image name (if using from_docker_image)

STDOUT FORMAT:
    [START] task=<task_name> env=<benchmark> model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>
"""

import asyncio
import json
import os
import re
import textwrap
from typing import List, Optional

from openai import OpenAI

# ──────────────────────────────────────────────────────────
# Import our environment client and action model
# ──────────────────────────────────────────────────────────
from client import IncidentEnv
from models import IncidentAction

# ──────────────────────────────────────────────────────────
# MANDATORY environment variables
# ──────────────────────────────────────────────────────────
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"
MODEL_NAME = os.getenv("MODEL_NAME") or "Qwen/Qwen2.5-72B-Instruct"
IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME") or os.getenv("IMAGE_NAME")

if not API_KEY: 
    raise ValueError("HF_TOKEN or API_KEY must be set")

if not MODEL_NAME: 
    raise ValueError("MODEL_NAME must be set")
# Environment config
ENV_URL = os.getenv("ENV_URL", "http://localhost:7860")
BENCHMARK = os.getenv("BENCHMARK", "incident_report_structuring")
SUCCESS_THRESHOLD = 0.5  # average reward above this = success

# Task list — so we know which task_ids to iterate over
from tasks import TASKS

# ──────────────────────────────────────────────────────────
# LLM Client
# ──────────────────────────────────────────────────────────
llm_client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

SYSTEM_PROMPT = textwrap.dedent("""
    You are an IT incident report analyst. You will receive a messy 
    incident report and a list of fields to extract. 
                                
    Return ONLY a valid JSON object. 

    IMPORTANT:                           
    - All fields must be present
    - Numeric values must be returned as strings (e.g., "2000")
    - Lists must be valid JSON arrays
    - If a field is not found, return empty string ""
""").strip()


# ──────────────────────────────────────────────────────────
# Structured logging — (Matches hackathon format)
# ──────────────────────────────────────────────────────────
def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    action_short = action[:100].replace("\n", " ") if action else "none"
    print(
        f"[STEP] step={step} action={action_short} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}",
        flush=True,
    )


# ──────────────────────────────────────────────────────────
# LLM extraction logic
# ──────────────────────────────────────────────────────────
def ask_llm_to_extract(raw_text: str, fields: list, hints: str) -> dict:
    """Send messy text to the LLM and get back extracted JSON fields."""

    fields_list = "\n".join(f"  - {f}" for f in fields)

    user_prompt = f"""Extract the requested fields from the raw text below.

RAW TEXT:
\"\"\"
{raw_text}
\"\"\"

FIELDS TO EXTRACT:
{fields_list}

FORMAT HINTS:
{hints}

Return ONLY a valid JSON object. Every field must be present.

YOUR JSON:"""

    try:
        response = llm_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1000,
            temperature=0.0,
        )

        raw_response = response.choices[0].message.content.strip()

        # Clean markdown code fences if the LLM wraps its response
        cleaned = raw_response
        if cleaned.startswith("```"):
            cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned)
            cleaned = re.sub(r'\n?```\s*$', '', cleaned)
        cleaned = cleaned.strip()

        extracted = json.loads(cleaned)
        if not isinstance(extracted, dict):
            return {f: "" for f in fields}
        return extracted

    except json.JSONDecodeError:
        print(f"[DEBUG] JSON parse error, raw: {raw_response[:200]}", flush=True)
        return {f: "" for f in fields}
    except Exception as e:
        print(f"[DEBUG] LLM error: {e}", flush=True)
        return {f: "" for f in fields}


# ──────────────────────────────────────────────────────────
# Main inference loop
# ──────────────────────────────────────────────────────────
async def main() -> None:
    """
    Connect to the environment, loop through all tasks,
    ask LLM to extract, submit, and log in hackathon format.

    Each task gets its own [START]...[STEP]...[END] block so the
    validator can count distinct tasks with graders.
    """

    # Connect to the running environment server
    env = IncidentEnv(base_url=ENV_URL)

    try:
        async with env:
            for task in TASKS:
                task_id = task["id"]
                rewards: List[float] = []
                steps_taken = 0
                score = 0.0
                success = False

                log_start(task=task_id, env=BENCHMARK, model=MODEL_NAME)

                try:
                    # Reset environment with a specific task
                    result = await env.reset(task_id=task_id)
                    obs = result.observation

                    # Ask the LLM to extract data from the raw text
                    extracted = ask_llm_to_extract(
                        raw_text=obs.raw_text,
                        fields=obs.fields_to_extract,
                        hints=obs.extraction_hints,
                    )

                    # Submit the extraction to the environment for grading
                    result = await env.step(
                        IncidentAction(extracted_data=extracted)
                    )

                    reward = result.reward or 0.0
                    done = result.done
                    rewards.append(reward)
                    steps_taken = 1

                    action_desc = f"extract({task_id}:{len(extracted)}fields)"
                    log_step(step=1, action=action_desc, reward=reward, done=done, error=None)

                    score = reward
                    score = min(max(score, 0.0), 1.0)
                    success = score >= SUCCESS_THRESHOLD

                except Exception as e:
                    print(f"[DEBUG] Task {task_id} failed: {e}", flush=True)

                finally:
                    log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

    except Exception as e:
        print(f"[DEBUG] Fatal exception: {e}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())