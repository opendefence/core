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

# Tilt syncs source into the API container, so its filesystem must be writable
for obj in objects:
    if obj['kind'] == 'Deployment' and obj['metadata']['name'] == 'core-api':
        for container in obj['spec']['template']['spec']['containers']:
            container['securityContext']['readOnlyRootFilesystem'] = False
k8s_yaml(encode_yaml_stream(objects))

docker_build(
    'ghcr.io/opendefence/core',
    '.',
    target='dev',
    only=['src', 'pyproject.toml', 'uv.lock', 'README.md'],
    entrypoint=[
        'uvicorn', 'opendefence_core.api.app:app',
        '--host', '0.0.0.0', '--port', '8000',
        '--reload', '--reload-dir', '/app/src',
    ],
    live_update=[
        fall_back_on(['pyproject.toml', 'uv.lock']),
        sync('src', '/app/src'),
    ],
)

k8s_resource('core-api', port_forwards='8000')
