# Hot-reload loop for core on the kind cluster from `task env`; `task dev`
# passes the cluster's kube-context in KUBE_CONTEXT.
# Base publishes the local-registry-hosting ConfigMap, so Tilt pushes images
# to its localhost registry without further configuration.
allow_k8s_contexts(os.getenv('KUBE_CONTEXT', 'kind-opendefence-dev'))

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
        container['args'] = ['api', 'run', '--reload', '--reload-dir', '/app/src']
        container['securityContext']['readOnlyRootFilesystem'] = False
    elif obj['metadata']['name'] == 'core-operator':
        # The operator can't reload in place; give it its own image so Tilt
        # rebuilds and restarts it on change instead of syncing files
        container['image'] = 'ghcr.io/opendefence/core-operator'
    elif obj['metadata']['name'] == 'core-ui':
        # Vite serves and hot-reloads the synced source instead of nginx, as
        # the node user, and writes its cache and the generated route tree
        container['image'] = 'ghcr.io/opendefence/core-ui-dev'
        container['securityContext']['readOnlyRootFilesystem'] = False
        # Vite needs far more memory than the nginx image the limits are for
        container['resources'] = {
            'requests': {'cpu': '100m', 'memory': '256Mi'},
            'limits': {'memory': '2Gi'},
        }
        pod = obj['spec']['template']['spec']['securityContext']
        pod['runAsUser'] = 1000
        pod['runAsGroup'] = 1000
k8s_yaml(encode_yaml_stream(objects))

dev_build = dict(
    context='.',
    target='dev',
    only=['src', 'pyproject.toml', 'uv.lock', 'README.md', 'LICENSE.txt'],
)
docker_build(
    'ghcr.io/opendefence/core',
    live_update=[
        fall_back_on([
            'pyproject.toml', 'uv.lock', 'README.md',
            'src/lib_opendefence_core/pyproject.toml',
            'src/lib_opendefence_core/README.md',
            'src/lib_opendefence_core/LICENSE.txt',
        ]),
        sync('src', '/app/src'),
    ],
    **dev_build
)
docker_build('ghcr.io/opendefence/core-operator', **dev_build)

docker_build(
    'ghcr.io/opendefence/core-ui-dev',
    context='ui',
    target='dev',
    live_update=[
        fall_back_on(['ui/package.json', 'ui/pnpm-lock.yaml', 'ui/pnpm-workspace.yaml']),
        sync('ui/src', '/app/src'),
        sync('ui/public', '/app/public'),
        sync('ui/index.html', '/app/index.html'),
        sync('ui/vite.config.ts', '/app/vite.config.ts'),
    ],
)

k8s_resource('core-api', port_forwards='8000')
k8s_resource('core-operator', labels=['operator'])
k8s_resource('core-ui', labels=['ui'])
