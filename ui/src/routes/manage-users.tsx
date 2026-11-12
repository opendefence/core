"use client";

import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { HelpCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRequireSuperadmin } from "@/hooks/auth/useRequireSuperadmin";
import { Forbidden } from "@/components/Forbidden";
import { TypeConfirmationModal } from "@/components/ConfirmationModals";
import { useTranslation } from "react-i18next";
import { useUserManagement } from "@/hooks/api/useUserManagement";
import { useWalkthrough } from "@/hooks/useWalkthrough";
import {
  UserList,
  BulkActionsBar,
  UserManagementDialog,
  WalkthroughDialog,
} from "@/components/manage-users";

export const Route = createFileRoute("/manage-users")({
  component: ManageUsersPage,
});

function ManageUsersPage() {
  const [administratorsOpen, setAdministratorsOpen] = useState(true);
  const [fightersOpen, setFightersOpen] = useState(false);
  const {
    callsign,
    isLoading: userTypeLoading,
    allowed,
  } = useRequireSuperadmin({
    noCallsign: "manageUsers.messages.noCandidateFound",
    forbidden: "manageUsers.forbidden",
  });
  const [walkthroughOpen, setWalkthroughOpen] = useWalkthrough(
    `manage-users-walkthrough-${callsign}`,
    !userTypeLoading,
  );
  const { t } = useTranslation();

  const {
    administrators,
    fighters,
    isLoading,
    selectedUser,
    openUser,
    userDialogOpen,
    setUserDialogOpen,
    selectedUsers,
    bulkMode,
    bulkAction,
    hasAdminSelected,
    promoteConfirmOpen,
    setPromoteConfirmOpen,
    demoteConfirmOpen,
    setDemoteConfirmOpen,
    deleteConfirmOpen,
    setDeleteConfirmOpen,
    bulkConfirmOpen,
    setBulkConfirmOpen,
    promoteUserMutation,
    demoteUserMutation,
    deleteUserMutation,
    isAdmin,
    isCurrentUser,
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
  } = useUserManagement({ currentCallsign: callsign });

  const handleAdministratorsOpen = (open: boolean) => {
    setAdministratorsOpen(open);
    if (open) setFightersOpen(false);
  };

  const handleFightersOpen = (open: boolean) => {
    setFightersOpen(open);
    if (open) setAdministratorsOpen(false);
  };

  if (!userTypeLoading && !allowed) {
    return (
      <Forbidden
        testid="manage-users-forbidden"
        message={t("manageUsers.forbidden")}
      />
    );
  }

  if (isLoading || userTypeLoading) {
    return (
      <div
        data-testid="manage-users-loading"
        className="max-w-4xl mx-auto space-y-6"
      >
        <h1 className="text-3xl font-bold">{t("manageUsers.title")}</h1>
        <div className="flex items-center justify-center py-12">
          <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  const isMutating =
    promoteUserMutation.isPending ||
    demoteUserMutation.isPending ||
    deleteUserMutation.isPending;

  return (
    <div
      data-testid="manage-users-page"
      data-bulk-mode={bulkMode ? "true" : "false"}
      className="max-w-4xl mx-auto space-y-6"
    >
      <div className="flex items-center justify-between">
        <div className="space-y-2 flex-1 mt-4">
          <h1 className="text-3xl font-bold">{t("manageUsers.title")}</h1>
        </div>
        <Button
          data-testid="manage-users-help-button"
          variant="ghost"
          size="icon"
          onClick={() => setWalkthroughOpen(true)}
          className="shrink-0"
        >
          <HelpCircle className="w-5 h-5" />
        </Button>
      </div>

      <div className="flex gap-3">
        <Button
          data-testid="manage-users-bulk-toggle"
          variant={bulkMode ? "ghost" : "outline"}
          onClick={toggleBulkMode}
          className={
            "rounded-xl" +
            (bulkMode ? " bg-primary-light hover:bg-primary-light/90" : "")
          }
        >
          {bulkMode ? t("manageUsers.exitBulkMode") : t("manageUsers.bulkMode")}
        </Button>
      </div>

      {bulkMode && (
        <BulkActionsBar
          selectedCount={selectedUsers.length}
          hasAdminSelected={hasAdminSelected}
          onPromote={handleBulkPromote}
          onDemote={handleBulkDemote}
          onRemove={handleBulkRemove}
        />
      )}

      <UserList
        testIdPrefix="administrators-list"
        title={t("manageUsers.administrators")}
        users={administrators}
        open={administratorsOpen}
        onOpenChange={handleAdministratorsOpen}
        emptyMessage={t("manageUsers.noAdministrators")}
        bulkMode={bulkMode}
        selectedUsers={selectedUsers}
        currentCallsign={callsign}
        onUserClick={openUser}
        onUserSelect={toggleUserSelection}
      />

      <UserList
        testIdPrefix="fighters-list"
        title={t("manageUsers.fighters")}
        users={fighters}
        open={fightersOpen}
        onOpenChange={handleFightersOpen}
        emptyMessage={t("manageUsers.noFighters")}
        bulkMode={bulkMode}
        selectedUsers={selectedUsers}
        currentCallsign={callsign}
        onUserClick={openUser}
        onUserSelect={toggleUserSelection}
      />

      <WalkthroughDialog
        open={walkthroughOpen}
        onOpenChange={setWalkthroughOpen}
      />

      <UserManagementDialog
        user={selectedUser}
        open={userDialogOpen}
        onOpenChange={setUserDialogOpen}
        isAdmin={selectedUser ? isAdmin(selectedUser) : false}
        isCurrentUser={selectedUser ? isCurrentUser(selectedUser) : false}
        administratorsCount={administrators.length}
        isLoading={isMutating}
        onPromote={handlePromoteClick}
        onDemote={handleDemoteClick}
        onRemove={handleRemoveClick}
      />

      <TypeConfirmationModal
        open={promoteConfirmOpen}
        onOpenChange={setPromoteConfirmOpen}
        title={t("manageUsers.confirmModals.promote.title")}
        description={t("manageUsers.confirmModals.promote.description", {
          callsign: selectedUser?.callsign,
        })}
        onConfirm={handlePromoteConfirm}
        isLoading={promoteUserMutation.isPending}
      />

      <TypeConfirmationModal
        open={demoteConfirmOpen}
        onOpenChange={setDemoteConfirmOpen}
        title={t("manageUsers.confirmModals.demote.title")}
        description={t("manageUsers.confirmModals.demote.description", {
          callsign: selectedUser?.callsign,
        })}
        onConfirm={handleDemoteConfirm}
        isLoading={demoteUserMutation.isPending}
      />

      <TypeConfirmationModal
        open={deleteConfirmOpen}
        onOpenChange={setDeleteConfirmOpen}
        title={t("manageUsers.confirmModals.remove.title")}
        description={t("manageUsers.confirmModals.remove.description", {
          callsign: selectedUser?.callsign,
        })}
        onConfirm={handleRemoveConfirm}
        isLoading={deleteUserMutation.isPending}
      />

      <TypeConfirmationModal
        open={bulkConfirmOpen}
        onOpenChange={setBulkConfirmOpen}
        title={t("manageUsers.bulkConfirm.title")}
        description={
          bulkAction
            ? t(`manageUsers.bulkConfirm.${bulkAction}Description`, {
                count: selectedUsers.length,
              })
            : ""
        }
        onConfirm={confirmBulkAction}
        isLoading={false}
      />
    </div>
  );
}
