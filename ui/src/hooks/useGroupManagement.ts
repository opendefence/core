import { useState } from "react";
import { ancestorsOf, toTree, useGroups, type Group } from "@/api/groups";
import { useRequireSuperadmin } from "@/hooks/auth/useRequireSuperadmin";

/** Roles an ancestor grants to every member of the selected group. */
export interface Inherited {
  from: Group;
  roles: Group["roles"];
}

export function useGroupManagement() {
  const { isLoading: userTypeLoading, allowed } = useRequireSuperadmin({
    noCallsign: "manageGroups.messages.noCallsign",
    forbidden: "manageGroups.forbidden",
  });

  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data: groups, isLoading } = useGroups();
  const selectedGroup = groups?.find((group) => group.id === selectedId);

  const ancestors =
    selectedGroup && groups ? ancestorsOf(selectedGroup, groups) : [];

  return {
    tree: toTree(groups),
    selectedGroup,
    parent: ancestors.at(0),
    inherited: ancestors
      .filter((group) => group.roles.length > 0)
      .map((group): Inherited => ({ from: group, roles: group.roles })),

    selectGroup: (id: string) => setSelectedId(id),
    isLoading,
    userTypeLoading,
    allowed,
  };
}
