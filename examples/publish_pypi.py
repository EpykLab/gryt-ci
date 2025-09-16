from gryt import Pipeline, Runner, CommandStep, LocalRuntime
from gryt import PyPIDestination

# Example: publish Python distributions to PyPI (or TestPyPI) via twine.
# Requirements:
# - Build distributions into ./dist first (e.g., `python -m build`).
# - twine available (pip install twine).
# - Credentials via TWINE_API_TOKEN or TWINE_USERNAME/TWINE_PASSWORD env.

runner = Runner([
    # For demonstration; replace it with your actual build steps
    CommandStep('build_py', {'cmd': ['bash', '-lc', 'python -m pip install build && python -m build']})
])

pypi_dest = PyPIDestination('pypi', {
    'dist_glob': 'dist/*',
    # 'repository_url': 'https://test.pypi.org/legacy/',  # uncomment for TestPyPI
    'extra_args': ['--skip-existing'],
})

PIPELINE = Pipeline([runner], runtime=LocalRuntime(), destinations=[pypi_dest])

if __name__ == '__main__':
    # No need to pass artifacts for PyPI; destination will pick up dist_glob
    out = PIPELINE.execute(artifacts=[])
    print(out)
