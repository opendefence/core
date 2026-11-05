import { MoreVertical } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { Role } from "@/api/roles";

const DATE = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  year: "numeric",
});

interface RoleItemProps {
  role: Role;
  onManage: (id: string) => void;
}

export function RoleItem({ role, onManage }: RoleItemProps) {
  const { t } = useTranslation();

  return (
    <div
      data-testid="role-item"
      data-role-name={role.name}
      data-role-managed={role.managed ? "true" : "false"}
      className="flex items-center justify-between p-5 bg-card border-2 border-border rounded-xl"
    >
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="font-bold text-lg" data-testid="role-display-name">
            {role.displayName}
          </span>
          {role.managed && (
            <span
              data-testid="role-managed-badge"
              className="text-xs font-bold uppercase px-3 py-0.5 rounded-full text-blue-600 bg-blue-100 dark:bg-blue-900/30"
            >
              {t("manageRoles.managed")}
            </span>
          )}
        </div>
        <p className="font-mono text-xs text-muted-foreground mt-1">
          {role.name}
        </p>
        {role.createdAt && (
          <p className="text-xs text-muted-foreground mt-2">
            {t("manageRoles.created", {
              date: DATE.format(new Date(role.createdAt)),
            })}
          </p>
        )}
      </div>
      <button
        onClick={() => onManage(role.id)}
        className="text-muted-foreground hover:text-foreground p-2"
        data-testid="role-manage-button"
      >
        <MoreVertical className="w-5 h-5" />
      </button>
    </div>
  );
}
