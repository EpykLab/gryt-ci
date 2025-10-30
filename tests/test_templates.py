"""Tests for Templates (v0.6.0)"""
import pytest
from pathlib import Path
from gryt.templates import (
    Template,
    TemplateRegistry,
    get_template_registry,
    create_go_template,
    create_python_template,
    create_node_template,
    create_minimal_template
)


class TestTemplate:
    """Test Template class"""

    def test_create_template(self):
        """Test creating a template"""
        template = Template(
            name="test-template",
            display_name="Test Template",
            description="A test template",
            language="python"
        )

        assert template.name == "test-template"
        assert template.language == "python"

    def test_render_basic_structure(self, temp_dir):
        """Test rendering template creates basic structure"""
        template = Template(
            name="test",
            display_name="Test",
            description="Test",
            language="python",
            files={
                "README.md": "# {{project_name}}\n\nA test project",
                "src/main.py": "print('Hello from {{project_name}}')"
            }
        )

        project_path = temp_dir / "test-project"
        template.render(project_path, {"project_name": "TestProject"})

        # Check .gryt structure
        assert (project_path / ".gryt").exists()
        assert (project_path / ".gryt" / "generations").exists()
        assert (project_path / ".gryt" / "pipelines").exists()

        # Check files
        assert (project_path / "README.md").exists()
        assert (project_path / "src" / "main.py").exists()

        # Check variable substitution
        readme_content = (project_path / "README.md").read_text()
        assert "TestProject" in readme_content
        assert "{{project_name}}" not in readme_content

    def test_render_with_pipelines(self, temp_dir):
        """Test rendering template with pipeline templates"""
        template = Template(
            name="test",
            display_name="Test",
            description="Test",
            language="python",
            pipeline_templates=[
                {
                    "name": "test-pipeline",
                    "description": "Test pipeline",
                    "steps": [
                        {"name": "test", "type": "CommandStep"}
                    ]
                }
            ]
        )

        project_path = temp_dir / "test-project-2"
        template.render(project_path)

        pipeline_file = project_path / ".gryt" / "pipelines" / "test-pipeline.yaml"
        assert pipeline_file.exists()

    def test_render_with_generation_example(self, temp_dir):
        """Test rendering template with generation example"""
        template = Template(
            name="test",
            display_name="Test",
            description="Test",
            language="python",
            generation_example={
                "version": "v0.1.0",
                "description": "Initial release",
                "changes": [
                    {"type": "add", "id": "INIT-001", "title": "Initial"}
                ]
            }
        )

        project_path = temp_dir / "test-project-3"
        template.render(project_path)

        gen_file = project_path / ".gryt" / "generations" / "v0.1.0.yaml"
        assert gen_file.exists()


class TestTemplateRegistry:
    """Test TemplateRegistry class"""

    def test_register_template(self):
        """Test registering a template"""
        registry = TemplateRegistry()
        registry.templates.clear()  # Clear built-ins

        template = Template(
            name="custom",
            display_name="Custom",
            description="Custom template",
            language="rust"
        )

        registry.register(template)

        assert "custom" in registry.templates
        assert registry.get("custom") == template

    def test_list_templates(self):
        """Test listing templates"""
        registry = TemplateRegistry()
        registry.templates.clear()

        template1 = Template("t1", "T1", "Desc 1", "go")
        template2 = Template("t2", "T2", "Desc 2", "python")

        registry.register(template1)
        registry.register(template2)

        templates = registry.list()

        assert len(templates) == 2
        assert template1 in templates
        assert template2 in templates

    def test_builtin_templates_loaded(self):
        """Test built-in templates are loaded"""
        registry = TemplateRegistry()

        templates = registry.list()

        # Should have at least 4 built-in templates
        assert len(templates) >= 4

        # Check for expected templates
        template_names = [t.name for t in templates]
        assert "go-release" in template_names
        assert "python-ci" in template_names
        assert "node-ci" in template_names
        assert "minimal" in template_names


class TestBuiltInTemplates:
    """Test built-in template creation functions"""

    def test_create_go_template(self):
        """Test Go template creation"""
        template = create_go_template()

        assert template.name == "go-release"
        assert template.language == "go"
        assert "go.mod" in template.files
        assert "main.go" in template.files
        assert len(template.pipeline_templates) > 0

    def test_create_python_template(self):
        """Test Python template creation"""
        template = create_python_template()

        assert template.name == "python-ci"
        assert template.language == "python"
        assert "pyproject.toml" in template.files
        assert len(template.pipeline_templates) > 0

    def test_create_node_template(self):
        """Test Node template creation"""
        template = create_node_template()

        assert template.name == "node-ci"
        assert template.language == "javascript"
        assert "package.json" in template.files
        assert "index.js" in template.files

    def test_create_minimal_template(self):
        """Test minimal template creation"""
        template = create_minimal_template()

        assert template.name == "minimal"
        assert template.language == "generic"
        assert "README.md" in template.files

    def test_go_template_renders(self, temp_dir):
        """Test Go template renders successfully"""
        template = create_go_template()
        project_path = temp_dir / "go-project"

        template.render(project_path, {"project_name": "my-go-app"})

        assert (project_path / "go.mod").exists()
        assert (project_path / "main.go").exists()
        assert (project_path / ".gryt" / "pipelines" / "release.yaml").exists()

        # Check substitution
        go_mod = (project_path / "go.mod").read_text()
        assert "my-go-app" in go_mod


class TestGlobalRegistry:
    """Test global registry singleton"""

    def test_get_template_registry(self):
        """Test getting global registry"""
        registry1 = get_template_registry()
        registry2 = get_template_registry()

        # Should be same instance
        assert registry1 is registry2

    def test_global_registry_has_templates(self):
        """Test global registry is populated"""
        registry = get_template_registry()

        templates = registry.list()
        assert len(templates) >= 4
