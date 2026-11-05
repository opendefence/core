import { useState } from "react";
import { Search } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useGroups } from "@/api/groups";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";

interface GroupPickerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  /** Ids the caller cannot choose, such as a group and everything below it. */
  exclude: string[];
  /** Offers "no group", which makes a moved group a root. */
  allowNone?: boolean;
  noneLabel?: string;
  onPick: (groupId: string | null) => void;
}

/** Picks one group. Used for a parent, a membership and an invite assignment. */
export function GroupPicker({
  open,
  onOpenChange,
  title,
  description,
  exclude,
  allowNone = false,
  noneLabel,
  onPick,
}: GroupPickerProps) {
  const { t } = useTranslation();
  const [filterText, setFilterText] = useState("");
  const { data: groups, isLoading } = useGroups();

  const text = filterText.toLowerCase();
  const choices =
    groups
      ?.filter((group) => !exclude.includes(group.id))
      .filter(
        (group) =>
          group.displayName.toLowerCase().includes(text) ||
          group.name.includes(text),
      )
      .sort((a, b) => a.displayName.localeCompare(b.displayName)) ?? [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="group-picker">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder={t("pickers.filterGroups")}
            value={filterText}
            onChange={(event) => setFilterText(event.target.value)}
            className="pl-9"
            data-testid="group-picker-filter"
          />
        </div>
        <ScrollArea className="h-[260px] rounded-md">
          {isLoading && (
            <p className="text-sm text-muted-foreground p-2">
              {t("pickers.loading")}
            </p>
          )}
          <div className="space-y-1 pr-2">
            {allowNone && (
              <button
                onClick={() => onPick(null)}
                className="w-full text-left px-3 py-2 rounded-lg hover:bg-accent transition-colors text-sm"
                data-testid="group-picker-none"
              >
                {noneLabel}
              </button>
            )}
            {!isLoading && choices.length === 0 && !allowNone && (
              <p
                className="text-sm text-muted-foreground p-2"
                data-testid="group-picker-empty"
              >
                {t("pickers.noGroups")}
              </p>
            )}
            {choices.map((group) => (
              <button
                key={group.id}
                onClick={() => onPick(group.id)}
                className="w-full text-left px-3 py-2 rounded-lg hover:bg-accent transition-colors"
                data-testid="group-picker-choice"
                data-group-name={group.name}
              >
                <span className="text-sm">{group.displayName}</span>
                <span className="block font-mono text-xs text-muted-foreground">
                  {group.name}
                </span>
              </button>
            ))}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
