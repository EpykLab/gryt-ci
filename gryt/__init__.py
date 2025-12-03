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
from .hook import Hook, PrintHook, HttpHook, PolicyHook, ChangeTypeHook
from .destination import Destination, CommandDestination, NpmRegistryDestination, PyPIDestination, GitHubReleaseDestination, ContainerRegistryDestination, SlackDestination, PrometheusDestination
from .publish import PublishDestinationStep
from .envvalidate import EnvValidator, EnvVarValidator, ToolValidator
from .containers import ContainerBuildStep
from .generation import Generation, GenerationChange
from .evolution import Evolution
from .policy import Policy, PolicySet, PolicyViolation
from .gates import PromotionGate, GateResult, AllChangesProvenGate, NoFailedEvolutionsGate, MinEvolutionsGate
from .templates import Template, TemplateRegistry, get_template_registry
from .dashboard import Dashboard, run_dashboard
from .audit import AuditTrail, export_audit_trail
from .rollback import RollbackManager
from .hotfix import HotfixWorkflow, HotfixGate, create_hotfix
from .compliance import ComplianceReport, generate_compliance_report
from .auth import Auth, FlyAuth
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
    ScytheValidator,
    FlyDeployStep
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
    "PolicyHook",
    "ChangeTypeHook",
    # Destinations
    "Destination",
    "CommandDestination",
    "NpmRegistryDestination",
    "PyPIDestination",
    "GitHubReleaseDestination",
    "ContainerRegistryDestination",
    "SlackDestination",
    "PrometheusDestination",
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
    # Validators
    "ScytheValidator",
    # Auth
    "Auth",
    "FlyAuth",
    # Deployment steps
    "FlyDeployStep",
    # Generations & Evolutions (v0.2.0, v0.3.0)
    "Generation",
    "GenerationChange",
    "Evolution",
    # Policies (v0.5.0)
    "Policy",
    "PolicySet",
    "PolicyViolation",
    # Promotion Gates (v0.4.0)
    "PromotionGate",
    "GateResult",
    "AllChangesProvenGate",
    "NoFailedEvolutionsGate",
    "MinEvolutionsGate",
    # Templates & Dashboard (v0.6.0)
    "Template",
    "TemplateRegistry",
    "get_template_registry",
    "Dashboard",
    "run_dashboard",
    # Audit, Rollback & Compliance (v1.0.0)
    "AuditTrail",
    "export_audit_trail",
    "RollbackManager",
    "HotfixWorkflow",
    "HotfixGate",
    "create_hotfix",
    "ComplianceReport",
    "generate_compliance_report",
]
