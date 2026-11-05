import { useState } from "react";
import { cn } from "cn";
import { useTranslation } from "react-i18next";
import type { Group } from "@/api/groups";
import { NAME_MAX, NAME_PATTERN } from "@/api/names";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface CreateGroupDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The selected group, offered as the parent of the new one. */
  under?: Group;
  onCreate: (
    name: string,
    displayName: string,
    parentId: string | null,
  ) => void;
  isCreating: boolean;
}

export function CreateGroupDialog({
  open,
  onOpenChange,
  under,
  onCreate,
  isCreating,
}: CreateGroupDialogProps) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [atRoot, setAtRoot] = useState(under === undefined);

  const nameOk = NAME_PATTERN.test(name) && name.length <= NAME_MAX;
  const ready = nameOk && displayName.trim().length > 0 && !isCreating;
  const parentId = atRoot ? null : (under?.id ?? null);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="create-group-dialog">
        <DialogHeader>
          <DialogTitle>{t("manageGroups.create.title")}</DialogTitle>
          <DialogDescription>
            {t("manageGroups.create.description")}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div className="space-y-2">
            <Label htmlFor="group-display-name">
              {t("manageGroups.create.displayNameLabel")}
            </Label>
            <Input
              id="group-display-name"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              data-testid="create-group-display-name"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="group-name">
              {t("manageGroups.create.nameLabel")}
            </Label>
            <Input
              id="group-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="font-mono"
              maxLength={NAME_MAX}
              data-testid="create-group-name"
            />
            <p
              className={cn(
                "text-xs",
                name && !nameOk ? "text-destructive" : "text-muted-foreground",
              )}
            >
              {name && !nameOk
                ? t("manageGroups.create.nameInvalid")
                : t("manageGroups.create.nameHelp")}
            </p>
          </div>
          {under && (
            <div className="flex items-center gap-3">
              <Checkbox
                id="group-at-root"
                checked={atRoot}
                onCheckedChange={(checked) => setAtRoot(checked === true)}
                data-testid="create-group-at-root"
              />
              <Label htmlFor="group-at-root" className="text-sm font-normal">
                {t("manageGroups.create.atRoot")}
              </Label>
            </div>
          )}
          <p className="text-xs text-muted-foreground">
            {parentId
              ? t("manageGroups.create.under", { group: under?.displayName })
              : t("manageGroups.create.topLevel")}
          </p>
        </div>
        <div className="flex gap-3 pt-4 flex-col sm:flex-row">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            className="flex-1 h-11"
            data-testid="create-group-cancel"
          >
            {t("manageGroups.cancel")}
          </Button>
          <Button
            variant="outline"
            disabled={!ready}
            onClick={() => onCreate(name, displayName.trim(), parentId)}
            className="flex-1 h-11 bg-primary-light hover:bg-primary-light/90"
            data-testid="create-group-confirm"
          >
            {isCreating
              ? t("manageGroups.creating")
              : t("manageGroups.create.submit")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

interface RenameGroupDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  group: Group;
  onRename: (displayName: string) => void;
  isRenaming: boolean;
}

export function RenameGroupDialog({
  open,
  onOpenChange,
  group,
  onRename,
  isRenaming,
}: RenameGroupDialogProps) {
  const { t } = useTranslation();
  const [displayName, setDisplayName] = useState(group.displayName);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="rename-group-dialog">
        <DialogHeader>
          <DialogTitle>{t("manageGroups.rename.title")}</DialogTitle>
          <DialogDescription>
            {t("manageGroups.rename.description", { name: group.name })}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2 pt-2">
          <Label htmlFor="group-new-display-name">
            {t("manageGroups.create.displayNameLabel")}
          </Label>
          <Input
            id="group-new-display-name"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            data-testid="rename-group-display-name"
          />
        </div>
        <div className="flex gap-3 pt-4 flex-col sm:flex-row">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            className="flex-1 h-11"
            data-testid="rename-group-cancel"
          >
            {t("manageGroups.cancel")}
          </Button>
          <Button
            variant="outline"
            disabled={displayName.trim().length === 0 || isRenaming}
            onClick={() => onRename(displayName.trim())}
            className="flex-1 h-11 bg-primary-light hover:bg-primary-light/90"
            data-testid="rename-group-confirm"
          >
            {t("manageGroups.rename.submit")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
