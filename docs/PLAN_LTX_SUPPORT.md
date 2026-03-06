# Plan: Add LTX Support to the Bridge

This document outlines the steps to add **LTX / LTX-2** (Lightricks text-to-video) support to the ComfyUI Bridge for AI Power Grid, so the bridge can accept video-generation jobs and run them via ComfyUI with LTX-2 workflows.

---

## 1. Current State

- **Bridge**: Receives jobs from AI Power Grid, converts them to ComfyUI workflows, runs on local ComfyUI, returns images or videos.
- **Job payload**: Already supports `media_type` (image/video), `source_processing` (txt2img, img2img, img2video), `payload.length` (frames), `payload.fps`; R2 upload and `_submit_result(..., media_type="video")` are implemented.
- **Workflows**: `workflows/` contains several LTX-2 JSON files:
  - **API format** (usable by bridge): `ltx2_text_to_video.json`, `ltx2_distilled.json`, `ltx2_i2v.json` (has SaveVideo).
  - **Web UI format** (rejected by bridge): `ltx2.json`, `LTX-2_T2V_Distilled_wLora.json` — would need to be re-exported as API format if used.
- **Legacy workflow updater**: Already has special handling for `LTXVScheduler`, `EmptyLTXVLatentVideo`, `RandomNoise`, and `SaveVideo` / `VHS_VideoCombine`.
- **Gap**: No LTX-specific model mapping, no `_bridge` metadata on LTX workflows, worker is registered as image-only, and there is no clear path to “use LTX workflow when job is video or model is LTX”.

---

## 2. Goals

1. **Advertise LTX/video capability** so the grid can send video (and optionally img2video) jobs to this worker.
2. **Map grid model names** (e.g. `LTX-2`, `ltx`, `ltxv`) to the correct ComfyUI checkpoint / config.
3. **Use an LTX workflow** when the job is for video or the requested model is LTX (workflow selection by model and/or media type).
4. **Inject job parameters** into LTX workflows in a reliable way (prompt, negative, seed, dimensions, length, steps, cfg, source image for i2v) via `_bridge` metadata where possible.
5. **Return video** from ComfyUI (SaveVideo / VHS_VideoCombine) and submit it correctly to the grid.

---

## 3. Implementation Plan

### Phase 1: Model mapping and worker registration

| Step | Description |
|------|-------------|
| 1.1 | **Model mapper** (`model_mapper.py`): Add LTX entries to `DEFAULT_MODEL_MAP` and extend `_build_model_map()` so that grid model names such as `LTX-2`, `ltx-2`, `ltx`, `ltxv`, `LTX-2 19B Distilled` map to the checkpoint filename used by your LTX workflows (e.g. `ltx-2-19b-distilled-fp8.safetensors`). |
| 1.2 | **Auto-detect LTX checkpoints**: In `get_comfyui_models()` or `_build_model_map()`, detect checkpoints whose names contain `ltx` / `ltx-2` and register them as LTX models for the grid. |
| 1.3 | **Worker registration** (`bridge.py`): If the grid API supports a video worker type or a list of types, add support for advertising video (e.g. `worker_type: "video"` or a second registration for video). If the API only supports a single type, document that users can run a second bridge instance with an LTX workflow and video model. Keep current image registration unchanged when not advertising LTX. |
| 1.4 | **Config**: Document (e.g. in README and `.env.example`) how to advertise an LTX model: e.g. `GRID_MODEL=LTX-2` or `ltx-2-19b-distilled`, and optionally `WORKFLOW_FILE=ltx2_distilled.json` or a new bridge-ready LTX workflow. |

### Phase 2: Workflow selection and LTX-specific workflow

| Step | Description |
|------|-------------|
| 2.1 | **Workflow selection**: When `WORKFLOW_FILE` is set, keep current behavior (single workflow for all jobs). Optionally add logic so that when the job’s `media_type` is `video` or the job’s `model` maps to an LTX checkpoint, the bridge can use a dedicated LTX workflow (e.g. from `WORKFLOW_FILE_VIDEO` or `WORKFLOW_FILE_LTX` env var, or a convention like `workflows/ltx2_bridge_api.json`). |
| 2.2 | **Create or choose an API-format LTX workflow** that: (a) outputs **video** (SaveVideo or VHS_VideoCombine), (b) is in API format (dict keyed by node id, no top-level `nodes` array), (c) uses a single checkpoint so the bridge can override only what’s needed. Prefer starting from `ltx2_distilled.json` or `ltx2_text_to_video.json` and adding a SaveVideo node, or from `ltx2_i2v.json` for img2video. |
| 2.3 | **Add `_bridge` metadata** to that workflow (see Section 4) so the bridge can inject prompt, negative (if supported), seed, steps, cfg, width, height, length, and optionally source_image, without relying on legacy node scanning. |

### Phase 3: Bridge workflow update logic for LTX

| Step | Description |
|------|-------------|
| 3.1 | **_update_workflow_with_metadata**: Ensure `_bridge` supports a `video_latent` node and a `conditioning` (or prompt) node that matches LTX (e.g. CLIPTextEncode feeding into LTXVConditioning, or the node that feeds positive/negative into LTXVConditioning). Already partially present; extend if LTX uses different node IDs or field names. |
| 3.2 | **LTX-specific fields**: In the chosen LTX workflow, map `_bridge.fields` (and nodes) for: prompt (and negative if applicable), seed, steps, cfg, width, height, length. For img2video, map `source_image` to the LoadImage (or preprocess) node. |
| 3.3 | **Legacy path**: If an LTX workflow is used without `_bridge`, the legacy updater already handles `EmptyLTXVLatentVideo`, `LTXVScheduler`, `SaveVideo`/`VHS_VideoCombine`. Add or verify handling for **LTXVConditioning** (e.g. do not overwrite its inputs if the prompt is applied upstream; or identify the CLIPTextEncode nodes that feed it and update those). |
| 3.4 | **Output filename**: Ensure the output node (SaveVideo / VHS_VideoCombine) gets `filename_prefix` like `video/aipg_{job_id}` or `aipg_{job.id}` so results are identifiable and `_get_generated_media` can find the video. |

### Phase 4: End-to-end and docs

| Step | Description |
|------|-------------|
| 4.1 | **Test**: Run the bridge with `WORKFLOW_FILE=<ltx_bridge_workflow>.json` and `GRID_MODEL=LTX-2` (or equivalent), and verify: job received, workflow submitted, ComfyUI produces video, bridge downloads it and submits with `media_type=video` and correct R2/content-type. |
| 4.2 | **Docs**: Update README with an “LTX-2 / Video” section: required ComfyUI nodes (ComfyUI-LTXVideo or equivalent), model paths, env vars (`GRID_MODEL`, `WORKFLOW_FILE`), and that video jobs return MP4 (or the actual format) via R2 or base64. |
| 4.3 | **Optional**: Add a small table in README mapping grid model names to suggested workflow files (e.g. `LTX-2` → `ltx2_bridge_api.json`). |

---

## 4. Suggested `_bridge` metadata for an LTX workflow

Example structure for a text-to-video LTX workflow (adjust node IDs to match the real workflow):

```json
"_bridge": {
  "version": 1,
  "name": "LTX-2 T2V",
  "media_type": "video",
  "supports_negative": true,
  "nodes": {
    "prompt": "3",
    "negative_prompt": "4",
    "sampler": "7",
    "latent": null,
    "video_latent": "6",
    "output": "9",
    "source_image": "98"
  },
  "fields": {
    "prompt": "text",
    "negative_prompt": "text",
    "seed": "seed",
    "width": "width",
    "height": "height",
    "steps": "steps",
    "cfg": "cfg",
    "length": "length"
  }
}
```

- For **ltx2_distilled.json**-style flows: prompt/negative may feed into **LTXVConditioning**; then the node IDs in `nodes` should point to the CLIPTextEncode (or equivalent) nodes that feed into LTXVConditioning, and `sampler` to the KSampler, `video_latent` to `EmptyLTXVLatentVideo`, `output` to SaveVideo (if you add it) or the node that produces the final video.
- If the workflow uses **SaveImage** for frames only: either add a SaveVideo (or VHS) node and point `output` to it, or document that this workflow is frame-only and the bridge would need to assemble frames into video (out of scope for initial LTX support; prefer workflows that output video directly).

---

## 5. File checklist

| File | Action |
|------|--------|
| `model_mapper.py` | Add LTX model names and optional LTX checkpoint detection. |
| `bridge.py` | Optional: video worker registration; workflow selection by media_type/model; ensure _bridge and legacy paths handle LTX prompt/conditioning/video_latent/output. |
| `workflows/` | Add one API-format LTX workflow with SaveVideo (or VHS) and `_bridge` metadata (e.g. `ltx2_bridge_api.json` or extend `ltx2_distilled.json`). |
| `README.md` | Document LTX/video setup, env vars, and model/workflow mapping. |
| `.env.example` | Add `WORKFLOW_FILE_VIDEO` or `WORKFLOW_FILE_LTX` and example `GRID_MODEL=LTX-2` if implemented. |

---

## 6. Risks and notes

- **Grid API**: Confirm whether the grid expects `worker_type: "video"` (or similar) for video jobs and whether pop/submit payloads differ for video (e.g. `media_type`, R2, content-type). The bridge already sends `media_type: "video"` on submit; registration side may need to match.
- **ComfyUI-LTXVideo**: LTX workflows depend on ComfyUI-LTXVideo (or equivalent) custom nodes. Document this clearly so users install the right stack.
- **Resource usage**: Video jobs are heavier than image jobs; consider documenting recommended `GRID_THREADS` and GPU memory for LTX-2.
- **Web UI vs API workflows**: `ltx2.json` and `LTX-2_T2V_Distilled_wLora.json` are Web UI format; the bridge requires API format. Either export them from ComfyUI as “API format” or maintain a separate, minimal API-format LTX workflow for the bridge.

---

## 7. Summary

Adding LTX support requires: (1) mapping grid model names to LTX checkpoints and optionally advertising video workers, (2) selecting an API-format LTX workflow that outputs video and adding `_bridge` metadata, (3) ensuring the bridge’s metadata and legacy updaters correctly set prompt, seed, dimensions, length, and source image for LTX nodes, and (4) documenting setup and optional env vars. The existing code already handles video output and submission; the main work is model mapping, workflow selection, a single bridge-ready LTX workflow with `_bridge`, and registration/docs.
