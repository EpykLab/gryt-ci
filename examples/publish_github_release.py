from pathlib import Path
from gryt import Pipeline, Runner, CommandStep, LocalRuntime
from gryt import GitHubReleaseDestination

# Example: publish files to a GitHub Release as assets.
# Requirements:
# - Environment variable GITHUB_TOKEN with repo scope.
# - The repository owner/repo must match the repo where the token has access.

# Build or prepare artifacts
runner = Runner([
    CommandStep('build', {'cmd': ['bash', '-lc', 'mkdir -p dist && echo ok > dist/demo.txt']}),
])

release_dest = GitHubReleaseDestination(
    id='gh_release',
    config={
        'owner': 'your-org',
        'repo': 'your-repo',
        'tag': 'v0.1.0',
        'title': 'v0.1.0',
        'body': 'Automated release from gryt example',
        'overwrite_assets': True,
    },
)

PIPELINE = Pipeline([runner], runtime=LocalRuntime(), destinations=[release_dest])

# The CLI will call PIPELINE.execute(); running directly for clarity:
if __name__ == '__main__':
    artifacts = [Path('dist/demo.txt')]
    out = PIPELINE.execute(artifacts=artifacts)
    print(out)
