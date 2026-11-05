import { Plus } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { Member } from "@/api/groups";
import { Button } from "@/components/ui/button";
import { RemovableList } from "./RemovableList";

interface GroupManagersProps {
  managers: Member[];
  onAdd: () => void;
  onRemove: (userId: string) => void;
  isChanging: boolean;
}

export function GroupManagers({
  managers,
  onAdd,
  onRemove,
  isChanging,
}: GroupManagersProps) {
  const { t } = useTranslation();

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">
        {t("manageGroups.detail.managers")}
      </h3>
      <RemovableList
        entries={managers.map((manager) => ({
          id: manager.id,
          label: manager.callsign,
        }))}
        empty={t("manageGroups.detail.noManagers")}
        removeLabel={t("manageGroups.managers.remove")}
        onRemove={onRemove}
        disabled={isChanging}
        testid="group-managers"
      />
      <p className="text-xs text-muted-foreground">
        {t("manageGroups.managers.noAuthority")}
      </p>
      <Button
        variant="outline"
        onClick={onAdd}
        disabled={isChanging}
        className="w-full"
        data-testid="group-add-manager"
      >
        <Plus className="w-4 h-4 mr-2" />
        {t("manageGroups.managers.add")}
      </Button>
    </div>
  );
}
