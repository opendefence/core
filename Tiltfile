# Hot-reload loop for core on the kind cluster from `task up`.
# Base publishes the local-registry-hosting ConfigMap, so Tilt pushes images
# to its localhost registry without further configuration.
allow_k8s_contexts('kind-opendefence-dev')

# Deploy what the Zarf package deploys, rendered with the local-dev values
values_file = 'values/local-dev.yaml'
for path in ['zarf.yaml', 'manifests', 'values']:
    watch_file(path)
objects = decode_yaml_stream(local(
    'zarf dev inspect manifests . --values %s --log-level warn --no-color' % values_file,
    quiet=True,
))

for obj in objects:
    if obj['kind'] != 'Deployment':
        continue
    container = obj['spec']['template']['spec']['containers'][0]
    if obj['metadata']['name'] == 'core-api':
        # uvicorn reloads source that Tilt syncs in, so the filesystem must be writable
        container['command'] = [
            'uvicorn', 'opendefence_core.api.app:app',
            '--host', '0.0.0.0', '--port', '8000',
            '--reload', '--reload-dir', '/app/src',
        ]
        container['securityContext']['readOnlyRootFilesystem'] = False
    elif obj['metadata']['name'] == 'opendefence-platform':
        # The operator can't reload in place; give it its own image so Tilt
        # rebuilds and restarts it on change instead of syncing files
        container['image'] = 'ghcr.io/opendefence/core-operator'
k8s_yaml(encode_yaml_stream(objects))

dev_build = dict(
    context='.',
    target='dev',
    only=['src', 'pyproject.toml', 'uv.lock', 'README.md'],
)
docker_build(
    'ghcr.io/opendefence/core',
    live_update=[
        fall_back_on(['pyproject.toml', 'uv.lock']),
        sync('src', '/app/src'),
    ],
    **dev_build
)
docker_build('ghcr.io/opendefence/core-operator', **dev_build)

k8s_resource('core-api', port_forwards='8000')
k8s_resource('opendefence-platform', labels=['operator'])
