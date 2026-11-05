import { useQuery } from "@tanstack/react-query";
import { api } from "./client";
import type { components } from "./schema";

export type Group = components["schemas"]["GroupResponse"];

/** A role as a group names it. */
export type GrantedRole = Group["roles"][number];

/** A group with the groups it contains. */
export interface GroupNode {
  group: Group;
  children: GroupNode[];
}

/** Every group on the platform. The hierarchy follows parentId. */
export function useGroups() {
  return useQuery({
    queryKey: ["groups"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v3/groups");
      if (error) throw new Error("Failed to load the groups");
      return data;
    },
  });
}

/** Groups that grant the role to their effective members. */
export function granting(groups: Group[] | undefined, roleId: string): Group[] {
  return (
    groups?.filter((group) => group.roles.some((r) => r.id === roleId)) ?? []
  );
}

const byDisplayName = (a: GroupNode, b: GroupNode) =>
  a.group.displayName.localeCompare(b.group.displayName);

/** The hierarchy as a forest, siblings in display-name order. */
export function toTree(groups: Group[] | undefined): GroupNode[] {
  const nodes = new Map<string, GroupNode>(
    groups?.map((group) => [group.id, { group, children: [] }]),
  );
  const roots: GroupNode[] = [];
  for (const node of nodes.values()) {
    const parent = node.group.parentId
      ? nodes.get(node.group.parentId)
      : undefined;
    // A group whose parent the caller cannot see is shown as a root.
    if (parent) parent.children.push(node);
    else roots.push(node);
  }
  for (const node of nodes.values()) node.children.sort(byDisplayName);
  return roots.sort(byDisplayName);
}

/** Every ancestor of the group, nearest parent first. */
export function ancestorsOf(group: Group, groups: Group[]): Group[] {
  const found: Group[] = [];
  let parentId = group.parentId;
  while (parentId) {
    const parent = groups.find((candidate) => candidate.id === parentId);
    // The operator rejects cycles, but never trust one into an endless loop.
    if (!parent || found.includes(parent)) break;
    found.push(parent);
    parentId = parent.parentId;
  }
  return found;
}
