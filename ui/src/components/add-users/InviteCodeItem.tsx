import type React from "react";
import { MoreVertical } from "lucide-react";
import { cn } from "cn";
import { useTranslation } from "react-i18next";
import { useGroups } from "@/api/groups";
import { isActive, type Invite } from "@/api/invites";
import { useRoles } from "@/api/roles";

const DATE = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  year: "numeric",
});

interface InviteCodeItemProps {
  invite: Invite;
  bulkMode: boolean;
  isSelected: boolean;
  onCodeClick: (code: string, e: React.MouseEvent) => void;
  onManageClick: (id: string, e: React.MouseEvent) => void;
  onToggleSelection: (id: string) => void;
}

export function InviteCodeItem({
  invite,
  bulkMode,
  isSelected,
  onCodeClick,
  onManageClick,
  onToggleSelection,
}: InviteCodeItemProps) {
  const { t } = useTranslation();
  const active = isActive(invite);
  const { data: groups } = useGroups();
  const { data: roles } = useRoles();

  const named = (ids: string[], known: { id: string; displayName: string }[]) =>
    ids
      .map((id) => known.find((entry) => entry.id === id)?.displayName)
      .filter((name) => name !== undefined);
  const assigned = [
    ...named(invite.groupIds, groups ?? []),
    ...named(invite.roleIds, roles ?? []),
  ];

  const handleClick = (e: React.MouseEvent) => {
    if (bulkMode) {
      onToggleSelection(invite.id);
    } else {
      if (!active) return;
      onCodeClick(invite.code, e);
    }
  };

  return (
    <div
      onClick={handleClick}
      data-testid="invite-code-item"
      data-invite-code={invite.code}
      data-invite-active={active ? "true" : "false"}
      data-invite-selected={isSelected ? "true" : "false"}
      className={cn(
        "flex items-center justify-between p-5 bg-card border-2 border-border rounded-xl hover:bg-accent/50 hover:border-primary/50 transition-all",
        bulkMode && isSelected && "bg-accent border-primary",
        !active ? "cursor-not-allowed" : "cursor-pointer",
      )}
    >
      <div className="flex items-center gap-4 flex-1">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span
              className="font-mono font-bold text-lg"
              data-testid="invite-code-value"
            >
              {invite.code}
            </span>
            <span
              data-testid="invite-code-status"
              data-invite-status={active ? "active" : "inactive"}
              className={cn(
                "text-xs font-bold uppercase px-3 py-0.5 rounded-full",
                active
                  ? "text-green-600 bg-green-100 dark:bg-green-900/30"
                  : "text-gray-500 bg-gray-100 dark:bg-gray-800",
              )}
            >
              {t(`addUsers.${active ? "active" : "inactive"}`)}
            </span>
          </div>
          {assigned.length > 0 && (
            <p
              className="text-xs text-muted-foreground mt-2"
              data-testid="invite-code-assignments"
            >
              {t("addUsers.assignments.gives", { names: assigned.join(", ") })}
            </p>
          )}
          {invite.createdAt && (
            <p className="text-xs text-muted-foreground mt-2">
              {t(invite.createdBy ? "addUsers.createdBy" : "addUsers.created", {
                creator: invite.createdBy?.callsign,
                date: DATE.format(new Date(invite.createdAt)),
              })}
            </p>
          )}
        </div>
      </div>
      {!bulkMode && (
        <button
          onClick={(e) => onManageClick(invite.id, e)}
          className="text-muted-foreground hover:text-foreground p-2"
          data-testid="invite-code-manage-button"
        >
          <MoreVertical className="w-5 h-5" />
        </button>
      )}
    </div>
  );
}
