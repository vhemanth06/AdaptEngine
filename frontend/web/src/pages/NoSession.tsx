import type { Ctx } from "../ctx";
import { Button, Card } from "../components/ui";

export default function NoSession({ go }: Pick<Ctx, "go">) {
  return (
    <Card>
      <p className="mb-3">No session yet.</p>
      <Button onClick={() => go("setup")}>Go to Setup</Button>
    </Card>
  );
}
