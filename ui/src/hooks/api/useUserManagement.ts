import { useState } from "react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { SUPERADMIN_ROLE, useRoleId } from "@/api/roles";
import {
  isAdmin,
  isLastAdmin,
  isSelf,
  useGiveUserRole,
  useRevokeUser,
  useTakeUserRole,
  useUsers,
  type User,
} from "@/api/users";

interface UseUserManagementOptions {
  currentCallsign: string | null;
}

export function useUserManagement({
  currentCallsign,
}: UseUserManagementOptions) {
  const { t } = useTranslation();
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [userDialogOpen, setUserDialogOpen] = useState(false);
  const [selectedUsers, setSelectedUsers] = useState<string[]>([]);
  const [bulkMode, setBulkMode] = useState(false);
  const [bulkAction, setBulkAction] = useState<
    "promote" | "demote" | "remove" | null
  >(null);

  // Confirmation states
  const [promoteConfirmOpen, setPromoteConfirmOpen] = useState(false);
  const [demoteConfirmOpen, setDemoteConfirmOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [bulkConfirmOpen, setBulkConfirmOpen] = useState(false);

  const { data: users, isLoading, refetch } = useUsers("active", 10000);

  // Promotion and demotion give and take one role: superadmin.
  const adminRole = useRoleId(SUPERADMIN_ROLE);

  const promoteUserMutation = useGiveUserRole({
    onSuccess: () => {
      toast.success(
        t("manageUsers.messages.promoted", {
          callsign: selectedUser?.callsign,
        }),
      );
      setPromoteConfirmOpen(false);
      setUserDialogOpen(false);
      refetch();
    },
    onError: (error) => {
      toast.error(
        t("manageUsers.messages.promoteFailed", { error: error.message }),
      );
    },
  });

  const demoteUserMutation = useTakeUserRole({
    onSuccess: () => {
      toast.success(
        t("manageUsers.messages.demoted", { callsign: selectedUser?.callsign }),
      );
      setDemoteConfirmOpen(false);
      setUserDialogOpen(false);
      refetch();
    },
    onError: (error) => {
      toast.error(
        t("manageUsers.messages.demoteFailed", { error: error.message }),
      );
    },
  });

  const deleteUserMutation = useRevokeUser({
    onSuccess: () => {
      toast.error(
        t("manageUsers.messages.removed", { callsign: selectedUser?.callsign }),
      );
      setDeleteConfirmOpen(false);
      setUserDialogOpen(false);
      refetch();
    },
    onError: (error) => {
      toast.error(
        t("manageUsers.messages.removeFailed", { error: error.message }),
      );
    },
  });

  const administrators = users?.filter(isAdmin) || [];
  const fighters = users?.filter((user) => !isAdmin(user)) || [];

  const isCurrentUser = (user: User) => isSelf(user, currentCallsign);

  const hasAdminSelected = administrators.some((admin) =>
    selectedUsers.includes(admin.id),
  );

  const toggleUserSelection = (user: User) => {
    if (isCurrentUser(user)) {
      toast.error(t("manageUsers.messages.cannotSelectSelf"));
      return;
    }
    setSelectedUsers((prev) =>
      prev.includes(user.id)
        ? prev.filter((id) => id !== user.id)
        : [...prev, user.id],
    );
  };

  const handlePromoteClick = () => {
    if (!selectedUser) return;
    setPromoteConfirmOpen(true);
  };

  const handlePromoteConfirm = () => {
    if (!selectedUser) return;
    promoteUserMutation.mutate({ userId: selectedUser.id, roleId: adminRole });
  };

  const handleDemoteClick = () => {
    if (!selectedUser) return;
    if (isCurrentUser(selectedUser)) {
      toast.error(t("manageUsers.messages.cannotDemoteOwn"));
      return;
    }
    setDemoteConfirmOpen(true);
  };

  const handleDemoteConfirm = () => {
    if (!selectedUser) return;
    demoteUserMutation.mutate({ userId: selectedUser.id, roleId: adminRole });
  };

  const handleRemoveClick = () => {
    if (!selectedUser) return;

    if (isCurrentUser(selectedUser)) {
      toast.error(t("manageUsers.messages.cannotDeleteOwn"));
      return;
    }

    if (isLastAdmin(administrators, selectedUser)) {
      toast.error(t("manageUsers.messages.cannotDeleteLastAdmin"));
      return;
    }

    setDeleteConfirmOpen(true);
  };

  const handleRemoveConfirm = () => {
    if (!selectedUser) return;
    deleteUserMutation.mutate(selectedUser.id);
  };

  const handleBulkPromote = () => {
    setBulkAction("promote");
    setBulkConfirmOpen(true);
  };

  const handleBulkDemote = () => {
    setBulkAction("demote");
    setBulkConfirmOpen(true);
  };

  const handleBulkRemove = () => {
    setBulkAction("remove");
    setBulkConfirmOpen(true);
  };

  const confirmBulkAction = async () => {
    for (const userId of selectedUsers) {
      if (bulkAction === "promote") {
        await promoteUserMutation.mutateAsync({ userId, roleId: adminRole });
      } else if (bulkAction === "demote") {
        await demoteUserMutation.mutateAsync({ userId, roleId: adminRole });
      } else if (bulkAction === "remove") {
        await deleteUserMutation.mutateAsync(userId);
      }
    }
    toast.success(
      t("manageUsers.messages.bulkSuccess", { count: selectedUsers.length }),
    );
    setSelectedUsers([]);
    setBulkMode(false);
    setBulkConfirmOpen(false);
    refetch();
  };

  const openUser = (user: User) => {
    setSelectedUser(user);
    setUserDialogOpen(true);
  };

  const toggleBulkMode = () => {
    setBulkMode(!bulkMode);
    setSelectedUsers([]);
  };

  return {
    // Data
    users,
    administrators,
    fighters,
    isLoading,

    // Selection state
    selectedUser,
    openUser,
    userDialogOpen,
    setUserDialogOpen,
    selectedUsers,
    bulkMode,
    bulkAction,
    hasAdminSelected,

    // Confirmation states
    promoteConfirmOpen,
    setPromoteConfirmOpen,
    demoteConfirmOpen,
    setDemoteConfirmOpen,
    deleteConfirmOpen,
    setDeleteConfirmOpen,
    bulkConfirmOpen,
    setBulkConfirmOpen,

    // Mutations
    promoteUserMutation,
    demoteUserMutation,
    deleteUserMutation,

    // Helpers
    isAdmin,
    isCurrentUser,

    // Actions
    toggleUserSelection,
    toggleBulkMode,
    handlePromoteClick,
    handlePromoteConfirm,
    handleDemoteClick,
    handleDemoteConfirm,
    handleRemoveClick,
    handleRemoveConfirm,
    handleBulkPromote,
    handleBulkDemote,
    handleBulkRemove,
    confirmBulkAction,
  };
}
