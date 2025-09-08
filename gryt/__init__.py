"""
gryt: Minimal MVP of a Python-based CI framework.

This package provides core primitives:
- Data: SQLite-backed data store for structured outputs.
- Step: Base class for executable steps; CommandStep example provided.
- Runner: Sequential runner for steps.
- Pipeline: Compose runners; supports optional parallel execution.
- Runtime: Abstract runtime; LocalRuntime stub.
- Versioning: Simple git-based semver bump/tag operations using subprocess.

The package aims to minimize dependencies (stdlib-only for MVP) and
keep APIs simple, well-typed, and serializable for humans and AI agents.
"""

from .data import SqliteData, Data
from .languages.node import NpmBuildStep
from .step import Step, CommandStep
from .runner import Runner
from .pipeline import Pipeline
from .runtime import Runtime, LocalRuntime
from .versioning import Versioning, SimpleVersioning
from .hook import Hook, PrintHook, HttpHook
from .destination import Destination, CommandDestination, NpmRegistryDestination, PyPIDestination, GitHubReleaseDestination
from .publish import PublishDestinationStep
from .envvalidate import EnvValidator, EnvVarValidator, ToolValidator
from .containers import ContainerBuildStep
from .steps import (
    GoModDownloadStep,
    GoBuildStep,
    GoTestStep,
    PipInstallStep,
    PytestStep,
    NpmInstallStep,
    SvelteBuildStep,
    CargoBuildStep,
    CargoTestStep,
)

__all__ = [
    "Data",
    "SqliteData",
    "Step",
    "CommandStep",
    "Runner",
    "Pipeline",
    "Runtime",
    "LocalRuntime",
    "Versioning",
    "SimpleVersioning",
    # Hooks
    "Hook",
    "PrintHook",
    "HttpHook",
    # Destinations
    "Destination",
    "CommandDestination",
    "NpmRegistryDestination",
    "PyPIDestination",
    "GitHubReleaseDestination",
    "PublishDestinationStep",
    # Env validation
    "EnvValidator",
    "EnvVarValidator",
    "ToolValidator",
    # Containers
    "ContainerBuildStep",
    # Language-specific steps
    "GoModDownloadStep",
    "GoBuildStep",
    "GoTestStep",
    "PipInstallStep",
    "PytestStep",
    "NpmInstallStep",
    "NpmBuildStep",
    "SvelteBuildStep",
    "CargoBuildStep",
    "CargoTestStep",
]
