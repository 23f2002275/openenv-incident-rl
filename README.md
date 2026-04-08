---
title: openenv-incident-rl
emoji: 🚨
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
tags: 
 - openenv
 - reinforcement-learning
 - nlp
 - incident-response
 - structured-extraction
---
# Incident Report Structuring Environment

**Live Environment:** https://pratham-math-openenv-incident-rl.hf.space/

## Environment Description
An OpenEnv environment where LLM agents extract structured data from messy IT incident reports written by on-call engineers. Features 9 tasks across 3 difficulty levels covering service outages, security incidents, and performance degradations. Partial credit fuzzy matching graders ensure meaningful reward signal throughout the episode.

## Real-world Motivation
Every modern tech company, including companies like Meta and other large-scale infrastructure providers, deals with IT incident reports daily. These reports are often chaotic, filled with jargon, changing timestamps, and conflicting data as situations evolve from initial alerts to resolution. 

Structuring these messy reports unlocks significant automation opportunities: automated ticketing, accurate SLA tracking, intelligent on-call routing, and aggregate post-mortem analysis across computing fleets. This environment forces agentic models to demonstrate genuine context-aware extraction capabilities out of highly complex jargon and messy communication threads, exactly simulating a task that human SREs perform manually today.

## Action Space
The agent sends an `IncidentAction` containing a single dictionary field:

| Field | Type | Description |
|-------|------|-------------|
| `extracted_data` | `dict` | JSON dictionary mapping field names to extracted string or list values |

## Observation Space
The environment returns an `IncidentObservation` with:

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | `str` | Unique task identifier |
| `difficulty` | `str` | "easy", "medium", or "hard" |
| `raw_text` | `str` | The messy incident report text |
| `fields_to_extract` | `list[str]` | Which fields the agent must extract |
| `extraction_hints` | `str` | Format hints for each field |
| `feedback` | `str` | Detailed grading feedback (after step) |
| `fields_correct` | `int` | Number of fields scoring >= 0.8 |
| `fields_total` | `int` | Total fields graded |
| `field_scores` | `dict` | Per-field scores (0.0 to 1.0) |
| `reward` | `float` | Overall score (average of field scores) |
| `done` | `bool` | Whether the episode is complete |

## Task Descriptions

| ID | Difficulty | Fields | Description |
|----|------------|--------|-------------|
| `easy_1` | Easy | 6 | Simple web service login downtime |
| `easy_2` | Easy | 7 | Database connection pool exhaustion |
| `easy_3` | Easy | 6 | API rate limit breach |
| `medium_1` | Medium | 9 | Microservice cascade failure |
| `medium_2` | Medium | 9 | Security unauthorized access attempt |
| `medium_3` | Medium | 9 | CI/CD pipeline failure blocking deployments |
| `hard_1` | Hard | 13 | Multi-region DB replication lag causing data inconsistency |
| `hard_2` | Hard | 13 | DDoS attack with partial CDN mitigation |
| `hard_3` | Hard | 13 | Memory leak causing gradual fleet-wide service degradation |


## Grading
The reward is the **average of all per-field scores** (0.0 to 1.0). Each field is conditionally graded using one of these strategies depending on data type:
- **exact**: Normalized string match (lowercase, strip whitespace) - used for ticket IDs and codes.
- **numeric**: Extracts numbers and compares values directly - used for memory usages, durations, quantities.
- **contains**: Checks if ground truth appears within the answer or vice versa - used for time and severities.
- **fuzzy**: Sørensen–Dice bigram similarity coefficient - used for vague terms like engineer names and affected systems.
- **list**: Checks membership and intersection proportion for lists of strings - used for regions, endpoints, and cascades.

This multi-strategy approach provides **natural partial credit** to prevent sparse rewards, keeping models iteratively aligned during training.

## Setup & Usage

```bash
# Install dependencies
pip install openenv-core

# Run server locally
uvicorn server.app:app --host 0.0.0.0 --port 7860
```

## Docker

```bash
docker build -t incident-report-env .
docker run -p 7860:7860 incident-report-env
```

## Baseline Scores

Evaluated using `Qwen/Qwen2.5-72B-Instruct` via HuggingFace Inference Router.

| Task | Difficulty | Fields | Score |
|------|------------|--------|-------|
| easy_1 | Easy | 6 | 1.00 |
| easy_2 | Easy | 7 | 0.93 |
| easy_3 | Easy | 6 | 0.93 |
| medium_1 | Medium | 9 | 0.70 |
| medium_2 | Medium | 9 | 0.93 |
| medium_3 | Medium | 9 | 0.84 |
| hard_1 | Hard | 13 | 0.85 |
| hard_2 | Hard | 13 | 0.83 |
| hard_3 | Hard | 13 | 0.94 |
| **Average** | — | — | **0.885** |

## Running Inference

Set required environment variables then run:

### Linux/Mac
```bash
export HF_TOKEN="your_token"
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
python inference.py
```

### Windows PowerShell
```powershell
$env:HF_TOKEN="your_token"
$env:API_BASE_URL="https://router.huggingface.co/v1"
$env:MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
python inference.py
```

## Environment Variables Required
When running `inference.py`, the following environment variables MUST be provided:

| Variable | Description |
|----------|-------------|
| `API_BASE_URL` | The API endpoint for the LLM |
| `MODEL_NAME` | The model identifier |
| `HF_TOKEN` | Your Hugging Face / API key |

## Validation

To validate your submission locally:

```bash
chmod +x validate-submission.sh
./validate-submission.sh https://pratham-math-openenv-incident-rl.hf.space/
```