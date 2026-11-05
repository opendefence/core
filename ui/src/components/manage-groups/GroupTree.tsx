import { useTranslation } from "react-i18next";
import { cn } from "cn";
import type { GroupNode } from "@/api/groups";

interface GroupTreeProps {
  tree: GroupNode[];
  selectedId?: string;
  onSelect: (id: string) => void;
}

/** The whole hierarchy, always open. Deployments hold few groups. */
export function GroupTree({ tree, selectedId, onSelect }: GroupTreeProps) {
  const { t } = useTranslation();

  if (tree.length === 0) {
    return (
      <p
        className="text-sm text-muted-foreground"
        data-testid="group-tree-empty"
      >
        {t("manageGroups.noGroups")}
      </p>
    );
  }

  return (
    <div className="space-y-1" data-testid="group-tree">
      {tree.map((node) => (
        <Branch
          key={node.group.id}
          node={node}
          depth={0}
          selectedId={selectedId}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}

interface BranchProps {
  node: GroupNode;
  depth: number;
  selectedId?: string;
  onSelect: (id: string) => void;
}

function Branch({ node, depth, selectedId, onSelect }: BranchProps) {
  const { group, children } = node;
  const selected = group.id === selectedId;

  return (
    <>
      <button
        onClick={() => onSelect(group.id)}
        style={{ paddingLeft: `${depth * 16 + 12}px` }}
        className={cn(
          "w-full text-left pr-3 py-2 rounded-lg transition-colors hover:bg-accent/60",
          selected && "bg-accent font-medium",
        )}
        data-testid="group-tree-node"
        data-group-name={group.name}
        data-group-depth={depth}
        data-group-selected={selected ? "true" : "false"}
      >
        <span className="text-sm">{group.displayName}</span>
        <span className="block font-mono text-xs text-muted-foreground">
          {group.name}
        </span>
      </button>
      {children.map((child) => (
        <Branch
          key={child.group.id}
          node={child}
          depth={depth + 1}
          selectedId={selectedId}
          onSelect={onSelect}
        />
      ))}
    </>
  );
}
