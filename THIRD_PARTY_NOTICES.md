# Third-party and generated-asset notices

KHALINOS is original project code created for the All Things Agentic Hackathon. Its Python environment and container images install third-party components rather than relicensing them as KHALINOS code.

## Runtime and development dependencies

| Component | Role | Upstream license or terms |
| --- | --- | --- |
| Google ADK and Google Cloud Python clients | Agent framework and Google Cloud access | Apache License 2.0; see the respective Google repositories and package metadata |
| FastAPI and Pydantic | API and schemas | MIT License |
| Uvicorn | ASGI server | BSD 3-Clause License |
| Playwright | Browser runtime automation | Apache License 2.0 |
| Pillow | Image inspection | HPND License |
| Godot Engine 4.7.1 | Trusted Godot runtime | MIT License |
| Chromium and Liberation fonts | Container browser and fonts | Upstream Chromium and font package licenses |
| rembg | Sprite-background segmentation integration | MIT License |

The exact Python dependency versions used by KHALINOS are declared in `pyproject.toml`. Container build inputs and digest checks are declared in `Dockerfile` and `Dockerfile.godot`.

## Model and generated assets

- Gemini 3.5 Flash, Gemini multimodal evaluation, and Nano Banana image generation are accessed through Vertex AI under the applicable Google Cloud and generative-AI service terms.
- The repository-contained combat-effect sheets were created for KHALINOS with OpenAI's built-in ImageGen. Their source hashes, selection bindings, composed atlas digest, and generation receipt are preserved in the evidence files; no third-party stock-art ownership is claimed.
- An optional development-only licensed-art qualification used user-approved AetherAI free assets under the AetherAI Free Asset License dated 2026-06-29. The original assets remain in an external local library, are not redistributed as a standalone KHALINOS asset pack, and were not bundled into the latest Cloud-qualified image. Generated game ZIPs may contain only bounded composed derivatives plus their source and license receipts when that opt-in path is enabled.
- Images stored in the evidence directories or generated result ZIPs were created for KHALINOS runs. They are not represented as third-party endorsements, trademarks, or pre-existing game art.
- `isnet-anime.onnx` is downloaded from the upstream `rembg` release location and SHA-256 verified during the Godot image build. Its upstream distribution terms apply; KHALINOS does not claim ownership of the model weights.

No Google, Godot, Chromium, or other third-party name or mark is used to imply sponsorship of KHALINOS beyond the hackathon and technology relationships stated in the submission.
