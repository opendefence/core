import { useState } from "react";
import { cn } from "cn";
import { useTranslation } from "react-i18next";
import type { Group } from "@/api/groups";
import { NAME_MAX, NAME_PATTERN } from "@/api/names";
import {
  isProtected,
  SUPERADMIN_ROLE,
  type Member,
  type Role,
} from "@/api/roles";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { RoleDetail } from "./RoleDetail";

interface CreateRoleDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreate: (name: string, displayName: string) => void;
  isCreating: boolean;
}

export function CreateRoleDialog({
  open,
  onOpenChange,
  onCreate,
  isCreating,
}: CreateRoleDialogProps) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [displayName, setDisplayName] = useState("");

  const nameOk = NAME_PATTERN.test(name) && name.length <= NAME_MAX;
  const ready = nameOk && displayName.trim().length > 0 && !isCreating;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="create-role-dialog">
        <DialogHeader>
          <DialogTitle>{t("manageRoles.create.title")}</DialogTitle>
          <DialogDescription>
            {t("manageRoles.create.description")}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div className="space-y-2">
            <Label htmlFor="role-display-name">
              {t("manageRoles.create.displayNameLabel")}
            </Label>
            <Input
              id="role-display-name"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              data-testid="create-role-display-name"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="role-name">
              {t("manageRoles.create.nameLabel")}
            </Label>
            <Input
              id="role-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="font-mono"
              maxLength={NAME_MAX}
              data-testid="create-role-name"
            />
            <p
              className={cn(
                "text-xs",
                name && !nameOk ? "text-destructive" : "text-muted-foreground",
              )}
            >
              {name && !nameOk
                ? t("manageRoles.create.nameInvalid")
                : t("manageRoles.create.nameHelp")}
            </p>
          </div>
        </div>
        <div className="flex gap-3 pt-4 flex-col sm:flex-row">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            className="flex-1 h-11"
            data-testid="create-role-cancel"
          >
            {t("manageRoles.cancel")}
          </Button>
          <Button
            variant="outline"
            disabled={!ready}
            onClick={() => onCreate(name, displayName.trim())}
            className="flex-1 h-11 bg-primary-light hover:bg-primary-light/90"
            data-testid="create-role-confirm"
          >
            {isCreating
              ? t("manageRoles.creating")
              : t("manageRoles.create.submit")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

interface ManageRoleDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  role?: Role;
  holders: Member[];
  isLoadingHolders: boolean;
  grantedBy: Group[];
  onAddHolder: () => void;
  onRemoveHolder: (userId: string) => void;
  isChanging: boolean;
  onDelete: () => void;
  isDeleting: boolean;
}

export function ManageRoleDialog({
  open,
  onOpenChange,
  role,
  holders,
  isLoadingHolders,
  grantedBy,
  onAddHolder,
  onRemoveHolder,
  isChanging,
  onDelete,
  isDeleting,
}: ManageRoleDialogProps) {
  const { t } = useTranslation();
  const kept = role ? isProtected(role) : false;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-md flex flex-col"
        data-testid="manage-role-dialog"
        data-role-name={role?.name ?? ""}
      >
        <DialogHeader>
          <DialogTitle>{role?.displayName}</DialogTitle>
          <DialogDescription>
            <span className="font-mono text-foreground">{role?.name}</span>
          </DialogDescription>
        </DialogHeader>
        <ScrollArea className="flex-1 min-h-0">
          <div className="space-y-4 pt-2 pr-2">
            <RoleDetail
              holders={holders}
              isLoadingHolders={isLoadingHolders}
              grantedBy={grantedBy}
              onAdd={onAddHolder}
              onRemove={onRemoveHolder}
              isChanging={isChanging}
            />
            <div className="space-y-3 text-sm text-muted-foreground">
              <p>{t("manageRoles.manage.namePermanent")}</p>
              {kept && (
                <p data-testid="manage-role-protected">
                  {role?.name === SUPERADMIN_ROLE
                    ? t("manageRoles.manage.superadminKept")
                    : t("manageRoles.manage.managedKept")}
                </p>
              )}
            </div>
          </div>
        </ScrollArea>
        <div className="flex flex-col gap-3 pt-4">
          <Button
            variant="destructive"
            onClick={onDelete}
            className="w-full"
            disabled={kept || isDeleting}
            data-testid="manage-role-delete-button"
          >
            {isDeleting
              ? t("manageRoles.deleting")
              : t("manageRoles.manage.delete")}
          </Button>
          <Button
            variant="ghost"
            onClick={() => onOpenChange(false)}
            className="w-full"
            data-testid="manage-role-cancel-button"
          >
            {t("manageRoles.cancel")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
