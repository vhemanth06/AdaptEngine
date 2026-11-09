import { useMemo } from "react";
import { Background, Position, ReactFlow, type Edge, type Node } from "@xyflow/react";
import type { Ctx } from "../ctx";
import { C, Card, conceptStatus } from "../components/ui";
import NoSession from "./NoSession";

const LEGEND = [
  ["Mastered (evidence)", C.green, "p ≥ θ with enough responses (engine rule)"],
  ["Remediation", C.vermillion, "engine flagged after a wrong answer below the remediation threshold"],
  ["Unlocked (today)", C.blue, "the engine scheduled it today"],
  ["Locked (later)", C.grey, "scheduled later: prerequisites or time come first"],
  ["Not in plan", "#ffffff", "not needed for the goal, or nothing left to do"],
] as const;

export default function CurriculumMap({ session, cur, go }: Ctx) {
  const { nodes, edges } = useMemo(() => {
    if (!session || !cur) return { nodes: [] as Node[], edges: [] as Edge[] };
    const rowAt: Record<number, number> = {};
    const nodes: Node[] = cur.concepts.map((c) => {
      const st = session.concepts.find((s) => s.concept_id === c.concept_id)!;
      const status = conceptStatus(st, session, cur);
      const row = (rowAt[c.depth] = (rowAt[c.depth] ?? -1) + 1);
      const goal = session.context.goal === c.concept_id;
      return {
        id: c.concept_id,
        position: { x: c.depth * 250, y: row * 140 },
        draggable: false,
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        data: {
          label: (
            <div data-testid={`node-${c.concept_id}`} data-status={status.key}>
              <div className="font-bold">
                {c.concept_id} {goal && "(goal)"}
              </div>
              <div className="text-sm">{c.description}</div>
              <div className="mt-1 text-sm font-semibold">{status.label}</div>
              <div className="font-mono text-sm">p = {st.p.toFixed(2)}</div>
            </div>
          ),
        },
        style: {
          width: 200,
          border: `${goal ? 4 : 2}px ${status.key === "locked" ? "dashed" : "solid"} ${status.key === "none" ? "#475569" : status.color}`,
          background: status.key === "none" ? "#fff" : `${status.color}22`,
          borderRadius: 12,
          fontSize: 16,
        },
      };
    });
    const edges: Edge[] = cur.concepts.flatMap((c) =>
      c.prerequisites.map((p) => ({ id: `${p}-${c.concept_id}`, source: p, target: c.concept_id, style: { strokeWidth: 2 } })),
    );
    return { nodes, edges };
  }, [session, cur]);

  if (!session) return <NoSession go={go} />;
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <Card title="Curriculum map (prerequisites flow left to right)" testId="map">
        <div style={{ height: 600 }}>
          <ReactFlow nodes={nodes} edges={edges} fitView nodesConnectable={false} proOptions={{ hideAttribution: true }}>
            <Background />
          </ReactFlow>
        </div>
      </Card>
      <Card title="Legend">
        <ul className="space-y-3">
          {LEGEND.map(([label, color, why]) => (
            <li key={label} className="flex gap-3">
              <span className="mt-1 inline-block h-5 w-5 shrink-0 rounded border-2 border-slate-700" style={{ background: color }} />
              <span>
                <b>{label}</b>
                <br />
                <span className="text-base text-slate-600">{why}</span>
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
