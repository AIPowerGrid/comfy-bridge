import json
import os
import struct
from glob import glob
from typing import Dict, Tuple, Any, Optional


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def read_png_text_chunks(path: str) -> Dict[str, str]:
    """Parse PNG tEXt/iTXt chunks and return a mapping of keyword -> text.

    - Supports tEXt: keyword\0text
    - Best-effort iTXt (uncompressed only): keyword\0flag\0method\0lang\0translated\0text
    """
    chunks: Dict[str, str] = {}
    with open(path, "rb") as f:
        sig = f.read(8)
        if sig != PNG_SIGNATURE:
            # Not a PNG or missing signature; try naive scan for 'tEXt'
            raw = sig + f.read(64 * 1024)
            idx = raw.find(b"tEXt")
            if idx != -1:
                # heuristic: try to parse simple keyword\0text after marker
                # This is purely best-effort for malformed inputs
                tail = raw[idx + 4 : idx + 4096]
                try:
                    nul = tail.index(b"\x00")
                    key = tail[:nul].decode(errors="ignore")
                    val = tail[nul + 1 :].decode(errors="ignore")
                    chunks[key] = val
                except Exception:
                    pass
            return chunks

        while True:
            len_bytes = f.read(4)
            if len(len_bytes) < 4:
                break
            (length,) = struct.unpack(">I", len_bytes)
            ctype = f.read(4)
            data = f.read(length)
            _crc = f.read(4)
            if len(ctype) < 4 or len(data) < length:
                break
            if ctype == b"tEXt":
                # keyword\0text
                try:
                    nul = data.index(b"\x00")
                    key = data[:nul].decode("latin1", errors="ignore")
                    val = data[nul + 1 :].decode("latin1", errors="ignore")
                    chunks[key] = val
                except Exception:
                    pass
            elif ctype == b"iTXt":
                # keyword\0compression_flag(1)\0compression_method(1)\0lang\0translated\0text
                try:
                    # Split by NULs for first 5 fields
                    parts = data.split(b"\x00", 5)
                    if len(parts) == 6:
                        key = parts[0].decode("utf-8", errors="ignore")
                        compression_flag = parts[1][:1]
                        # If compressed (flag==1), skip for simplicity
                        if compression_flag == b"\x01":
                            continue
                        # text is the last part
                        text = parts[5].decode("utf-8", errors="ignore")
                        chunks[key] = text
                except Exception:
                    pass
    return chunks


def summarize_prompt(prompt_text: str) -> Dict[str, Any]:
    """Extract key fields from the Comfy prompt JSON stored in the 'prompt' chunk."""
    summary: Dict[str, Any] = {
        "positive_text": None,
        "negative_text": None,
        "ksampler": {},
        "unet_name": None,
        "clip_name": None,
        "width": None,
        "height": None,
    }
    try:
        wf = json.loads(prompt_text)
        # Identify nodes
        ksampler_id: Optional[str] = None
        for nid, node in wf.items():
            if isinstance(node, dict) and node.get("class_type") == "KSampler":
                ksampler_id = nid
                inputs = node.get("inputs", {}) or {}
                summary["ksampler"] = {
                    "seed": inputs.get("seed"),
                    "steps": inputs.get("steps"),
                    "cfg": inputs.get("cfg"),
                    "sampler_name": inputs.get("sampler_name"),
                    "scheduler": inputs.get("scheduler"),
                    "denoise": inputs.get("denoise"),
                }
                break

        # Map positive/negative connections
        pos_ref = None
        neg_ref = None
        if ksampler_id is not None:
            ks_inputs = wf[ksampler_id].get("inputs", {}) or {}
            pos_ref = ks_inputs.get("positive")
            neg_ref = ks_inputs.get("negative")
            pos_id = str(pos_ref[0]) if isinstance(pos_ref, list) and pos_ref else None
            neg_id = str(neg_ref[0]) if isinstance(neg_ref, list) and neg_ref else None
        else:
            pos_id = neg_id = None

        for nid, node in wf.items():
            if not isinstance(node, dict):
                continue
            ctype = node.get("class_type")
            inputs = node.get("inputs", {}) or {}
            if ctype == "CLIPTextEncode":
                text = inputs.get("text")
                if str(nid) == str(pos_id):
                    summary["positive_text"] = text
                if str(nid) == str(neg_id):
                    summary["negative_text"] = text
            elif ctype == "UNETLoader":
                summary["unet_name"] = inputs.get("unet_name")
            elif ctype == "CLIPLoader":
                if not summary["clip_name"]:
                    summary["clip_name"] = inputs.get("clip_name")
            elif ctype in ("EmptyLatentImage", "EmptySD3LatentImage"):
                summary["width"] = inputs.get("width")
                summary["height"] = inputs.get("height")
    except Exception as e:
        summary["error"] = f"Failed to parse prompt JSON: {e}"
    return summary


def compare_dicts(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Tuple[Any, Any]]:
    keys = set(a.keys()) | set(b.keys())
    diffs: Dict[str, Tuple[Any, Any]] = {}
    for k in sorted(keys):
        if a.get(k) != b.get(k):
            diffs[k] = (a.get(k), b.get(k))
    return diffs


def main() -> None:
    base_dir = os.getcwd()
    horde_files = sorted(glob(os.path.join(base_dir, "horde_*.png")))
    comfy_files = sorted(glob(os.path.join(base_dir, "ComfyUI_*.png")))
    if not horde_files or not comfy_files:
        print("No files found. Put a horde_*.png and a ComfyUI_*.png in tests/image_compare/")
        return

    horde = horde_files[0]
    comfy = comfy_files[0]

    print(f"Comparing:\n- Bridge: {os.path.basename(horde)}\n- Native: {os.path.basename(comfy)}\n")

    h_txt = read_png_text_chunks(horde)
    c_txt = read_png_text_chunks(comfy)

    print(f"Text keys (bridge): {sorted(h_txt.keys())}")
    print(f"Text keys (native): {sorted(c_txt.keys())}\n")

    # Extract prompt chunk summaries
    h_prompt = h_txt.get("prompt", "")
    c_prompt = c_txt.get("prompt", "")

    h_sum = summarize_prompt(h_prompt) if h_prompt else {"error": "No prompt chunk"}
    c_sum = summarize_prompt(c_prompt) if c_prompt else {"error": "No prompt chunk"}

    print("Bridge summary:")
    print(json.dumps(h_sum, indent=2)[:4000])
    print("\nNative summary:")
    print(json.dumps(c_sum, indent=2)[:4000])

    print("\n=== ACTUAL PROMPT CONTENT ===")
    print("Bridge prompt (first 1000 chars):")
    print(h_prompt[:1000] if h_prompt else "No prompt")
    print("\nNative prompt (first 1000 chars):")
    print(c_prompt[:1000] if c_prompt else "No prompt")

    print("\nDifferences:")
    diffs = compare_dicts(h_sum, c_sum)
    if not diffs:
        print("(No differences in summarized fields)")
    else:
        print(json.dumps(diffs, indent=2)[:4000])


if __name__ == "__main__":
    main()


