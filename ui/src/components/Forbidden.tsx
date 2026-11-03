import { cn } from "cn";

interface ForbiddenProps {
  /** Translated reason the page is closed to this user. */
  message: string;
  testid?: string;
  className?: string;
}

/** The 403 an admin page shows while it redirects the caller away. */
export function Forbidden({ message, testid, className }: ForbiddenProps) {
  return (
    <div
      data-testid={testid}
      className={cn("max-w-4xl mx-auto space-y-6 text-center py-12", className)}
    >
      <h1 className="text-6xl font-bold text-destructive">403</h1>
      <p className="text-xl text-muted-foreground">{message}</p>
    </div>
  );
}
