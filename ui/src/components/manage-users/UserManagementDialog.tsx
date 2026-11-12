"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useTranslation } from "react-i18next";
import {
  useGiveUserRole,
  useTakeUserRole,
  useUserGroups,
  type User,
} from "@/api/users";
import {
  granting,
  useAddGroupMember,
  useGroups,
  useRemoveGroupMember,
} from "@/api/groups";
import { RemovableList } from "@/components/manage-groups/RemovableList";
import { GroupPicker } from "@/components/pickers/GroupPicker";
import { RolePicker } from "@/components/pickers/RolePicker";

interface UserManagementDialogProps {
  user: User | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  isAdmin: boolean;
  isCurrentUser: boolean;
  administratorsCount: number;
  isLoading: boolean;
  onPromote: () => void;
  onDemote: () => void;
  onRemove: () => void;
  /** Reload the list, so an edit here shows in the rows behind. */
  onChanged: () => void;
}

export function UserManagementDialog({
  user,
  open,
  onOpenChange,
  isAdmin,
  isCurrentUser,
  administratorsCount,
  isLoading,
  onPromote,
  onDemote,
  onRemove,
  onChanged,
}: UserManagementDialogProps) {
  const { t } = useTranslation();
  const [rolePickerOpen, setRolePickerOpen] = useState(false);
  const [groupPickerOpen, setGroupPickerOpen] = useState(false);

  const { data: groups } = useGroups();
  const { data: userGroups, refetch: refetchGroups } = useUserGroups(user?.id);

  const changed = () => {
    setRolePickerOpen(false);
    setGroupPickerOpen(false);
    refetchGroups();
    onChanged();
  };
  const failed = (error: Error) => toast.error(error.message);
  const options = { onSuccess: changed, onError: failed };

  const giveRole = useGiveUserRole(options);
  const takeRole = useTakeUserRole(options);
  const addGroup = useAddGroupMember(options);
  const removeGroup = useRemoveGroupMember(options);

  const isChanging =
    giveRole.isPending ||
    takeRole.isPending ||
    addGroup.isPending ||
    removeGroup.isPending;

  const canRemove = !isCurrentUser && !(isAdmin && administratorsCount <= 1);
  const canDemote = !isCurrentUser;

  const directRoles = user?.roles ?? [];
  const direct = new Set(directRoles.map((role) => role.id));
  const roleEntries = [
    ...directRoles.map((role) => ({ id: role.id, label: role.displayName })),
    ...(user?.effectiveRoles ?? [])
      .filter((role) => !direct.has(role.id))
      .map((role) => ({
        id: role.id,
        label: role.displayName,
        note: t("manageUsers.userDialog.fromGroup", {
          group: granting(groups, role.id)
            .map((group) => group.displayName)
            .join(", "),
        }),
        fixed: true,
      })),
  ];
  const groupEntries = (userGroups ?? []).map((group) => ({
    id: group.id,
    label: group.displayName,
  }));

  return (
    <>
      <Dialog
        open={open && !rolePickerOpen && !groupPickerOpen}
        onOpenChange={onOpenChange}
      >
        <DialogContent
          data-testid="user-management-dialog"
          data-user-callsign={user?.callsign ?? ""}
          data-user-is-admin={isAdmin ? "true" : "false"}
          data-user-is-current={isCurrentUser ? "true" : "false"}
          className="sm:max-w-md max-h-[90vh] flex flex-col"
        >
          <DialogHeader>
            <DialogTitle>{t("manageUsers.userDialog.title")}</DialogTitle>
            <DialogDescription>
              {t("common.managing")}{" "}
              <span className="font-semibold text-foreground">
                {user?.callsign}
              </span>
            </DialogDescription>
          </DialogHeader>
          <ScrollArea className="flex-1 min-h-0 px-6">
            <div className="space-y-5 py-4">
              <p className="text-sm text-muted-foreground">
                {t("manageUsers.userDialog.state")}{" "}
                <span
                  className="font-medium text-foreground"
                  data-testid="user-dialog-state"
                >
                  {user ? t(`manageUsers.states.${user.state}`) : ""}
                </span>
              </p>

              <div className="space-y-2">
                <h3 className="text-sm font-semibold">
                  {t("manageUsers.userDialog.roles")}
                </h3>
                <RemovableList
                  entries={roleEntries}
                  empty={t("manageUsers.userDialog.noRoles")}
                  removeLabel={t("manageUsers.userDialog.removeRole")}
                  onRemove={(roleId) =>
                    user && takeRole.mutate({ userId: user.id, roleId })
                  }
                  disabled={isChanging || isLoading}
                  testid="user-roles"
                />
                <Button
                  variant="outline"
                  onClick={() => setRolePickerOpen(true)}
                  disabled={isChanging || isLoading}
                  className="w-full"
                  data-testid="user-add-role"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  {t("manageUsers.userDialog.addRole")}
                </Button>
              </div>

              <div className="space-y-2">
                <h3 className="text-sm font-semibold">
                  {t("manageUsers.userDialog.groups")}
                </h3>
                <RemovableList
                  entries={groupEntries}
                  empty={t("manageUsers.userDialog.noGroups")}
                  removeLabel={t("manageUsers.userDialog.removeGroup")}
                  onRemove={(groupId) =>
                    user && removeGroup.mutate({ groupId, userId: user.id })
                  }
                  disabled={isChanging || isLoading}
                  testid="user-groups"
                />
                <Button
                  variant="outline"
                  onClick={() => setGroupPickerOpen(true)}
                  disabled={isChanging || isLoading}
                  className="w-full"
                  data-testid="user-add-group"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  {t("manageUsers.userDialog.addGroup")}
                </Button>
              </div>
            </div>
          </ScrollArea>
          <DialogFooter className="flex-row gap-2 sm:justify-between pt-4 border-t">
            <Button
              data-testid="user-management-dialog-back-button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
              className="flex-1"
              disabled={isLoading}
            >
              {t("manageUsers.userDialog.goBack")}
            </Button>

            <Button
              data-testid="user-management-dialog-remove-button"
              variant="outline"
              onClick={onRemove}
              className="flex-1 bg-transparent"
              disabled={isLoading || !canRemove}
              title={
                isCurrentUser
                  ? t("manageUsers.tooltips.cannotRemove")
                  : undefined
              }
            >
              {t("manageUsers.userDialog.remove")}
            </Button>

            {!isAdmin ? (
              <Button
                data-testid="user-management-dialog-promote-button"
                variant={"outline"}
                onClick={onPromote}
                className="flex-1 bg-primary-light hover:bg-primary-light/90"
                disabled={isLoading}
              >
                {t("manageUsers.userDialog.promote")}
              </Button>
            ) : (
              <Button
                data-testid="user-management-dialog-demote-button"
                onClick={onDemote}
                variant={"outline"}
                className="flex-1 bg-primary-light hover:bg-primary-light/90"
                disabled={isLoading || !canDemote}
                title={
                  isCurrentUser
                    ? t("manageUsers.tooltips.cannotDemote")
                    : undefined
                }
              >
                {t("manageUsers.userDialog.demote")}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <RolePicker
        open={rolePickerOpen}
        onOpenChange={setRolePickerOpen}
        title={t("manageUsers.userDialog.addRole")}
        description={t("manageUsers.userDialog.addRoleDescription", {
          callsign: user?.callsign,
        })}
        exclude={directRoles.map((role) => role.id)}
        onPick={(roleId) =>
          user && giveRole.mutate({ userId: user.id, roleId })
        }
      />

      <GroupPicker
        open={groupPickerOpen}
        onOpenChange={setGroupPickerOpen}
        title={t("manageUsers.userDialog.addGroup")}
        description={t("manageUsers.userDialog.addGroupDescription", {
          callsign: user?.callsign,
        })}
        exclude={groupEntries.map((group) => group.id)}
        onPick={(groupId) =>
          user && groupId && addGroup.mutate({ groupId, userId: user.id })
        }
      />
    </>
  );
}
