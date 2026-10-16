# OpenDefence resource models

`lib-opendefence-core` provides the `platform.opendefence.fi/v1alpha1` resource models.

Install the package with `pip install lib-opendefence-core`.

```python
from lib_opendefence_core.models.v1alpha1 import Group, Integration, Invite, Role, User, UserBinding
```

The package uses Cloudcoil and Pydantic. Its release version matches the
`opendefence-core` application version. The Kubernetes API version stays `v1alpha1`.
