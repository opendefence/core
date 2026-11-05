import { useState } from "react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import {
  isProtected,
  useCreateRole,
  useDeleteRole,
  useRoles,
  type Role,
} from "@/api/roles";
import { useRequireSuperadmin } from "@/hooks/auth/useRequireSuperadmin";

export function useRoleManagement() {
  const { t } = useTranslation();

  const { isLoading: userTypeLoading, allowed } = useRequireSuperadmin({
    noCallsign: "manageRoles.messages.noCallsign",
    forbidden: "manageRoles.forbidden",
  });

  const [filterText, setFilterText] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data: roles, isLoading, refetch } = useRoles();
  const selectedRole = roles?.find((role) => role.id === selectedId);

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
    selectedRole,
    openRole: (id: string) => setSelectedId(id),
    closeRole: () => setSelectedId(null),

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
