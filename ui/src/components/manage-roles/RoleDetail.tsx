import { Plus, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { Group } from "@/api/groups";
import type { Member } from "@/api/roles";
import { Button } from "@/components/ui/button";

interface RoleDetailProps {
  holders: Member[];
  isLoadingHolders: boolean;
  grantedBy: Group[];
  onAdd: () => void;
  onRemove: (userId: string) => void;
  isChanging: boolean;
}

/** Who holds the role directly, and which groups grant it to their members. */
export function RoleDetail({
  holders,
  isLoadingHolders,
  grantedBy,
  onAdd,
  onRemove,
  isChanging,
}: RoleDetailProps) {
  const { t } = useTranslation();

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <h4 className="text-sm font-semibold">
          {t("manageRoles.detail.holders", { count: holders.length })}
        </h4>
        {isLoadingHolders && (
          <p className="text-sm text-muted-foreground">
            {t("manageRoles.detail.loadingHolders")}
          </p>
        )}
        {!isLoadingHolders && holders.length === 0 && (
          <p
            className="text-sm text-muted-foreground"
            data-testid="role-holders-empty"
          >
            {t("manageRoles.detail.noHolders")}
          </p>
        )}
        <div className="space-y-1" data-testid="role-holders">
          {holders.map((holder) => (
            <div
              key={holder.id}
              className="flex items-center justify-between px-3 py-2 rounded-lg bg-accent/40"
              data-testid="role-holder"
              data-callsign={holder.callsign}
            >
              <span className="text-sm">{holder.callsign}</span>
              <button
                onClick={() => onRemove(holder.id)}
                disabled={isChanging}
                className="text-muted-foreground hover:text-foreground disabled:opacity-50"
                aria-label={t("manageRoles.detail.remove")}
                data-testid="role-holder-remove"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
        <Button
          variant="outline"
          onClick={onAdd}
          disabled={isChanging}
          className="w-full"
          data-testid="role-add-holder"
        >
          <Plus className="w-4 h-4 mr-2" />
          {t("manageRoles.detail.add")}
        </Button>
      </div>

      {grantedBy.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-semibold">
            {t("manageRoles.detail.grantedBy")}
          </h4>
          <ul
            className="text-sm text-muted-foreground space-y-1"
            data-testid="role-granting-groups"
          >
            {grantedBy.map((group) => (
              <li key={group.id} data-group-name={group.name}>
                {group.displayName}
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted-foreground">
            {t("manageRoles.detail.throughGroups")}
          </p>
        </div>
      )}
    </div>
  );
}
