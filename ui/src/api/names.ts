/**
 * Naming rules the platform applies to roles and groups alike. The API takes
 * both from models.v1alpha1.integration.ROLE_NAME_PATTERN.
 */
export const NAME_PATTERN = /^[a-z0-9]([-a-z0-9]*[a-z0-9])?$/;

/** Longest name a Kubernetes resource may carry. */
export const NAME_MAX = 63;
