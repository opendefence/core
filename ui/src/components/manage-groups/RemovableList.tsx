import { X } from "lucide-react";

export interface Entry {
  id: string;
  label: string;
  /** Where the entry comes from, when it is not held by the group itself. */
  note?: string;
  /** A fixed entry has no remove button. */
  fixed?: boolean;
}

interface RemovableListProps {
  entries: Entry[];
  empty: string;
  removeLabel: string;
  onRemove: (id: string) => void;
  disabled: boolean;
  testid: string;
}

/** The rows of one group relation: members, roles granted, or managers. */
export function RemovableList({
  entries,
  empty,
  removeLabel,
  onRemove,
  disabled,
  testid,
}: RemovableListProps) {
  if (entries.length === 0) {
    return (
      <p
        className="text-sm text-muted-foreground"
        data-testid={`${testid}-empty`}
      >
        {empty}
      </p>
    );
  }

  return (
    <div className="space-y-1" data-testid={testid}>
      {entries.map((entry) => (
        <div
          key={entry.id}
          className="flex items-center justify-between px-3 py-2 rounded-lg bg-accent/40"
          data-testid={`${testid}-entry`}
          data-entry-label={entry.label}
        >
          <span className="text-sm">
            {entry.label}
            {entry.note && (
              <span className="text-muted-foreground"> {entry.note}</span>
            )}
          </span>
          {!entry.fixed && (
            <button
              onClick={() => onRemove(entry.id)}
              disabled={disabled}
              className="text-muted-foreground hover:text-foreground disabled:opacity-50"
              aria-label={removeLabel}
              data-testid={`${testid}-remove`}
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
