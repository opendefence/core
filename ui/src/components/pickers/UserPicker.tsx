import { useState } from "react";
import { Search } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useUsers } from "@/api/users";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";

interface UserPickerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  /** Ids the caller already has, left out of the list. */
  exclude: string[];
  onPick: (userId: string) => void;
}

/** Picks one active user. Used wherever a user joins a role or a group. */
export function UserPicker({
  open,
  onOpenChange,
  title,
  description,
  exclude,
  onPick,
}: UserPickerProps) {
  const { t } = useTranslation();
  const [filterText, setFilterText] = useState("");
  const { data: users, isLoading } = useUsers("active");

  const text = filterText.toLowerCase();
  const choices =
    users
      ?.filter((user) => !exclude.includes(user.id))
      .filter((user) => user.callsign.toLowerCase().includes(text))
      .sort((a, b) => a.callsign.localeCompare(b.callsign)) ?? [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="user-picker">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder={t("pickers.filterUsers")}
            value={filterText}
            onChange={(event) => setFilterText(event.target.value)}
            className="pl-9"
            data-testid="user-picker-filter"
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
              data-testid="user-picker-empty"
            >
              {t("pickers.noUsers")}
            </p>
          )}
          <div className="space-y-1 pr-2">
            {choices.map((user) => (
              <button
                key={user.id}
                onClick={() => onPick(user.id)}
                className="w-full text-left px-3 py-2 rounded-lg hover:bg-accent transition-colors"
                data-testid="user-picker-choice"
                data-callsign={user.callsign}
              >
                {user.callsign}
              </button>
            ))}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
