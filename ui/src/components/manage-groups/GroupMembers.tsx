import { Plus } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { Group, Member } from "@/api/groups";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { RemovableList, type Entry } from "./RemovableList";

/** A member of a group below this one, who is a member of this one as well. */
export interface FromBelow {
  member: Member;
  from: Group;
}

interface GroupMembersProps {
  members: Member[];
  fromBelow: FromBelow[];
  showEffective: boolean;
  onToggleEffective: (show: boolean) => void;
  onAdd: () => void;
  onRemove: (userId: string) => void;
  isChanging: boolean;
}

export function GroupMembers({
  members,
  fromBelow,
  showEffective,
  onToggleEffective,
  onAdd,
  onRemove,
  isChanging,
}: GroupMembersProps) {
  const { t } = useTranslation();

  const entries: Entry[] = members.map((member) => ({
    id: member.id,
    label: member.callsign,
  }));

  if (showEffective) {
    entries.push(
      ...fromBelow.map(({ member, from }): Entry => ({
        id: `${from.id}:${member.id}`,
        label: member.callsign,
        note: t("manageGroups.members.fromGroup", { group: from.displayName }),
        fixed: true,
      })),
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold">
          {t("manageGroups.members.title", { count: members.length })}
        </h3>
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          {t("manageGroups.members.showEffective")}
          <Switch
            checked={showEffective}
            onCheckedChange={onToggleEffective}
            data-testid="group-members-effective-toggle"
          />
        </label>
      </div>

      <RemovableList
        entries={entries}
        empty={t("manageGroups.members.none")}
        removeLabel={t("manageGroups.members.remove")}
        onRemove={onRemove}
        disabled={isChanging}
        testid="group-members"
      />

      <Button
        variant="outline"
        onClick={onAdd}
        disabled={isChanging}
        className="w-full"
        data-testid="group-add-member"
      >
        <Plus className="w-4 h-4 mr-2" />
        {t("manageGroups.members.add")}
      </Button>
    </div>
  );
}
