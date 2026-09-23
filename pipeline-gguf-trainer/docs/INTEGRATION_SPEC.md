# Integration Specification: Future Higher Stack & Cockpit Integration

## 1. Overview

This document specifies the exact API contracts, endpoints, and data payloads for future integration of the GGUF Training Pipeline into the higher stack:
- **StoneSage Cockpit (`:8080`)**: Web HUD and mobile app training panel.
- **Cluster MCP Bridge (`:8765`)**: Native MCP tools for autonomous self-training cycles.

---

## 2. API Endpoints & Payload Contracts

### 2.1 Ingest Deep Sleep Dossiers
- **Endpoint**: `POST /api/trainer/ingest/sleep`
- **Description**: Triggers collection and curation of recent exploration dossiers into SFT and DPO formats.
- **Request Body**:
  ```json
  {
    "limit": 50,
    "min_score_delta": 1,
    "frontier_only": false
  }
  ```
- **Response**:
  ```json
  {
    "status": "success",
    "dossiers_parsed": 50,
    "sft_samples_generated": 50,
    "dpo_pairs_generated": 48,
    "sft_file": "/opt/pipeline-gguf-trainer/data/processed/sleep_cycles_sft.jsonl",
    "dpo_file": "/opt/pipeline-gguf-trainer/data/processed/sleep_cycles_dpo.jsonl"
  }
  ```

### 2.2 Ingest External URL
- **Endpoint**: `POST /api/trainer/ingest/url`
- **Description**: Scrapes URL, bounds into < 900 char chunks, and synthesizes QA instruction pairs.
- **Request Body**:
  ```json
  {
    "url": "https://unsloth.ai/docs/get-started/fine-tuning-llms-guide"
  }
  ```
- **Response**:
  ```json
  {
    "status": "success",
    "url": "https://unsloth.ai/docs/get-started/fine-tuning-llms-guide",
    "chunks_extracted": 14,
    "qa_pairs_generated": 14,
    "output_file": "/opt/pipeline-gguf-trainer/data/processed/url_qa.jsonl"
  }
  ```

### 2.3 Trigger Training Run
- **Endpoint**: `POST /api/trainer/train`
- **Description**: Launches asynchronous QLoRA or DPO training run.
- **Request Body**:
  ```json
  {
    "mode": "sft",
    "target_model": "ornith-1.5-9b",
    "steps": 60,
    "dataset": "sleep_cycles_sft.jsonl",
    "quant_target": "q4_k_m"
  }
  ```
- **Response**:
  ```json
  {
    "task_id": "train-20260910-001",
    "status": "training_started",
    "estimated_duration_sec": 180
  }
  ```

### 2.4 Query Live Training Status
- **Endpoint**: `GET /api/trainer/status`
- **Response**:
  ```json
  {
    "status": "running",
    "progress_percent": 65.0,
    "current_step": 39,
    "total_steps": 60,
    "current_loss": 0.842,
    "vram_allocated_gb": 8.4,
    "safety_check": {
      "passed": true,
      "pass_rate": 1.0
    }
  }
  ```

### 2.5 Promote Model to Cluster Production
- **Endpoint**: `POST /api/trainer/promote`
- **Description**: Deploys staged GGUF model to `/opt/models/` and restarts the corresponding `llama-coordinator` or `llama-worker` systemd service.
- **Request Body**:
  ```json
  {
    "staged_gguf": "/opt/pipeline-gguf-trainer/output/gguf/ornith-1.5-9b-trained-q4_k_m.gguf",
    "target_role": "worker",
    "user_approval": true
  }
  ```
- **Response**:
  ```json
  {
    "status": "promoted",
    "deployed_path": "/opt/models/ornith-1.5-9b-worker-q4_k_m.gguf",
    "backup_path": "/opt/models/ornith-1.5-9b-worker-q4_k_m.gguf.bak",
    "service_restarted": "llama-worker"
  }
  ```

---

## 3. Future MCP Bridge Integration

When integrating into `mcp_server.py` on `:8765`, register these three native tools:
1. `pipeline_ingest_source(source_type, source_path_or_url)`
2. `pipeline_start_training(mode, steps, target_model)`
3. `pipeline_check_status_and_safety()`
