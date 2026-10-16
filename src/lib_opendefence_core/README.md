# OpenDefence resource models

`lib-opendefence-core` provides the `platform.opendefence.fi/v1alpha1` resource models.

Install the package with `pip install lib-opendefence-core`.

```python
from lib_opendefence_core.models.v1alpha1 import Group, Integration, Invite, Role, User, UserBinding
```

The package uses Cloudcoil and Pydantic. Its release version matches the
`opendefence-core` application version. The Kubernetes API version stays `v1alpha1`.

Use `get_logger()` for typed `trace()` and `audit()` methods:

```python
from lib_opendefence_core.logging import get_logger

logger = get_logger(__name__)
logger.audit("User %s enrolled", "alice")
```

The helper registers both levels and returns the standard logger for that name.
Use `TRACE` and `AUDIT` from the same module when setting numeric log levels.
Configure handlers through the application's logging setup or `init_logging()`.
