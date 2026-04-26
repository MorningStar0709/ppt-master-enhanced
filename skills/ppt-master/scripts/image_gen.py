#!/usr/bin/env python3
"""
Unified Image Generation Tool

Dispatches to the appropriate backend based on explicit provider configuration.

Backend selection (`IMAGE_BACKEND` in `.env` or the current process environment):
  IMAGE_BACKEND=gemini     -> Gemini backend (google-genai SDK)
  IMAGE_BACKEND=openai     -> OpenAI-compatible backend (openai SDK)
  IMAGE_BACKEND=minimax    -> MiniMax image backend
  IMAGE_BACKEND=stability  -> Stability AI backend
  IMAGE_BACKEND=bfl        -> Black Forest Labs FLUX backend
  IMAGE_BACKEND=ideogram   -> Ideogram backend
  IMAGE_BACKEND=qwen       -> Alibaba Qwen image backend
  IMAGE_BACKEND=zhipu      -> Zhipu GLM-Image backend
  IMAGE_BACKEND=volcengine -> Volcengine Seedream backend
  IMAGE_BACKEND=siliconflow -> SiliconFlow backend
  IMAGE_BACKEND=fal        -> fal.ai backend
  IMAGE_BACKEND=replicate  -> Replicate backend

Configuration source:
  1. Current process environment variables
  2. Repository-root `.env` as a fallback layer

Supported keys:
  IMAGE_BACKEND    (required) backend name

  Provider-specific keys are used for credentials and overrides, for example:
    GEMINI_API_KEY / GEMINI_MODEL / GEMINI_BASE_URL
    OPENAI_API_KEY / OPENAI_MODEL / OPENAI_BASE_URL
    QWEN_API_KEY / QWEN_MODEL / QWEN_BASE_URL
    ZHIPU_API_KEY / ZHIPU_MODEL / ZHIPU_BASE_URL

Usage:
  conda run -n ppt-master python image_gen.py "prompt" --aspect_ratio 16:9 --image_size 1K -o images/
  conda run -n ppt-master python image_gen.py --list-backends
  conda run -n ppt-master python image_gen.py --check-capability
"""

import os
import sys
import argparse
from pathlib import Path

try:
    from runtime_utils import configure_utf8_stdio, resolve_repo_root, safe_print
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from runtime_utils import configure_utf8_stdio, resolve_repo_root, safe_print  # type: ignore

REPO_ROOT = resolve_repo_root(__file__)
PRIMARY_ENV_PATH = REPO_ROOT / ".env"
IMAGE_ENV_PREFIXES = (
    "IMAGE_",
    "GEMINI_",
    "OPENAI_",
    "MINIMAX_",
    "STABILITY_",
    "BFL_",
    "IDEOGRAM_",
    "QWEN_",
    "DASHSCOPE_",
    "ZHIPU_",
    "BIGMODEL_",
    "VOLCENGINE_",
    "ARK_",
    "SILICONFLOW_",
    "FAL_",
    "REPLICATE_",
)
DEPRECATED_IMAGE_KEYS = {
    "IMAGE_API_KEY",
    "IMAGE_MODEL",
    "IMAGE_BASE_URL",
}

# All aspect ratios accepted by the unified CLI
# (each backend validates its own subset internally)
ALL_ASPECT_RATIOS = [
    "1:1", "1:4", "1:8",
    "2:3", "3:2", "3:4", "4:1", "4:3",
    "4:5", "5:4", "8:1", "9:16", "16:9", "21:9"
]

ALL_IMAGE_SIZES = ["512px", "1K", "2K", "4K"]

BACKEND_REGISTRY = {
    "gemini": {
        "module": "backend_gemini",
        "tier": "core",
        "label": "Google Gemini",
        "default_model": "gemini-3.1-flash-image-preview",
        "key_hint": "GEMINI_API_KEY",
        "aliases": ["google"],
    },
    "openai": {
        "module": "backend_openai",
        "tier": "core",
        "label": "OpenAI / OpenAI-compatible",
        "default_model": "gpt-image-1",
        "key_hint": "OPENAI_API_KEY",
        "aliases": ["openai-compatible", "openai_compatible"],
    },
    "minimax": {
        "module": "backend_minimax",
        "tier": "experimental",
        "label": "MiniMax Image",
        "default_model": "image-01",
        "key_hint": "MINIMAX_API_KEY",
        "aliases": ["minimaxi"],
    },
    "qwen": {
        "module": "backend_qwen",
        "tier": "core",
        "label": "Alibaba Qwen Image",
        "default_model": "qwen-image-2.0-pro",
        "key_hint": "QWEN_API_KEY / DASHSCOPE_API_KEY",
        "aliases": ["alibaba", "dashscope"],
    },
    "zhipu": {
        "module": "backend_zhipu",
        "tier": "core",
        "label": "Zhipu GLM-Image",
        "default_model": "glm-image",
        "key_hint": "ZHIPU_API_KEY / BIGMODEL_API_KEY",
        "aliases": ["bigmodel", "glm", "glm-image"],
    },
    "volcengine": {
        "module": "backend_volcengine",
        "tier": "core",
        "label": "Volcengine Seedream",
        "default_model": "doubao-seedream-4-5-251128",
        "key_hint": "VOLCENGINE_API_KEY / ARK_API_KEY",
        "aliases": ["ark", "doubao", "seedream"],
    },
    "stability": {
        "module": "backend_stability",
        "tier": "extended",
        "label": "Stability AI",
        "default_model": "stable-image-core",
        "key_hint": "STABILITY_API_KEY",
        "aliases": ["stabilityai", "stability-ai"],
    },
    "bfl": {
        "module": "backend_bfl",
        "tier": "extended",
        "label": "Black Forest Labs FLUX",
        "default_model": "flux-pro-1.1-ultra",
        "key_hint": "BFL_API_KEY",
        "aliases": ["flux", "black-forest-labs", "black_forest_labs"],
    },
    "ideogram": {
        "module": "backend_ideogram",
        "tier": "extended",
        "label": "Ideogram",
        "default_model": "ideogram-v3",
        "key_hint": "IDEOGRAM_API_KEY",
    },
    "siliconflow": {
        "module": "backend_siliconflow",
        "tier": "experimental",
        "label": "SiliconFlow",
        "default_model": "Qwen/Qwen-Image",
        "key_hint": "SILICONFLOW_API_KEY",
        "aliases": ["silicon"],
    },
    "fal": {
        "module": "backend_fal",
        "tier": "experimental",
        "label": "fal.ai",
        "default_model": "fal-ai/imagen3/fast",
        "key_hint": "FAL_KEY / FAL_API_KEY",
        "aliases": ["fal-ai"],
    },
    "replicate": {
        "module": "backend_replicate",
        "tier": "experimental",
        "label": "Replicate",
        "default_model": "black-forest-labs/flux-1.1-pro",
        "key_hint": "REPLICATE_API_TOKEN / REPLICATE_API_KEY",
    },
}

TIER_ORDER = {"core": 0, "extended": 1, "experimental": 2}
SUPPORTED_BACKENDS = tuple(sorted(BACKEND_REGISTRY))


def _is_image_env_key(name: str) -> bool:
    """Return whether an env var name belongs to image generation config."""
    return name.startswith(IMAGE_ENV_PREFIXES)


def _strip_env_quotes(value: str) -> str:
    """Strip matching surrounding quotes from a `.env` value."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _load_image_env_files() -> None:
    """
    Load image generation config from the repository-root `.env`.

    Existing process environment variables win over `.env`.
    """
    env_path = PRIMARY_ENV_PATH
    if not env_path.exists():
        return

    with env_path.open("r", encoding="utf-8") as fh:
        for lineno, raw_line in enumerate(fh, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("export "):
                line = line[7:].lstrip()

            if "=" not in line:
                raise ValueError(
                    f"Invalid line in {env_path}:{lineno}. Expected KEY=VALUE."
                )

            key, value = line.split("=", 1)
            key = key.strip()
            if not key:
                raise ValueError(
                    f"Invalid line in {env_path}:{lineno}. Missing variable name."
                )

            if not _is_image_env_key(key):
                continue

            if key in DEPRECATED_IMAGE_KEYS:
                replacement = {
                    "IMAGE_API_KEY": "GEMINI_API_KEY / OPENAI_API_KEY / QWEN_API_KEY / ZHIPU_API_KEY / ...",
                    "IMAGE_MODEL": "GEMINI_MODEL / OPENAI_MODEL / QWEN_MODEL / ZHIPU_MODEL / ...",
                    "IMAGE_BASE_URL": "GEMINI_BASE_URL / OPENAI_BASE_URL / QWEN_BASE_URL / ZHIPU_BASE_URL / ...",
                }[key]
                raise ValueError(
                    f"Unsupported key in {env_path}:{lineno}: {key}\n"
                    "Global image config keys have been removed.\n"
                    f"Use IMAGE_BACKEND plus provider-specific keys instead, such as {replacement}."
                )

            os.environ.setdefault(key, _strip_env_quotes(value.strip()))


def _reject_legacy_env_path() -> None:
    """Reject the deprecated `.trae/.env` location."""
    legacy_env_path = REPO_ROOT / ".trae" / ".env"
    if not legacy_env_path.exists():
        return
    raise ValueError(
        "Unsupported legacy image config path detected.\n"
        f"Found: {legacy_env_path}\n"
        f"Use repository-root .env only: {PRIMARY_ENV_PATH}\n"
        "Move image generation settings out of `.trae/.env` and rerun."
    )


def _validate_runtime_config() -> None:
    """Reject deprecated global image variables from any configuration source."""
    for key in DEPRECATED_IMAGE_KEYS:
        if key not in os.environ:
            continue
        replacement = {
            "IMAGE_API_KEY": "GEMINI_API_KEY / OPENAI_API_KEY / QWEN_API_KEY / ZHIPU_API_KEY / ...",
            "IMAGE_MODEL": "GEMINI_MODEL / OPENAI_MODEL / QWEN_MODEL / ZHIPU_MODEL / ...",
            "IMAGE_BASE_URL": "GEMINI_BASE_URL / OPENAI_BASE_URL / QWEN_BASE_URL / ZHIPU_BASE_URL / ...",
        }[key]
        raise ValueError(
            f"Unsupported image config key: {key}\n"
            "Global image config keys have been removed.\n"
            f"Use IMAGE_BACKEND plus provider-specific keys instead, such as {replacement}."
        )


def _build_backend_aliases() -> dict[str, str]:
    """Build a lookup from aliases to canonical backend names."""
    aliases = {}
    for canonical_name, config in BACKEND_REGISTRY.items():
        aliases[canonical_name] = canonical_name
        for alias in config.get("aliases", []):
            aliases[alias] = canonical_name
    return aliases


BACKEND_ALIASES = _build_backend_aliases()


_BACKEND_PIP_HINTS = {
    "gemini": "google-genai",
    "openai": "openai",
}


def _load_backend(canonical_name: str) -> tuple[object, str]:
    """Import and return the configured backend module."""
    module_name = f"image_backends.{BACKEND_REGISTRY[canonical_name]['module']}"
    try:
        module = __import__(module_name, fromlist=["*"])
    except ImportError as exc:
        pip_name = _BACKEND_PIP_HINTS.get(canonical_name, exc.name or "<dependency>")
        safe_print(
            f"Error: backend '{canonical_name}' needs a package that is not installed.\n"
            f"Missing: {exc.name}\n"
            f"Run: conda run -n ppt-master pip install {pip_name}",
            file=sys.stderr,
        )
        sys.exit(1)
    return module, canonical_name


def _resolve_key_hint_names(canonical_name: str) -> list[str]:
    """Expand configured key hints into concrete environment variable names."""
    key_hint = BACKEND_REGISTRY[canonical_name].get("key_hint", "")
    names: list[str] = []
    for part in key_hint.split("/"):
        name = part.strip()
        if name:
            names.append(name)
    return names


def _probe_backend(canonical_name: str) -> tuple[bool, list[str]]:
    """Return whether a backend looks usable without executing a generation call."""
    messages: list[str] = []
    key_names = _resolve_key_hint_names(canonical_name)
    present_keys = [name for name in key_names if os.environ.get(name, "").strip()]
    if present_keys:
        messages.append(f"credentials: OK ({', '.join(present_keys)})")
    else:
        if key_names:
            messages.append(f"credentials: MISSING ({' / '.join(key_names)})")
        else:
            messages.append("credentials: UNKNOWN")

    module_name = f"image_backends.{BACKEND_REGISTRY[canonical_name]['module']}"
    try:
        __import__(module_name, fromlist=["*"])
        messages.append("backend module: OK")
    except ImportError as exc:
        messages.append(f"backend module: MISSING DEPENDENCY ({exc.name or 'unknown'})")

    model_name = os.environ.get(f"{canonical_name.upper()}_MODEL", "").strip()
    if model_name:
        messages.append(f"model override: {model_name}")
    else:
        messages.append(f"default model: {BACKEND_REGISTRY[canonical_name]['default_model']}")

    usable = bool(present_keys)
    for message in messages:
        if "MISSING DEPENDENCY" in message:
            usable = False
            break
    return usable, messages


def _print_backend_list() -> None:
    """Print supported backends grouped by support tier."""
    safe_print("Supported image backends:\n")
    tiers = ("core", "extended", "experimental")
    for tier in tiers:
        safe_print(f"{tier.upper()}:")
        for name, info in sorted(
            BACKEND_REGISTRY.items(),
            key=lambda item: (TIER_ORDER[item[1]["tier"]], item[0]),
        ):
            if info["tier"] != tier:
                continue
            safe_print(
                f"  {name:<12} {info['label']} | default={info['default_model']} | keys={info['key_hint']}"
            )
        safe_print()
    safe_print("Recommendation: prefer CORE backends for everyday PPT generation.")
    safe_print(f"Config file: {PRIMARY_ENV_PATH}")


def _resolve_backend() -> tuple[object, str]:
    """
    Determine which backend to use from explicit configuration.

    Returns:
        A backend module with a generate() function.
    """
    backend_name = os.environ.get("IMAGE_BACKEND", "").strip().lower()
    if backend_name:
        canonical = BACKEND_ALIASES.get(backend_name)
        if not canonical:
            supported = ", ".join(SUPPORTED_BACKENDS)
            safe_print(f"Error: Unknown IMAGE_BACKEND='{backend_name}'. Supported: {supported}")
            sys.exit(1)
        return _load_backend(canonical)

    supported = ", ".join(SUPPORTED_BACKENDS)
    safe_print(
        "Error: No image backend configured.\n"
        "\n"
        "Set IMAGE_BACKEND explicitly in one of these places:\n"
        f"  1. Current process environment\n"
        f"  2. {PRIMARY_ENV_PATH}\n"
        "\n"
        f"Supported backends: {supported}\n"
        "\n"
        "Example:\n"
        "  IMAGE_BACKEND=gemini\n"
        "  GEMINI_API_KEY=your-key\n"
    )
    sys.exit(1)


def _current_backend_context(cli_backend: str | None) -> str:
    """Describe how the active backend was selected for troubleshooting output."""
    env_backend = os.environ.get("IMAGE_BACKEND", "").strip()
    if cli_backend:
        return (
            f"requested via --backend={cli_backend}; "
            f"effective IMAGE_BACKEND={env_backend or cli_backend}"
        )
    if env_backend:
        return f"resolved from IMAGE_BACKEND={env_backend}"
    return "no effective IMAGE_BACKEND was resolved"


def _check_capability(cli_backend: str | None) -> int:
    """Print whether automatic image generation is usable in the current environment."""
    configured_backend = (cli_backend or os.environ.get("IMAGE_BACKEND", "")).strip().lower()
    if not configured_backend:
        safe_print("[UNAVAILABLE] No image backend configured.")
        safe_print(f"Config file checked: {PRIMARY_ENV_PATH}")
        safe_print("Next step: use a non-AI fallback or configure IMAGE_BACKEND plus provider credentials.")
        return 1

    canonical = BACKEND_ALIASES.get(configured_backend)
    if not canonical:
        safe_print(f"[UNAVAILABLE] Unknown backend '{configured_backend}'.")
        safe_print(f"Supported backends: {', '.join(SUPPORTED_BACKENDS)}")
        return 1

    usable, messages = _probe_backend(canonical)
    status = "AVAILABLE" if usable else "UNAVAILABLE"
    safe_print(f"[{status}] backend={canonical}")
    safe_print(f"Selection context: {_current_backend_context(cli_backend)}")
    for message in messages:
        safe_print(f"  - {message}")
    if usable:
        safe_print("Automatic AI image generation can be used as a fallback in this environment.")
        return 0

    safe_print("Automatic AI image generation is not currently usable.")
    safe_print("Recommended fallback: verified local substitute / external sourcing / manual generation / labeled placeholder / layout redesign.")
    return 1


def main() -> None:
    """Run the CLI entry point."""
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Generate images using AI image model providers."
    )
    parser.add_argument(
        "prompt", nargs="?", default="a beautiful landscape",
        help="The text prompt for image generation."
    )
    parser.add_argument(
        "--negative_prompt", "-n", default=None,
        help="Negative prompt to specify what to avoid."
    )
    parser.add_argument(
        "--aspect_ratio", default="1:1", choices=ALL_ASPECT_RATIOS,
        help=f"Aspect ratio. Default: 1:1."
    )
    parser.add_argument(
        "--image_size", default="1K",
        help=f"Image size. Choices: {ALL_IMAGE_SIZES}. Default: 1K. (case-insensitive)"
    )
    parser.add_argument(
        "--output", "-o", default=None,
        help="Output directory. Default: current directory."
    )
    parser.add_argument(
        "--filename", "-f", default=None,
        help="Output filename (without extension). Overrides auto-naming."
    )
    parser.add_argument(
        "--model", "-m", default=None,
        help="Model name. Default depends on backend."
    )
    parser.add_argument(
        "--backend", "-b", default=None, choices=SUPPORTED_BACKENDS,
        help="Override IMAGE_BACKEND env var."
    )
    parser.add_argument(
        "--list-backends", action="store_true",
        help="List available backends grouped by support tier and exit."
    )
    parser.add_argument(
        "--check-capability", action="store_true",
        help="Check whether automatic AI image generation is usable in the current environment and exit."
    )

    args = parser.parse_args()

    if args.list_backends:
        _print_backend_list()
        return

    try:
        _reject_legacy_env_path()
        _load_image_env_files()
        _validate_runtime_config()
    except ValueError as e:
        safe_print(f"Error: {e}")
        sys.exit(1)

    # CLI --backend overrides the value loaded from .env
    if args.backend:
        os.environ["IMAGE_BACKEND"] = args.backend

    if args.check_capability:
        sys.exit(_check_capability(args.backend))

    backend, backend_name = _resolve_backend()
    safe_print(f"Using backend: {backend_name}\n")

    try:
        backend.generate(
            prompt=args.prompt,
            negative_prompt=args.negative_prompt,
            aspect_ratio=args.aspect_ratio,
            image_size=args.image_size,
            output_dir=args.output,
            filename=args.filename,
            model=args.model,
        )
    except (ValueError, FileNotFoundError) as e:
        safe_print(f"Error while using backend '{backend_name}': {e}")
        safe_print(
            "Hint: check provider-specific API keys, model overrides, output paths, "
            "and whether this backend is configured in the current environment."
        )
        safe_print(f"Backend selection context: {_current_backend_context(args.backend)}")
        sys.exit(1)
    except RuntimeError as e:
        safe_print(f"Error while using backend '{backend_name}': {e}")
        safe_print(
            "Hint: this usually means a provider-side request/configuration failure, "
            "not that .env blocked --backend from taking effect."
        )
        safe_print(f"Backend selection context: {_current_backend_context(args.backend)}")
        sys.exit(1)
    except KeyboardInterrupt:
        safe_print("\n\nInterrupted by user.")
        sys.exit(130)


if __name__ == "__main__":
    main()
