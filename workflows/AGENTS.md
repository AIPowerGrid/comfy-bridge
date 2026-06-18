# workflows — ComfyUI graph templates

## Purpose

ComfyUI workflow graphs (JSON) the worker loads and fills per job. One file per model/mode
(txt2img, img2img edit, video). `model_mapper.py` maps a grid model name to a file here;
`workflow.py` templates it.

## Ownership

- One `.json` per supported pipeline (e.g. `turbovision.json`, `flux1_krea_dev.json`,
  `flux2_klein_4b_api.json` + `..._image_edit.json`, `wan2_2_t2v_14b.json`, `sdxl.json`).
- `README.md` — authoring notes (placeholders, dynamic fields, required node types).
- Files may be in either ComfyUI native export (`nodes` array, `type` + `widgets_values`) or
  API export (`class_type` + `inputs`) form; `workflow.py` handles both.

## Local Contracts

- The worker fills only: prompt / negative prompt, seed, width / height, steps, cfg, batch_size
  (or video length/fps), output `filename_prefix` (`horde_<job_id>`), and the source image for
  img2img. Everything else (sampler, scheduler, LoRAs, model loaders) is preserved as authored.
- A graph is advertised only if its checkpoint file resolves to a grid model name (or it is in
  the mapper's defaults) — see root "advertise only what you can serve".
- Preferred: include a `_bridge` block (`version: 1`, `nodes`, `fields`) for explicit
  field mapping; without it the templater falls back to class-type/title heuristics.
- A `SaveImage`/`SaveVideo` node is required so outputs can be collected by filename prefix.

## Work Guidance

—

## Verification

—

## Child DOX Index

- None — leaf.
