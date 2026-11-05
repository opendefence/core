import { useTranslation } from "react-i18next";
import type { Group } from "@/api/groups";
import type { Inherited } from "@/hooks/useGroupManagement";

interface GroupDetailProps {
  group?: Group;
  parent?: Group;
  inherited: Inherited[];
}

export function GroupDetail({ group, parent, inherited }: GroupDetailProps) {
  const { t } = useTranslation();

  if (!group) {
    return (
      <p
        className="text-sm text-muted-foreground"
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

      <Section title={t("manageGroups.detail.parent")}>
        <p className="text-sm">
          {parent ? parent.displayName : t("manageGroups.detail.root")}
        </p>
      </Section>

      <Section title={t("manageGroups.detail.roles")}>
        {group.roles.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {t("manageGroups.detail.noRoles")}
          </p>
        ) : (
          <ul className="text-sm space-y-1" data-testid="group-roles">
            {group.roles.map((role) => (
              <li key={role.id} data-role-name={role.name}>
                {role.displayName}
              </li>
            ))}
          </ul>
        )}
        <p className="text-xs text-muted-foreground">
          {t("manageGroups.detail.rolesReach")}
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

      <Section title={t("manageGroups.detail.managers")}>
        {group.managers.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {t("manageGroups.detail.noManagers")}
          </p>
        ) : (
          <ul className="text-sm space-y-1" data-testid="group-managers">
            {group.managers.map((manager) => (
              <li key={manager.id} data-callsign={manager.callsign}>
                {manager.callsign}
              </li>
            ))}
          </ul>
        )}
      </Section>
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
