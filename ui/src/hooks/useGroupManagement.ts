import { useState } from "react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import {
  ancestorsOf,
  descendantsOf,
  toTree,
  useCreateGroup,
  useDeleteGroup,
  useGroupMembers,
  useGroups,
  useUpdateGroup,
  type Group,
} from "@/api/groups";
import { useRequireSuperadmin } from "@/hooks/auth/useRequireSuperadmin";

/** Roles an ancestor grants to every member of the selected group. */
export interface Inherited {
  from: Group;
  roles: Group["roles"];
}

export function useGroupManagement() {
  const { t } = useTranslation();

  const { isLoading: userTypeLoading, allowed } = useRequireSuperadmin({
    noCallsign: "manageGroups.messages.noCallsign",
    forbidden: "manageGroups.forbidden",
  });

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [renameOpen, setRenameOpen] = useState(false);
  const [moveOpen, setMoveOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const { data: groups, isLoading, refetch } = useGroups();
  const selectedGroup = groups?.find((group) => group.id === selectedId);
  const { data: members } = useGroupMembers(selectedGroup?.id);

  const ancestors =
    selectedGroup && groups ? ancestorsOf(selectedGroup, groups) : [];
  const descendants =
    selectedGroup && groups ? descendantsOf(selectedGroup, groups) : [];

  const failed = (key: string) => (error: Error) =>
    toast.error(t(key, { error: error.message }));

  const create = useCreateGroup({
    onSuccess: (group) => {
      toast.success(
        t("manageGroups.messages.created", { group: group.displayName }),
      );
      setCreateOpen(false);
      setSelectedId(group.id);
      refetch();
    },
    onError: failed("manageGroups.messages.createError"),
  });

  const update = useUpdateGroup({
    onSuccess: () => {
      toast.success(t("manageGroups.messages.changed"));
      setRenameOpen(false);
      setMoveOpen(false);
      refetch();
    },
    onError: failed("manageGroups.messages.changeError"),
  });

  const remove = useDeleteGroup({
    onSuccess: () => {
      toast.success(t("manageGroups.messages.deleted"));
      setDeleteOpen(false);
      setSelectedId(null);
      refetch();
    },
    onError: failed("manageGroups.messages.deleteError"),
  });

  /**
   * What still refers to the group. The operator refuses only the first of
   * these; the others would leave references the operator cannot resolve.
   */
  const blockers = (group: Group) => {
    const found: string[] = [];
    if (descendants.length > 0) found.push(t("manageGroups.delete.children"));
    if ((members?.length ?? 0) > 0)
      found.push(t("manageGroups.delete.members"));
    if (group.managers.length > 0)
      found.push(t("manageGroups.delete.managers"));
    if (group.roles.length > 0) found.push(t("manageGroups.delete.roles"));
    return found;
  };

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

    createOpen,
    setCreateOpen,
    renameOpen,
    setRenameOpen,
    moveOpen,
    setMoveOpen,
    deleteOpen,
    setDeleteOpen,

    isCreating: create.isPending,
    isChanging: update.isPending,
    isDeleting: remove.isPending,

    /** The group itself and everything below it cannot become its parent. */
    moveExclude: selectedGroup
      ? [selectedGroup.id, ...descendants.map((group) => group.id)]
      : [],

    createGroup: (name: string, displayName: string, parentId: string | null) =>
      create.mutate({ name, displayName, parentId }),

    renameGroup: (displayName: string) => {
      if (!selectedGroup) return;
      update.mutate({ groupId: selectedGroup.id, displayName });
    },

    moveGroup: (parentId: string | null) => {
      if (!selectedGroup) return;
      update.mutate({ groupId: selectedGroup.id, parentId });
    },

    askDelete: () => {
      if (!selectedGroup) return;
      const found = blockers(selectedGroup);
      if (found.length > 0) {
        toast.error(
          t("manageGroups.delete.blocked", { reasons: found.join(", ") }),
        );
        return;
      }
      setDeleteOpen(true);
    },

    deleteGroup: () => {
      if (!selectedGroup) return;
      remove.mutate(selectedGroup.id);
    },
  };
}
