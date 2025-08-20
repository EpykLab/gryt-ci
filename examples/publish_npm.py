from gryt import Pipeline, Runner, CommandStep, LocalRuntime
from gryt import NpmRegistryDestination

# Example: publish an npm package.
# Requirements:
# - package.json prepared with version and files.
# - NPM auth (NPM_TOKEN and .npmrc or CI environment setup).

runner = Runner([
    # Example build step; adjust for your project
    CommandStep('npm_build', {'cmd': ['bash', '-lc', 'npm ci && npm pack']})
])

npm_dest = NpmRegistryDestination('npm_publish', {
    'package_dir': '.',
    'registry': 'https://registry.npmjs.org',
    'tag': 'latest',
})

PIPELINE = Pipeline([runner], runtime=LocalRuntime(), destinations=[npm_dest])

if __name__ == '__main__':
    # npm publish uses package_dir; artifacts list is not required
    out = PIPELINE.execute(artifacts=[])
    print(out)
