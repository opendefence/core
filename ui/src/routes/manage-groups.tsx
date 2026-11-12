"use client";

import { createFileRoute } from "@tanstack/react-router";
import { Plus } from "lucide-react";
import { useTranslation } from "react-i18next";
import { SimpleConfirmationModal } from "@/components/ConfirmationModals";
import { Forbidden } from "@/components/Forbidden";
import {
  CreateGroupDialog,
  GroupDetail,
  GroupManagers,
  GroupMembers,
  GroupRoles,
  GroupTree,
  RenameGroupDialog,
} from "@/components/manage-groups";
import { GroupPicker } from "@/components/pickers/GroupPicker";
import { RolePicker } from "@/components/pickers/RolePicker";
import { UserPicker } from "@/components/pickers/UserPicker";
import { Button } from "@/components/ui/button";
import { useGroupManagement } from "@/hooks/useGroupManagement";

export const Route = createFileRoute("/manage-groups")({
  component: ManageGroupsPage,
});

function ManageGroupsPage() {
  const { t } = useTranslation();
  const {
    tree,
    selectedGroup,
    parent,
    inherited,
    selectGroup,
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
    isCreating,
    isChanging,
    isDeleting,
    moveExclude,
    createGroup,
    renameGroup,
    moveGroup,
    askDelete,
    deleteGroup,
    members,
    fromBelow,
    showEffective,
    setShowEffective,
    memberPickerOpen,
    setMemberPickerOpen,
    rolePickerOpen,
    setRolePickerOpen,
    managerPickerOpen,
    setManagerPickerOpen,
    rolePickerExclude,
    isLinking,
    addMember,
    removeMember,
    grantRole,
    revokeRole,
    addManager,
    removeManager,
  } = useGroupManagement();

  if (!userTypeLoading && !allowed) {
    return (
      <Forbidden
        testid="manage-groups-forbidden"
        message={t("manageGroups.forbidden")}
      />
    );
  }

  if (isLoading || userTypeLoading) {
    return (
      <div className="max-w-4xl mx-auto space-y-6">
        <h1 className="text-3xl font-bold">{t("manageGroups.title")}</h1>
        <div className="flex items-center justify-center py-12">
          <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  return (
    <div
      className="max-w-4xl mx-auto space-y-6"
      data-testid="manage-groups-page"
    >
      <div className="space-y-2 mt-4">
        <h1 className="text-3xl font-bold">{t("manageGroups.title")}</h1>
        <p className="text-sm text-muted-foreground">
          {t("manageGroups.description")}
        </p>
      </div>

      <Button
        onClick={() => setCreateOpen(true)}
        variant="outline"
        className="w-full md:w-auto bg-primary-light hover:bg-primary-light/90 h-12 px-6 font-semibold rounded-xl"
        data-testid="create-group-button"
      >
        <Plus className="w-5 h-5 mr-2" />
        {t("manageGroups.create.title")}
      </Button>

      <div className="grid gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        <div className="flex min-h-48 flex-col p-5 bg-card border-2 border-border rounded-xl">
          <GroupTree
            tree={tree}
            selectedId={selectedGroup?.id}
            onSelect={selectGroup}
          />
        </div>
        <div className="flex min-h-48 flex-col p-5 bg-card border-2 border-border rounded-xl space-y-5">
          <GroupDetail
            group={selectedGroup}
            parent={parent}
            inherited={inherited}
            onRename={() => setRenameOpen(true)}
            onMove={() => setMoveOpen(true)}
            onDelete={askDelete}
            isBusy={isChanging || isDeleting}
          />
          {selectedGroup && (
            <>
              <GroupMembers
                members={members}
                fromBelow={fromBelow}
                showEffective={showEffective}
                onToggleEffective={setShowEffective}
                onAdd={() => setMemberPickerOpen(true)}
                onRemove={removeMember}
                isChanging={isLinking}
              />
              <GroupRoles
                roles={selectedGroup.roles}
                onAdd={() => setRolePickerOpen(true)}
                onRemove={revokeRole}
                isChanging={isLinking}
              />
              <GroupManagers
                managers={selectedGroup.managers}
                onAdd={() => setManagerPickerOpen(true)}
                onRemove={removeManager}
                isChanging={isLinking}
              />
            </>
          )}
        </div>
      </div>

      {/* Mounted only while open, so every dialog starts from fresh fields. */}
      {createOpen && (
        <CreateGroupDialog
          open
          onOpenChange={setCreateOpen}
          under={selectedGroup}
          onCreate={createGroup}
          isCreating={isCreating}
        />
      )}

      {renameOpen && selectedGroup && (
        <RenameGroupDialog
          open
          onOpenChange={setRenameOpen}
          group={selectedGroup}
          onRename={renameGroup}
          isRenaming={isChanging}
        />
      )}

      <GroupPicker
        open={moveOpen}
        onOpenChange={setMoveOpen}
        title={t("manageGroups.move.title")}
        description={t("manageGroups.move.description", {
          group: selectedGroup?.displayName,
        })}
        exclude={moveExclude}
        allowNone
        noneLabel={t("manageGroups.move.toRoot")}
        onPick={moveGroup}
      />

      <UserPicker
        open={memberPickerOpen}
        onOpenChange={setMemberPickerOpen}
        title={t("manageGroups.members.add")}
        description={t("manageGroups.members.addDescription", {
          group: selectedGroup?.displayName,
        })}
        exclude={members.map((member) => member.id)}
        onPick={addMember}
      />

      <RolePicker
        open={rolePickerOpen}
        onOpenChange={setRolePickerOpen}
        title={t("manageGroups.roles.add")}
        description={t("manageGroups.roles.addDescription", {
          group: selectedGroup?.displayName,
        })}
        exclude={rolePickerExclude}
        onPick={grantRole}
      />

      <UserPicker
        open={managerPickerOpen}
        onOpenChange={setManagerPickerOpen}
        title={t("manageGroups.managers.add")}
        description={t("manageGroups.managers.addDescription", {
          group: selectedGroup?.displayName,
        })}
        exclude={selectedGroup?.managers.map((manager) => manager.id) ?? []}
        onPick={addManager}
      />

      <SimpleConfirmationModal
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title={t("manageGroups.delete.title")}
        description={t("manageGroups.delete.description", {
          group: selectedGroup?.displayName,
        })}
        actionText={t("manageGroups.delete.title")}
        onConfirm={deleteGroup}
        isLoading={isDeleting}
        isDangerous
        testId="delete-group-modal"
      />
    </div>
  );
}
