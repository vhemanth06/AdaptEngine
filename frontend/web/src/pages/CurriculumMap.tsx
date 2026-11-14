import { useMemo, useState } from "react";
import { Background, Controls, Handle, MiniMap, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import type { Ctx } from "../ctx";
import { Card, Chip, PBar, conceptStatus, planDays, type MapStatus } from "../components/ui";
import NoSession from "./NoSession";

const LEGEND: [string, string, string][] = [
  ["✓ Mastered (evidence)", "var(--mastered)", "p ≥ θ with enough responses (engine rule)"],
  ["↻ Remediation", "var(--remediation)", "engine flagged after a wrong answer below the remediation threshold"],
  ["▶ Unlocked (today)", "var(--progress)", "the engine scheduled it today"],
  ["🔒 Locked (later)", "var(--locked)", "scheduled later: prerequisites or time come first"],
  ["Not in plan", "var(--border-strong)", "not needed for the goal, or nothing left to do"],
];

type ConceptData = { id: string; description: string; status: MapStatus; p: number; goal: boolean; dim: boolean };

function Ring({ p, color }: { p: number; color: string }) {
  const r = 15,
    c = 2 * Math.PI * r;
  return (
    <svg width={38} height={38} viewBox="0 0 38 38" aria-hidden>
      <circle cx={19} cy={19} r={r} fill="none" stroke="var(--surface-3)" strokeWidth={4} />
      <circle cx={19} cy={19} r={r} fill="none" stroke={color} strokeWidth={4} strokeDasharray={`${p * c} ${c}`} transform="rotate(-90 19 19)" strokeLinecap="round" />
      <text x={19} y={23} textAnchor="middle" fontSize={10} fill="var(--text)" fontFamily="var(--font-mono)">
        {Math.round(p * 100)}
      </text>
    </svg>
  );
}

function ConceptNode({ data }: NodeProps<Node<ConceptData>>) {
  const { status } = data;
  const color = status.key === "none" ? "var(--border-strong)" : status.color;
  return (
    <div
      data-testid={`node-${data.id}`}
      data-status={status.key}
      className="flex w-[210px] items-center gap-2 rounded-[var(--radius-lg)] bg-[var(--surface)] px-3 py-2 text-[var(--text)] transition-opacity"
      style={{
        border: `${data.goal ? 3 : 1.5}px ${status.key === "locked" ? "dashed" : "solid"} ${color}`,
        background: status.key === "none" ? "var(--surface)" : `color-mix(in srgb, ${color} 10%, var(--surface))`,
        opacity: data.dim ? 0.35 : 1,
      }}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <Ring p={data.p} color={color} />
      <div className="min-w-0">
        <div className="text-sm font-semibold">
          {data.id} {data.goal && <span className="text-[var(--accent)]">· goal</span>}
        </div>
        <div className="truncate text-xs text-[var(--text-muted)]">{data.description}</div>
        <div className="text-xs font-medium" style={{ color: status.key === "none" ? "var(--text-faint)" : color }}>
          {status.label}
        </div>
      </div>
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </div>
  );
}
const nodeTypes = { concept: ConceptNode };

export default function CurriculumMap({ session, cur, go }: Ctx) {
  const [hover, setHover] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const { nodes, edges } = useMemo(() => {
    if (!session || !cur) return { nodes: [] as Node<ConceptData>[], edges: [] as Edge[] };
    const near = hover ? new Set([hover, ...(cur.concepts.find((c) => c.concept_id === hover)?.prerequisites ?? []), ...cur.concepts.filter((c) => c.prerequisites.includes(hover)).map((c) => c.concept_id)]) : null;
    const rowAt: Record<number, number> = {};
    const nodes: Node<ConceptData>[] = cur.concepts.map((c) => {
      const st = session.concepts.find((s) => s.concept_id === c.concept_id)!;
      const row = (rowAt[c.depth] = (rowAt[c.depth] ?? -1) + 1);
      return {
        id: c.concept_id,
        type: "concept",
        position: { x: c.depth * 270, y: row * 110 },
        draggable: false,
        data: {
          id: c.concept_id,
          description: c.description,
          status: conceptStatus(st, session, cur),
          p: st.p,
          goal: session.context.goal === c.concept_id,
          dim: !!near && !near.has(c.concept_id),
        },
      };
    });
    const edges: Edge[] = cur.concepts.flatMap((c) =>
      c.prerequisites.map((p) => {
        const on = hover === p || hover === c.concept_id;
        return {
          id: `${p}-${c.concept_id}`,
          source: p,
          target: c.concept_id,
          animated: on,
          style: { strokeWidth: on ? 2.5 : 1.5, stroke: on ? "var(--accent)" : "var(--border-strong)", opacity: hover && !on ? 0.3 : 1 },
        };
      }),
    );
    return { nodes, edges };
  }, [session, cur, hover]);

  if (!session) return <NoSession go={go} />;
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
      <Card title="Prerequisites flow left to right" testId="map" className="p-0">
        <div style={{ height: "calc(100vh - 260px)", minHeight: 480 }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            fitView
            nodesConnectable={false}
            onNodeMouseEnter={(_, n) => setHover(n.id)}
            onNodeMouseLeave={() => setHover(null)}
            onNodeClick={(_, n) => setSelected(n.id)}
            proOptions={{ hideAttribution: true }}
            colorMode={document.documentElement.dataset.theme === "dark" ? "dark" : "light"}
          >
            <Background gap={20} color="var(--border)" />
            <MiniMap pannable zoomable nodeColor={(n) => (n.data as ConceptData).status.color} maskColor="color-mix(in srgb, var(--bg) 70%, transparent)" />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
      </Card>
      <div className="space-y-4">
        {selected ? <ConceptDrawer id={selected} ctx={{ session, cur }} onClose={() => setSelected(null)} /> : null}
        <Card title="Legend">
          <ul className="space-y-3">
            {LEGEND.map(([label, color, why]) => (
              <li key={label} className="flex gap-3">
                <span className="mt-1 inline-block h-4 w-4 shrink-0 rounded-full border-2" style={{ borderColor: color, background: `color-mix(in srgb, ${color} 20%, transparent)` }} />
                <span>
                  <b>{label}</b>
                  <br />
                  <span className="text-sm text-[var(--text-muted)]">{why}</span>
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-sm text-[var(--text-faint)]">Hover a concept to highlight its prerequisite edges; click it for details.</p>
        </Card>
      </div>
    </div>
  );
}

function ConceptDrawer({ id, ctx, onClose }: { id: string; ctx: Pick<Ctx, "session" | "cur">; onClose: () => void }) {
  const { session, cur } = ctx;
  if (!session || !cur) return null;
  const c = cur.concepts.find((x) => x.concept_id === id)!;
  const st = session.concepts.find((x) => x.concept_id === id)!;
  const status = conceptStatus(st, session, cur);
  const pre = c.prerequisites.map((p) => session.concepts.find((x) => x.concept_id === p)!);
  const firstDay = planDays(session.plan).find((d) => d.activities.some((a) => cur.activities.find((x) => x.activity_id === a)?.target_concept === id))?.day;
  const blocking = pre.filter((p) => !p.evidence_mastered);
  return (
    <Card title={`${c.concept_id} · ${c.description}`} actions={<button className="text-[var(--text-muted)]" onClick={onClose} aria-label="Close details">✕</button>} testId="concept-drawer">
      <div className="space-y-3">
        <Chip tone={status.key === "mastered" ? "mastered" : status.key === "remediation" ? "remediation" : status.key === "unlocked" ? "progress" : "locked"}>{status.label}</Chip>
        <PBar p={st.p} theta={session.theta} />
        <p className="text-sm text-[var(--text-muted)]">
          {st.responses} responses · {st.lessons_done} lessons done · {st.status}
        </p>
        <div>
          <h3 className="mb-1 font-medium">Why {status.key === "mastered" ? "it is done" : firstDay ? `it starts on day ${firstDay}` : "it is not scheduled"}</h3>
          {status.key === "mastered" ? (
            <p>p ≥ θ = {session.theta} with at least {session.k_responses} response{session.k_responses === 1 ? "" : "s"}.</p>
          ) : blocking.length ? (
            <p>Locked until its prerequisites are mastered: {blocking.map((b) => `${b.concept_id} (p ${b.p.toFixed(2)})`).join(", ")}.</p>
          ) : (
            <p>All prerequisites are mastered{firstDay ? "; the engine scheduled it." : "; it is not on the goal path or nothing is left to do."}</p>
          )}
        </div>
      </div>
    </Card>
  );
}
