"use client";

import { createFileRoute } from "@tanstack/react-router";
import { Plus, Search } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Forbidden } from "@/components/Forbidden";
import {
  CreateRoleDialog,
  ManageRoleDialog,
  RoleList,
} from "@/components/manage-roles";
import { UserPicker } from "@/components/pickers/UserPicker";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useRoleManagement } from "@/hooks/useRoleManagement";

export const Route = createFileRoute("/manage-roles")({
  component: ManageRolesPage,
});

function ManageRolesPage() {
  const { t } = useTranslation();
  const {
    filterText,
    setFilterText,
    createOpen,
    setCreateOpen,
    pickerOpen,
    setPickerOpen,
    selectedRole,
    openRole,
    closeRole,
    roles,
    holders,
    isLoadingHolders,
    grantedBy,
    isChanging,
    isLoading,
    userTypeLoading,
    allowed,
    isCreating,
    isDeleting,
    createRole,
    deleteRole,
    giveRole,
    takeRole,
  } = useRoleManagement();

  if (!userTypeLoading && !allowed) {
    return (
      <Forbidden
        testid="manage-roles-forbidden"
        message={t("manageRoles.forbidden")}
      />
    );
  }

  if (isLoading || userTypeLoading) {
    return (
      <div className="max-w-4xl mx-auto space-y-6">
        <h1 className="text-3xl font-bold">{t("manageRoles.title")}</h1>
        <div className="flex items-center justify-center py-12">
          <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  return (
    <div
      className="max-w-4xl mx-auto space-y-6"
      data-testid="manage-roles-page"
    >
      <div className="space-y-2 mt-4">
        <h1 className="text-3xl font-bold">{t("manageRoles.title")}</h1>
        <p className="text-sm text-muted-foreground">
          {t("manageRoles.description")}
        </p>
      </div>

      <Button
        onClick={() => setCreateOpen(true)}
        variant="outline"
        className="w-full md:w-auto bg-primary-light hover:bg-primary-light/90 h-12 px-6 font-semibold rounded-xl"
        data-testid="create-role-button"
      >
        <Plus className="w-5 h-5 mr-2" />
        {t("manageRoles.create.title")}
      </Button>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input
          placeholder={t("manageRoles.filterPlaceholder")}
          value={filterText}
          onChange={(event) => setFilterText(event.target.value)}
          className="pl-9"
          data-testid="role-filter"
        />
      </div>

      <RoleList roles={roles} onManage={openRole} />

      {/* Mounted only while open, so every new role starts from empty fields. */}
      {createOpen && (
        <CreateRoleDialog
          open
          onOpenChange={setCreateOpen}
          onCreate={createRole}
          isCreating={isCreating}
        />
      )}

      <ManageRoleDialog
        open={selectedRole !== undefined && !pickerOpen}
        onOpenChange={(open) => (open ? undefined : closeRole())}
        role={selectedRole}
        holders={holders}
        isLoadingHolders={isLoadingHolders}
        grantedBy={grantedBy}
        onAddHolder={() => setPickerOpen(true)}
        onRemoveHolder={takeRole}
        isChanging={isChanging}
        onDelete={deleteRole}
        isDeleting={isDeleting}
      />

      <UserPicker
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        title={t("manageRoles.detail.add")}
        description={t("manageRoles.detail.addDescription", {
          role: selectedRole?.displayName,
        })}
        exclude={holders.map((holder) => holder.id)}
        onPick={giveRole}
      />
    </div>
  );
}
