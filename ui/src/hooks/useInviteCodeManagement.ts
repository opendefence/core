import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import {
  isActive,
  UNLIMITED,
  useCreateInvite,
  useDeleteInvite,
  useInvites,
  useSetInviteActive,
  type Invite,
} from "@/api/invites";
import { useRequireSuperadmin } from "@/hooks/auth/useRequireSuperadmin";
import { useWalkthrough } from "@/hooks/useWalkthrough";

const POLL_MS = 10000;

export function useInviteCodeManagement() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const {
    callsign,
    isLoading: userTypeLoading,
    allowed,
  } = useRequireSuperadmin({
    noCallsign: "addUsers.messages.noCallsignError",
    forbidden: "addUsers.messages.forbiddenError",
  });

  const [walkthroughOpen, setWalkthroughOpen] = useWalkthrough(
    `add-users-walkthrough-${callsign}`,
    !userTypeLoading,
  );
  const [filterText, setFilterText] = useState("");
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [manageDialogOpen, setManageDialogOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [bulkMode, setBulkMode] = useState(false);

  const { data: invites, isLoading, refetch } = useInvites(POLL_MS);
  const byId = (id: string | null) => invites?.find((i) => i.id === id);

  const failed = (key: string) => (error: Error) =>
    toast.error(t(key, { error: error.message }));

  const closeManageDialog = () => {
    setManageDialogOpen(false);
    setSelectedId(null);
    refetch();
  };

  const create = useCreateInvite({
    onSuccess: (invite) => {
      toast.success(t("addUsers.messages.codeCreated"));
      setCreateModalOpen(false);
      navigate({ to: "/invite-code/$code", params: { code: invite.code } });
    },
    onError: failed("addUsers.messages.createError"),
  });

  const remove = useDeleteInvite({
    onError: failed("addUsers.messages.deleteError"),
  });

  const setActive = useSetInviteActive({
    onError: (error, { active }) =>
      failed(
        active
          ? "addUsers.messages.activateError"
          : "addUsers.messages.deactivateError",
      )(error),
  });

  /** Run an action over every selected invite, then leave bulk mode. */
  const bulk = async (
    act: (invite: Invite) => Promise<unknown>,
    message: string,
  ) => {
    const chosen = invites?.filter((i) => selectedIds.includes(i.id)) ?? [];
    for (const invite of chosen) await act(invite);
    toast.success(t(message, { count: chosen.length }));
    setSelectedIds([]);
    setBulkMode(false);
    refetch();
  };

  return {
    filterText,
    setFilterText,
    createModalOpen,
    setCreateModalOpen,
    manageDialogOpen,
    closeManageDialog,
    selectedInvite: byId(selectedId),
    selectedIds,
    bulkMode,
    walkthroughOpen,
    setWalkthroughOpen,

    filteredInvites:
      invites?.filter((invite) =>
        invite.code.toLowerCase().includes(filterText.toLowerCase()),
      ) ?? [],
    isLoading,
    userTypeLoading,
    allowed,

    isCreating: create.isPending,
    isDeleting: remove.isPending,
    isTogglingStatus: setActive.isPending,

    handleCreateInvite: (roleIds: string[], groupIds: string[]) =>
      create.mutate({ useCount: UNLIMITED, roleIds, groupIds }),

    handleDeleteCode: async () => {
      const invite = byId(selectedId);
      if (!invite) return;
      await remove.mutateAsync(invite.id);
      toast.success(t("addUsers.messages.codeDeleted"));
      closeManageDialog();
    },

    handleToggleStatus: async () => {
      const invite = byId(selectedId);
      if (!invite) return;
      const active = !isActive(invite);
      await setActive.mutateAsync({ invite, active });
      toast.success(
        t(
          active
            ? "addUsers.messages.codeActivated"
            : "addUsers.messages.codeDeactivated",
        ),
      );
      closeManageDialog();
    },

    handleCodeClick: (code: string) =>
      navigate({ to: "/invite-code/$code", params: { code } }),

    handleManageClick: (id: string) => {
      setSelectedId(id);
      setManageDialogOpen(true);
    },

    handleBulkDelete: () =>
      bulk((i) => remove.mutateAsync(i.id), "addUsers.messages.codesDeleted"),
    handleBulkDisable: () =>
      bulk(
        (invite) => setActive.mutateAsync({ invite, active: false }),
        "addUsers.messages.codesDisabled",
      ),
    handleBulkEnable: () =>
      bulk(
        (invite) => setActive.mutateAsync({ invite, active: true }),
        "addUsers.messages.codesEnabled",
      ),

    toggleCodeSelection: (id: string) =>
      setSelectedIds((prev) =>
        prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id],
      ),

    toggleBulkMode: () => {
      setBulkMode(!bulkMode);
      setSelectedIds([]);
    },
  };
}
