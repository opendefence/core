"use client";

import { createFileRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { useInviteCodeManagement } from "@/hooks/useInviteCodeManagement";
import { Forbidden } from "@/components/Forbidden";
import { InviteCodeHeader } from "@/components/add-users/InviteCodeHeader";
import { InviteCodeItem } from "@/components/add-users/InviteCodeItem";
import { BulkActionsBar } from "@/components/add-users/BulkActionsBar";
import {
  CreateInviteDialog,
  ManageCodeDialog,
  WalkthroughDialog,
} from "@/components/add-users/InviteCodeDialogs";

export const Route = createFileRoute("/add-users")({
  component: AddUsersPage,
});

function AddUsersPage() {
  const { t } = useTranslation();
  const {
    filterText,
    setFilterText,
    createModalOpen,
    setCreateModalOpen,
    manageDialogOpen,
    closeManageDialog,
    selectedInvite,
    selectedIds,
    bulkMode,
    walkthroughOpen,
    setWalkthroughOpen,
    filteredInvites,
    isLoading,
    userTypeLoading,
    allowed,
    isCreating,
    isDeleting,
    isTogglingStatus,
    handleCreateInvite,
    handleDeleteCode,
    handleToggleStatus,
    handleCodeClick,
    handleManageClick,
    handleBulkDelete,
    handleBulkDisable,
    handleBulkEnable,
    toggleCodeSelection,
    toggleBulkMode,
  } = useInviteCodeManagement();

  if (!userTypeLoading && !allowed) {
    return <Forbidden message={t("addUsers.forbidden")} />;
  }

  if (isLoading || userTypeLoading) {
    return (
      <div className="max-w-4xl mx-auto space-y-6">
        <h1 className="text-2xl font-bold">{t("addUsers.title")}</h1>
        <div className="flex items-center justify-center py-12">
          <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <InviteCodeHeader
        filterText={filterText}
        onFilterChange={setFilterText}
        bulkMode={bulkMode}
        onToggleBulkMode={toggleBulkMode}
        onCreateClick={() => setCreateModalOpen(true)}
        onHelpClick={() => setWalkthroughOpen(true)}
        isCreating={isCreating}
      />

      {bulkMode && (
        <BulkActionsBar
          selectedCount={selectedIds.length}
          onEnable={handleBulkEnable}
          onDisable={handleBulkDisable}
          onDelete={handleBulkDelete}
        />
      )}

      <div className="space-y-3">
        {filteredInvites.map((invite) => (
          <InviteCodeItem
            key={invite.id}
            invite={invite}
            bulkMode={bulkMode}
            isSelected={selectedIds.includes(invite.id)}
            onCodeClick={(code: string, e: React.MouseEvent) => {
              e.preventDefault();
              handleCodeClick(code);
            }}
            onManageClick={(id: string, e: React.MouseEvent) => {
              e.preventDefault();
              e.stopPropagation();
              handleManageClick(id);
            }}
            onToggleSelection={toggleCodeSelection}
          />
        ))}
      </div>

      {createModalOpen && (
        <CreateInviteDialog
          open
          onOpenChange={setCreateModalOpen}
          onConfirm={handleCreateInvite}
        />
      )}

      <WalkthroughDialog
        open={walkthroughOpen}
        onOpenChange={setWalkthroughOpen}
      />

      <ManageCodeDialog
        open={manageDialogOpen}
        onOpenChange={(open) => (open ? undefined : closeManageDialog())}
        selectedInvite={selectedInvite}
        onToggleStatus={handleToggleStatus}
        onDelete={handleDeleteCode}
        isDeleting={isDeleting}
        isTogglingStatus={isTogglingStatus}
      />
    </div>
  );
}
