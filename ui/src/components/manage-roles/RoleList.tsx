import { useTranslation } from "react-i18next";
import type { Role } from "@/api/roles";
import { RoleItem } from "./RoleItem";

interface RoleListProps {
  roles: Role[];
  onManage: (id: string) => void;
}

export function RoleList({ roles, onManage }: RoleListProps) {
  const { t } = useTranslation();

  if (roles.length === 0) {
    return (
      <p
        className="text-sm text-muted-foreground"
        data-testid="role-list-empty"
      >
        {t("manageRoles.noRoles")}
      </p>
    );
  }

  return (
    <div
      className="space-y-3"
      data-testid="role-list"
      data-role-count={roles.length}
    >
      {roles.map((role) => (
        <RoleItem key={role.id} role={role} onManage={onManage} />
      ))}
    </div>
  );
}
