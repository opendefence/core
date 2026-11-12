import { useTranslation } from "react-i18next";
import type { Group } from "@/api/groups";
import { Button } from "@/components/ui/button";
import type { Inherited } from "@/hooks/useGroupManagement";

interface GroupDetailProps {
  group?: Group;
  parent?: Group;
  inherited: Inherited[];
  onRename: () => void;
  onMove: () => void;
  onDelete: () => void;
  isBusy: boolean;
}

export function GroupDetail({
  group,
  parent,
  inherited,
  onRename,
  onMove,
  onDelete,
  isBusy,
}: GroupDetailProps) {
  const { t } = useTranslation();

  if (!group) {
    return (
      <p
        className="flex flex-1 items-center justify-center text-sm text-muted-foreground"
        data-testid="group-detail-empty"
      >
        {t("manageGroups.selectGroup")}
      </p>
    );
  }

  return (
    <div
      className="space-y-5"
      data-testid="group-detail"
      data-group-name={group.name}
    >
      <div>
        <h2 className="text-xl font-bold">{group.displayName}</h2>
        <p className="font-mono text-xs text-muted-foreground">{group.name}</p>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={onRename}
          disabled={isBusy}
          data-testid="group-rename-button"
        >
          {t("manageGroups.rename.title")}
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={onMove}
          disabled={isBusy}
          data-testid="group-move-button"
        >
          {t("manageGroups.move.title")}
        </Button>
        <Button
          variant="destructive"
          size="sm"
          onClick={onDelete}
          disabled={isBusy}
          data-testid="group-delete-button"
        >
          {t("manageGroups.delete.title")}
        </Button>
      </div>

      <Section title={t("manageGroups.detail.parent")}>
        <p className="text-sm">
          {parent ? parent.displayName : t("manageGroups.detail.root")}
        </p>
      </Section>

      {inherited.length > 0 && (
        <Section title={t("manageGroups.detail.inherited")}>
          <ul className="text-sm space-y-1" data-testid="group-inherited-roles">
            {inherited.map(({ from, roles }) => (
              <li key={from.id} data-group-name={from.name}>
                {roles.map((role) => role.displayName).join(", ")}
                <span className="text-muted-foreground">
                  {" "}
                  {t("manageGroups.detail.fromGroup", {
                    group: from.displayName,
                  })}
                </span>
              </li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      {children}
    </div>
  );
}
