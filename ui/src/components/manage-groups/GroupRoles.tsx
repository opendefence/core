import { Plus } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { GrantedRole } from "@/api/groups";
import { Button } from "@/components/ui/button";
import { RemovableList } from "./RemovableList";

interface GroupRolesProps {
  roles: GrantedRole[];
  onAdd: () => void;
  onRemove: (roleId: string) => void;
  isChanging: boolean;
}

export function GroupRoles({
  roles,
  onAdd,
  onRemove,
  isChanging,
}: GroupRolesProps) {
  const { t } = useTranslation();

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">
        {t("manageGroups.detail.roles")}
      </h3>
      <RemovableList
        entries={roles.map((role) => ({
          id: role.id,
          label: role.displayName,
        }))}
        empty={t("manageGroups.detail.noRoles")}
        removeLabel={t("manageGroups.roles.remove")}
        onRemove={onRemove}
        disabled={isChanging}
        testid="group-roles"
      />
      <p className="text-xs text-muted-foreground">
        {t("manageGroups.detail.rolesReach")}
      </p>
      <Button
        variant="outline"
        onClick={onAdd}
        disabled={isChanging}
        className="w-full"
        data-testid="group-add-role"
      >
        <Plus className="w-4 h-4 mr-2" />
        {t("manageGroups.roles.add")}
      </Button>
    </div>
  );
}
