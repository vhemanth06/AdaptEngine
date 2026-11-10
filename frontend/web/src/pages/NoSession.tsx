import type { Ctx } from "../ctx";
import { Button, EmptyState } from "../components/ui";

export default function NoSession({ go }: Pick<Ctx, "go">) {
  return (
    <EmptyState title="No session yet" action={<Button onClick={() => go("setup")}>Go to Setup</Button>}>
      Start a session on the Setup screen; this screen then shows the engine's view of it.
    </EmptyState>
  );
}
