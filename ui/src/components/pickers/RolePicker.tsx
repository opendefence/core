import { useState } from "react";
import { Search } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useRoles } from "@/api/roles";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";

interface RolePickerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  /** Ids the caller already has, left out of the list. */
  exclude: string[];
  onPick: (roleId: string) => void;
}

/** Picks one role. Used wherever a role is granted to a group or an invite. */
export function RolePicker({
  open,
  onOpenChange,
  title,
  description,
  exclude,
  onPick,
}: RolePickerProps) {
  const { t } = useTranslation();
  const [filterText, setFilterText] = useState("");
  const { data: roles, isLoading } = useRoles();

  const text = filterText.toLowerCase();
  const choices =
    roles
      ?.filter((role) => !exclude.includes(role.id))
      .filter(
        (role) =>
          role.displayName.toLowerCase().includes(text) ||
          role.name.includes(text),
      )
      .sort((a, b) => a.displayName.localeCompare(b.displayName)) ?? [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="role-picker">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder={t("pickers.filterRoles")}
            value={filterText}
            onChange={(event) => setFilterText(event.target.value)}
            className="pl-9"
            data-testid="role-picker-filter"
          />
        </div>
        <ScrollArea className="h-[260px] rounded-md">
          {isLoading && (
            <p className="text-sm text-muted-foreground p-2">
              {t("pickers.loading")}
            </p>
          )}
          {!isLoading && choices.length === 0 && (
            <p
              className="text-sm text-muted-foreground p-2"
              data-testid="role-picker-empty"
            >
              {t("pickers.noRoles")}
            </p>
          )}
          <div className="space-y-1 pr-2">
            {choices.map((role) => (
              <button
                key={role.id}
                onClick={() => onPick(role.id)}
                className="w-full text-left px-3 py-2 rounded-lg hover:bg-accent transition-colors"
                data-testid="role-picker-choice"
                data-role-name={role.name}
              >
                <span className="text-sm">{role.displayName}</span>
                <span className="block font-mono text-xs text-muted-foreground">
                  {role.name}
                </span>
              </button>
            ))}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
