import { useTranslation } from "react-i18next";
import { useGroups } from "@/api/groups";
import { useRoles } from "@/api/roles";
import { Checkbox } from "@/components/ui/checkbox";

interface InviteAssignmentsProps {
  roleIds: string[];
  groupIds: string[];
  onToggleRole: (roleId: string) => void;
  onToggleGroup: (groupId: string) => void;
}

/** Groups and roles the invite gives the user it creates. Both are optional. */
export function InviteAssignments({
  roleIds,
  groupIds,
  onToggleRole,
  onToggleGroup,
}: InviteAssignmentsProps) {
  const { t } = useTranslation();
  const { data: groups } = useGroups();
  const { data: roles } = useRoles();

  return (
    <div className="space-y-4">
      <Checklist
        title={t("addUsers.assignments.groups")}
        empty={t("addUsers.assignments.noGroups")}
        testid="invite-groups"
        entries={
          groups
            ?.map((group) => ({ id: group.id, label: group.displayName }))
            .sort((a, b) => a.label.localeCompare(b.label)) ?? []
        }
        chosen={groupIds}
        onToggle={onToggleGroup}
      />
      <Checklist
        title={t("addUsers.assignments.roles")}
        empty={t("addUsers.assignments.noRoles")}
        testid="invite-roles"
        entries={
          roles
            ?.map((role) => ({ id: role.id, label: role.displayName }))
            .sort((a, b) => a.label.localeCompare(b.label)) ?? []
        }
        chosen={roleIds}
        onToggle={onToggleRole}
      />
    </div>
  );
}

interface ChecklistProps {
  title: string;
  empty: string;
  testid: string;
  entries: { id: string; label: string }[];
  chosen: string[];
  onToggle: (id: string) => void;
}

function Checklist({
  title,
  empty,
  testid,
  entries,
  chosen,
  onToggle,
}: ChecklistProps) {
  return (
    <div className="space-y-2">
      <h4 className="text-sm font-semibold">{title}</h4>
      {entries.length === 0 ? (
        <p
          className="text-sm text-muted-foreground"
          data-testid={`${testid}-empty`}
        >
          {empty}
        </p>
      ) : (
        <div className="rounded-md border border-border">
          <div className="p-2 space-y-1" data-testid={testid}>
            {entries.map((entry) => (
              <label
                key={entry.id}
                className="flex items-center gap-3 px-2 py-1.5 rounded-lg hover:bg-accent/60 cursor-pointer"
                data-testid={`${testid}-entry`}
                data-entry-label={entry.label}
                data-entry-chosen={chosen.includes(entry.id) ? "true" : "false"}
              >
                <Checkbox
                  checked={chosen.includes(entry.id)}
                  onCheckedChange={() => onToggle(entry.id)}
                />
                <span className="text-sm">{entry.label}</span>
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
