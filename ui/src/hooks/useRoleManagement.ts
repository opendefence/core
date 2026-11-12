import { useState } from "react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { granting, useGroups } from "@/api/groups";
import {
  isProtected,
  SUPERADMIN_ROLE,
  useCreateRole,
  useDeleteRole,
  useRoleMembers,
  useRoles,
  type Role,
} from "@/api/roles";
import {
  isLastAdmin,
  isSelf,
  useGiveUserRole,
  useTakeUserRole,
} from "@/api/users";
import { useRequireSuperadmin } from "@/hooks/auth/useRequireSuperadmin";

export function useRoleManagement() {
  const { t } = useTranslation();

  const {
    callsign,
    isLoading: userTypeLoading,
    allowed,
  } = useRequireSuperadmin({
    noCallsign: "manageRoles.messages.noCallsign",
    forbidden: "manageRoles.forbidden",
  });

  const [filterText, setFilterText] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data: roles, isLoading, refetch } = useRoles();
  const selectedRole = roles?.find((role) => role.id === selectedId);

  const { data: groups } = useGroups();
  const {
    data: holders,
    isLoading: isLoadingHolders,
    refetch: refetchHolders,
  } = useRoleMembers(selectedRole?.id);

  const failed = (key: string) => (error: Error) =>
    toast.error(t(key, { error: error.message }));

  const create = useCreateRole({
    onSuccess: (role) => {
      toast.success(
        t("manageRoles.messages.created", { role: role.displayName }),
      );
      setCreateOpen(false);
      refetch();
    },
    onError: failed("manageRoles.messages.createError"),
  });

  const remove = useDeleteRole({
    onSuccess: () => {
      toast.success(
        t("manageRoles.messages.deleted", { role: selectedRole?.displayName }),
      );
      setSelectedId(null);
      refetch();
    },
    onError: failed("manageRoles.messages.deleteError"),
  });

  const give = useGiveUserRole({
    onSuccess: () => {
      toast.success(t("manageRoles.messages.given"));
      setPickerOpen(false);
      refetchHolders();
    },
    onError: failed("manageRoles.messages.giveError"),
  });

  const take = useTakeUserRole({
    onSuccess: () => {
      toast.success(t("manageRoles.messages.taken"));
      refetchHolders();
    },
    onError: failed("manageRoles.messages.takeError"),
  });

  const matches = (role: Role) => {
    const text = filterText.toLowerCase();
    return (
      role.displayName.toLowerCase().includes(text) || role.name.includes(text)
    );
  };

  return {
    filterText,
    setFilterText,
    createOpen,
    setCreateOpen,
    pickerOpen,
    setPickerOpen,
    selectedRole,
    openRole: (id: string) => setSelectedId(id),
    closeRole: () => setSelectedId(null),

    holders: holders ?? [],
    isLoadingHolders,
    grantedBy: selectedRole ? granting(groups, selectedRole.id) : [],
    isChanging: give.isPending || take.isPending,

    giveRole: (userId: string) => {
      if (!selectedRole) return;
      give.mutate({ userId, roleId: selectedRole.id });
    },

    takeRole: (userId: string) => {
      const holder = holders?.find((user) => user.id === userId);
      if (!selectedRole || !holder) return;
      if (selectedRole.name === SUPERADMIN_ROLE) {
        if (isSelf(holder, callsign)) {
          toast.error(t("manageRoles.messages.cannotTakeOwn"));
          return;
        }
        // Only direct holders are known here, so a group grant is not counted.
        if (isLastAdmin(holders ?? [], holder)) {
          toast.error(t("manageRoles.messages.cannotTakeLast"));
          return;
        }
      }
      take.mutate({ userId, roleId: selectedRole.id });
    },

    roles:
      roles
        ?.filter(matches)
        .sort((a, b) => a.displayName.localeCompare(b.displayName)) ?? [],
    isLoading,
    userTypeLoading,
    allowed,

    isCreating: create.isPending,
    isDeleting: remove.isPending,

    createRole: (name: string, displayName: string) =>
      create.mutate({ name, displayName }),

    deleteRole: () => {
      if (!selectedRole || isProtected(selectedRole)) return;
      remove.mutate(selectedRole.id);
    },
  };
}
