"""
Template system for project initialization (v0.6.0)

Provides project templates for common language stacks and CI patterns.
"""
from __future__ import annotations

import json
import shutil
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class Template:
    """A project template with predefined structure and configuration.

    Attributes:
        name: Template identifier (e.g., "go-release", "python-ci")
        display_name: Human-readable name
        description: Template description
        language: Primary language (go, python, node, rust, etc.)
        files: Dict of file paths to content (supports Jinja2-like templating)
        gryt_config: Configuration for .gryt directory
        pipeline_templates: Pre-configured pipelines
        generation_example: Example generation file
    """
    name: str
    display_name: str
    description: str
    language: str
    files: Dict[str, str] = field(default_factory=dict)
    gryt_config: Dict[str, Any] = field(default_factory=dict)
    pipeline_templates: List[Dict[str, Any]] = field(default_factory=list)
    generation_example: Optional[Dict[str, Any]] = None

    def render(self, project_path: Path, context: Optional[Dict[str, Any]] = None) -> None:
        """Render template to filesystem.

        Args:
            project_path: Target directory for project
            context: Template variables (project_name, author, etc.)
        """
        context = context or {}
        context.setdefault("project_name", project_path.name)

        # Create .gryt directory structure
        gryt_dir = project_path / ".gryt"
        gryt_dir.mkdir(parents=True, exist_ok=True)
        (gryt_dir / "generations").mkdir(exist_ok=True)
        (gryt_dir / "pipelines").mkdir(exist_ok=True)

        # Write gryt config
        if self.gryt_config:
            config_path = gryt_dir / "config.yaml"
            with open(config_path, "w") as f:
                yaml.dump(self.gryt_config, f)

        # Write pipeline templates
        for pipeline in self.pipeline_templates:
            pipeline_name = pipeline.get("name", "default")
            pipeline_path = gryt_dir / "pipelines" / f"{pipeline_name}.yaml"
            with open(pipeline_path, "w") as f:
                yaml.dump(pipeline, f)

        # Write example generation
        if self.generation_example:
            gen_version = self.generation_example.get("version", "v0.1.0")
            gen_path = gryt_dir / "generations" / f"{gen_version}.yaml"
            with open(gen_path, "w") as f:
                yaml.dump(self.generation_example, f)

        # Write project files
        for file_path, content in self.files.items():
            target = project_path / file_path
            target.parent.mkdir(parents=True, exist_ok=True)

            # Simple template variable substitution
            rendered_content = content
            for key, value in context.items():
                rendered_content = rendered_content.replace(f"{{{{{key}}}}}", str(value))

            with open(target, "w") as f:
                f.write(rendered_content)


class TemplateRegistry:
    """Registry of available project templates."""

    def __init__(self):
        self.templates: Dict[str, Template] = {}
        self._load_builtin_templates()

    def register(self, template: Template) -> None:
        """Register a template"""
        self.templates[template.name] = template

    def get(self, name: str) -> Optional[Template]:
        """Get template by name"""
        return self.templates.get(name)

    def list(self) -> List[Template]:
        """List all available templates"""
        return list(self.templates.values())

    def _load_builtin_templates(self) -> None:
        """Load built-in templates"""
        # Go template
        self.register(create_go_template())

        # Python template
        self.register(create_python_template())

        # Node template
        self.register(create_node_template())

        # Minimal template
        self.register(create_minimal_template())


def create_go_template() -> Template:
    """Create Go project template with release pipeline"""
    return Template(
        name="go-release",
        display_name="Go Release Pipeline",
        description="Go project with build, test, and release pipeline",
        language="go",
        files={
            "README.md": """# {{project_name}}

Go project with gryt-ci release pipeline.

## Getting Started

```bash
# Initialize gryt
gryt init

# Create a new generation
gryt generation new v0.1.0

# Start an evolution
gryt evolution start v0.1.0 --change FEAT-001

# Run the pipeline
gryt run release

# Promote when ready
gryt generation promote v0.1.0
```
""",
            "go.mod": """module {{project_name}}

go 1.21
""",
            "main.go": """package main

import "fmt"

func main() {
    fmt.Println("Hello from {{project_name}}")
}
""",
            ".gitignore": """# Binaries
bin/
*.exe
*.dll
*.so
*.dylib

# Test artifacts
*.test
*.out

# Gryt
.gryt/gryt.db
.gryt/*.log
""",
        },
        gryt_config={
            "execution_mode": "local",
            "default_pipeline": "release",
        },
        pipeline_templates=[
            {
                "name": "release",
                "description": "Build, test, and release Go binary",
                "steps": [
                    {
                        "name": "go_mod_download",
                        "type": "GoModDownloadStep",
                    },
                    {
                        "name": "go_test",
                        "type": "GoTestStep",
                        "config": {"verbose": True},
                    },
                    {
                        "name": "go_build",
                        "type": "GoBuildStep",
                        "config": {"output": "bin/{{project_name}}"},
                    },
                ],
            }
        ],
        generation_example={
            "version": "v0.1.0",
            "description": "Initial release",
            "changes": [
                {
                    "type": "add",
                    "id": "FEAT-001",
                    "title": "Initial implementation",
                }
            ],
            "pipeline_template": "release",
        },
    )


def create_python_template() -> Template:
    """Create Python project template with testing pipeline"""
    return Template(
        name="python-ci",
        display_name="Python CI Pipeline",
        description="Python project with pytest and packaging",
        language="python",
        files={
            "README.md": """# {{project_name}}

Python project with gryt-ci testing and release pipeline.

## Getting Started

```bash
# Install dependencies
pip install -e .

# Initialize gryt
gryt init

# Create a new generation
gryt generation new v0.1.0

# Run the pipeline
gryt run test
```
""",
            "pyproject.toml": """[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "{{project_name}}"
version = "0.1.0"
description = "A Python project"
requires-python = ">=3.9"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=7.0", "gryt-ci"]
""",
            "{{project_name}}/__init__.py": """\"\"\"{{project_name}} - A Python project\"\"\"\n\n__version__ = "0.1.0"\n""",
            "tests/test_basic.py": """import pytest

def test_example():
    assert True
""",
            ".gitignore": """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
dist/
*.egg-info/

# Testing
.pytest_cache/
.coverage
htmlcov/

# Gryt
.gryt/gryt.db
.gryt/*.log
""",
        },
        gryt_config={
            "execution_mode": "local",
            "default_pipeline": "test",
        },
        pipeline_templates=[
            {
                "name": "test",
                "description": "Run pytest tests",
                "steps": [
                    {
                        "name": "pip_install",
                        "type": "PipInstallStep",
                        "config": {"requirements": ".[dev]"},
                    },
                    {
                        "name": "pytest",
                        "type": "PytestStep",
                        "config": {"verbose": True, "coverage": True},
                    },
                ],
            }
        ],
        generation_example={
            "version": "v0.1.0",
            "description": "Initial release",
            "changes": [
                {
                    "type": "add",
                    "id": "FEAT-001",
                    "title": "Initial implementation",
                }
            ],
            "pipeline_template": "test",
        },
    )


def create_node_template() -> Template:
    """Create Node.js project template"""
    return Template(
        name="node-ci",
        display_name="Node.js CI Pipeline",
        description="Node.js project with npm build and test",
        language="javascript",
        files={
            "README.md": """# {{project_name}}

Node.js project with gryt-ci build and test pipeline.

## Getting Started

```bash
# Install dependencies
npm install

# Initialize gryt
gryt init

# Run the pipeline
gryt run build
```
""",
            "package.json": """{
  "name": "{{project_name}}",
  "version": "0.1.0",
  "description": "A Node.js project",
  "main": "index.js",
  "scripts": {
    "test": "echo \\"No tests yet\\" && exit 0",
    "build": "echo \\"Build complete\\""
  },
  "devDependencies": {}
}
""",
            "index.js": """console.log('Hello from {{project_name}}');
""",
            ".gitignore": """# Dependencies
node_modules/
package-lock.json
yarn.lock

# Build
dist/
build/

# Gryt
.gryt/gryt.db
.gryt/*.log
""",
        },
        gryt_config={
            "execution_mode": "local",
            "default_pipeline": "build",
        },
        pipeline_templates=[
            {
                "name": "build",
                "description": "Install dependencies and build",
                "steps": [
                    {
                        "name": "npm_install",
                        "type": "NpmInstallStep",
                    },
                    {
                        "name": "npm_test",
                        "type": "CommandStep",
                        "config": {"cmd": "npm test"},
                    },
                    {
                        "name": "npm_build",
                        "type": "NpmBuildStep",
                    },
                ],
            }
        ],
        generation_example={
            "version": "v0.1.0",
            "description": "Initial release",
            "changes": [
                {
                    "type": "add",
                    "id": "FEAT-001",
                    "title": "Initial implementation",
                }
            ],
            "pipeline_template": "build",
        },
    )


def create_minimal_template() -> Template:
    """Create minimal template with basic structure only"""
    return Template(
        name="minimal",
        display_name="Minimal Setup",
        description="Minimal gryt-ci setup with basic pipeline",
        language="generic",
        files={
            "README.md": """# {{project_name}}

Minimal gryt-ci setup.

## Getting Started

```bash
# Initialize gryt
gryt init

# Create your first generation
gryt generation new v0.1.0
```
""",
            ".gitignore": """.gryt/gryt.db
.gryt/*.log
""",
        },
        gryt_config={
            "execution_mode": "local",
        },
        pipeline_templates=[
            {
                "name": "default",
                "description": "Default pipeline",
                "steps": [
                    {
                        "name": "hello",
                        "type": "CommandStep",
                        "config": {"cmd": "echo 'Hello from gryt-ci'"},
                    },
                ],
            }
        ],
        generation_example={
            "version": "v0.1.0",
            "description": "Initial release",
            "changes": [
                {
                    "type": "add",
                    "id": "INIT-001",
                    "title": "Project initialization",
                }
            ],
            "pipeline_template": "default",
        },
    )


# Global registry instance
_registry = TemplateRegistry()


def get_template_registry() -> TemplateRegistry:
    """Get the global template registry"""
    return _registry
