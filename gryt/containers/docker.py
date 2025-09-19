from __future__ import annotations

from typing import Any, Dict, List, Optional
from pathlib import Path

from ..step import Step


class ContainerBuildStep(Step):
    """Build a container image using the Docker SDK for Python (if available).

    This step avoids shelling out to the `docker` CLI. It attempts to use the
    docker Python SDK (docker-py). If the SDK is not installed or the daemon
    is not available, it returns a structured error with guidance.

    Config options:
    - context_path: str (required) – build context directory containing Dockerfile
    - dockerfile: str (default 'Dockerfile') – relative path within context
    - tags: List[str] | str – one or more tags to apply (e.g., 'repo/name:tag')
    - build_args: Dict[str, str] – build arguments
    - labels: Dict[str, str] – image labels
    - platform: str – e.g., 'linux/amd64'
    - target: str – build target stage
    - network: str – build network mode
    - pull: bool – attempt to pull newer base images
    - push: bool – also push the tagged image(s) after build (requires registry auth)
    - decode_stream: bool (default True) – decode build output stream into list of messages

    Returns dict with keys:
    - status: 'success' | 'error'
    - image_id: str (on success)
    - tags: List[str]
    - logs: List[dict] (build output; truncated to a reasonable size)
    - push: Dict[tag, Any] (if push=True)
    - error: str (on error)
    """

    def run(self) -> Dict[str, Any]:
        cfg = self.config
        try:
            import docker  # type: ignore
            from docker.errors import DockerException  # type: ignore
        except Exception:
            return {
                "status": "error",
                "error": "Docker SDK for Python not installed. Install with 'pip install docker' or add it to your environment.",
            }

        context_path = cfg.get("context_path")
        if not context_path:
            return {"status": "error", "error": "config['context_path'] is required"}

        ctx = Path(context_path)
        if not ctx.exists() or not ctx.is_dir():
            return {"status": "error", "error": f"context_path does not exist or is not a directory: {ctx}"}

        dockerfile = cfg.get("dockerfile", "Dockerfile")
        tags = cfg.get("tags")
        if isinstance(tags, str):
            tags_list: List[str] = [tags]
        else:
            tags_list = list(tags or [])

        build_args: Optional[Dict[str, str]] = cfg.get("build_args")
        labels: Optional[Dict[str, str]] = cfg.get("labels")
        platform: Optional[str] = cfg.get("platform")
        target: Optional[str] = cfg.get("target")
        network: Optional[str] = cfg.get("network")
        pull: bool = bool(cfg.get("pull", False))
        push: bool = bool(cfg.get("push", False))
        decode_stream: bool = bool(cfg.get("decode_stream", True))
        # Optional: buildkit features are daemon-side; we don't toggle here.

        client = None
        try:
            client = docker.from_env()
        except Exception as e:  # noqa: BLE001
            return {"status": "error", "error": f"Failed to connect to Docker daemon: {e}"}

        logs: List[Dict[str, Any]] = []
        image_id: Optional[str] = None
        try:
            # Low-level API provides streaming logs
            low = client.api
            build_params: Dict[str, Any] = {
                "path": str(ctx),
                "dockerfile": dockerfile,
                "tag": tags_list[0] if tags_list else None,
                "buildargs": build_args,
                "decode": decode_stream,
                "pull": pull,
            }
            if platform:
                build_params["platform"] = platform
            if target:
                build_params["target"] = target
            if network:
                build_params["network_mode"] = network
            if labels:
                build_params["labels"] = labels

            # Remove None-valued keys to avoid API issues
            build_params = {k: v for k, v in build_params.items() if v is not None}

            stream = low.build(**build_params)
            # stream is a generator of dicts when decode=True; otherwise bytes
            show = bool(getattr(self, "show", False))
            for chunk in stream:
                if isinstance(chunk, (bytes, bytearray)):
                    # Best-effort decoding
                    try:
                        msg = chunk.decode("utf-8", errors="ignore")
                        logs.append({"stream": msg})
                        if show:
                            print(msg, end="", flush=True)
                    except Exception:
                        logs.append({"raw": "<binary>"})
                else:
                    logs.append(chunk)
                    # Also print text messages if requested
                    if show:
                        text = chunk.get("stream") or chunk.get("status") or chunk.get("errorDetail", {}).get("message")
                        if text:
                            print(str(text), end="\n" if not str(text).endswith("\n") else "", flush=True)
                    # Try to capture image id from aux events
                    aux = chunk.get("aux") if isinstance(chunk, dict) else None
                    if isinstance(aux, dict) and aux.get("ID"):
                        image_id = aux.get("ID")
            # If no aux ID, try to find image by tag if provided
            if not image_id:
                if tags_list:
                    try:
                        img = client.images.get(tags_list[0])
                        image_id = img.id
                    except Exception:
                        pass
                # Or inspect last build log for image id
                if not image_id:
                    for entry in reversed(logs):
                        if isinstance(entry, dict):
                            aux = entry.get("aux")
                            if isinstance(aux, dict) and aux.get("ID"):
                                image_id = aux.get("ID")
                                break

            # Tag additional tags if provided
            if image_id and len(tags_list) > 1:
                try:
                    img_obj = client.images.get(image_id)
                    for t in tags_list[1:]:
                        # Split repo:tag
                        t = t.lower()
                        if ":" in t:
                            repo, tag = t.rsplit(":", 1)
                        else:
                            repo, tag = t, None
                        img_obj.tag(repository=repo, tag=tag)
                except Exception:
                    # Non-fatal if tagging extra tags fails
                    pass

            push_results: Dict[str, Any] = {}
            if push and tags_list:
                for t in tags_list:
                    try:
                        # client.images.push returns a string stream; use low-level for decode
                        for line in client.api.push(repository=t, stream=True, decode=True):
                            push_results.setdefault(t, []).append(line)
                            if bool(getattr(self, "show", False)):
                                # Print status lines from push as they arrive
                                text = line.get("status") or line.get("errorDetail", {}).get("message") or line.get("progressDetail")
                                if text:
                                    print(str(text), flush=True)
                    except Exception as e:  # noqa: BLE001
                        push_results[t] = [{"error": str(e)}]

            result = {
                "status": "success",
                "image_id": image_id,
                "tags": tags_list,
                # Truncate logs to avoid oversized JSON
                "logs": logs[-500:],
            }
            if push:
                result["push"] = push_results

            # Persist to data store if available
            if self.data:
                self.data.insert(
                    "steps_output",
                    {
                        "step_id": self.id,
                        "runner_id": None,
                        "name": self.id,
                        "output_json": result,
                        "stdout": "\n".join([e.get("stream", "") if isinstance(e, dict) else str(e) for e in result.get("logs", [])])[:100000],
                        "stderr": None,
                        "status": result.get("status"),
                        "duration": result.get("duration"),
                    },
                )
            return result
        except DockerException as e:  # noqa: F821
            err = {
                "status": "error",
                "error": str(e),
            }
            if self.data:
                self.data.insert(
                    "steps_output",
                    {
                        "step_id": self.id,
                        "runner_id": None,
                        "name": self.id,
                        "output_json": err,
                        "stdout": None,
                        "stderr": err.get("error"),
                        "status": err.get("status"),
                        "duration": None,
                    },
                )
            return err
        except Exception as e:  # noqa: BLE001
            err = {
                "status": "error",
                "error": str(e),
            }
            if self.data:
                self.data.insert(
                    "steps_output",
                    {
                        "step_id": self.id,
                        "runner_id": None,
                        "name": self.id,
                        "output_json": err,
                        "stdout": None,
                        "stderr": err.get("error"),
                        "status": err.get("status"),
                        "duration": None,
                    },
                )
            return err
        finally:
            try:
                if client is not None:
                    client.close()
            except Exception:
                pass
