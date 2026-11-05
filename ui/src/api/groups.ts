import { useMutation, useQuery } from "@tanstack/react-query";
import { api, reason, type Options } from "./client";
import type { components } from "./schema";

export type Group = components["schemas"]["GroupResponse"];

/** A role as a group names it. */
export type GrantedRole = Group["roles"][number];

/** A user as the group endpoints name them. */
export type Member = components["schemas"]["UserSummary"];

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

/** Users that name the group directly. Members of groups below are not listed. */
export function useGroupMembers(groupId: string | undefined) {
  return useQuery({
    queryKey: ["groups", groupId, "members"],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v3/groups/{group_id}/members",
        { params: { path: { group_id: groupId ?? "" } } },
      );
      if (error) throw new Error("Failed to load the members of the group");
      return data;
    },
    enabled: groupId !== undefined,
  });
}

interface NewGroup {
  name: string;
  displayName: string;
  parentId: string | null;
}

/** Create a group. The name is its permanent slug; only the display name changes. */
export function useCreateGroup(options?: Options<Group, NewGroup>) {
  return useMutation({
    mutationFn: async (group: NewGroup) => {
      const { data, error } = await api.POST("/api/v3/groups", { body: group });
      if (error) throw new Error(reason(error, "Failed to create the group"));
      return data;
    },
    ...options,
  });
}

interface GroupChange {
  groupId: string;
  displayName?: string;
  /** null makes the group a root. Left out, the group stays where it is. */
  parentId?: string | null;
}

/** Rename the group, or move it under another parent. */
export function useUpdateGroup(options?: Options<Group, GroupChange>) {
  return useMutation({
    mutationFn: async ({ groupId, ...change }: GroupChange) => {
      const { data, error } = await api.PATCH("/api/v3/groups/{group_id}", {
        params: { path: { group_id: groupId } },
        body: change,
      });
      if (error) throw new Error(reason(error, "Failed to change the group"));
      return data;
    },
    ...options,
  });
}

/** Delete a group. The operator refuses while the group has children. */
export function useDeleteGroup(options?: Options<void, string>) {
  return useMutation({
    mutationFn: async (groupId: string) => {
      const { error } = await api.DELETE("/api/v3/groups/{group_id}", {
        params: { path: { group_id: groupId } },
      });
      if (error) throw new Error(reason(error, "Failed to delete the group"));
    },
    ...options,
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

/** Every group below this one, at any depth. */
export function descendantsOf(group: Group, groups: Group[]): Group[] {
  const found: Group[] = [];
  const queue = [group];
  while (queue.length > 0) {
    const current = queue.pop();
    for (const candidate of groups) {
      if (candidate.parentId !== current?.id) continue;
      if (found.includes(candidate)) continue;
      found.push(candidate);
      queue.push(candidate);
    }
  }
  return found;
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
