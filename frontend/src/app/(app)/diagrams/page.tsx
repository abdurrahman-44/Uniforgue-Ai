"use client";

import { useCallback, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addEdge,
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { toast } from "sonner";
import {
  Code2,
  Download,
  Network,
  Plus,
  Redo2,
  Save,
  Trash2,
  Undo2,
} from "lucide-react";
import { apiDownloadBlob, apiFetch } from "@/lib/api";
import {
  Badge,
  Button,
  EmptyState,
  GlassCard,
  Input,
  Modal,
  PageHeader,
  Select,
  Textarea,
} from "@/components/ui/primitives";
import type { DiagramItem } from "@/types/api";

const DIAGRAM_TYPES = [
  { id: "flowchart", label: "Flowchart" },
  { id: "uml_class", label: "UML Class Diagram" },
  { id: "uml_sequence", label: "UML Sequence Diagram" },
  { id: "uml_use_case", label: "UML Use Case Diagram" },
  { id: "uml_activity", label: "UML Activity Diagram" },
  { id: "er", label: "ER Database Diagram" },
  { id: "dfd", label: "Data Flow Diagram (DFD)" },
  { id: "architecture", label: "System Architecture" },
  { id: "network", label: "Network Topology" },
  { id: "mind_map", label: "Mind Map" },
  { id: "concept_map", label: "Concept Map" },
  { id: "org_chart", label: "Organizational Chart" },
];

export default function DiagramStudioPage() {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newType, setNewType] = useState("flowchart");

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [mermaidCode, setMermaidCode] = useState("");
  const [plantumlCode, setPlantumlCode] = useState("");
  const [newNodeLabel, setNewNodeLabel] = useState("");
  const [newNodeColor, setNewNodeColor] = useState("#7C3AED");
  const [showCode, setShowCode] = useState(false);
  const [history, setHistory] = useState<{ nodes: Node[]; edges: Edge[] }[]>([]);
  const [redoStack, setRedoStack] = useState<{ nodes: Node[]; edges: Edge[] }[]>([]);

  const { data: listData } = useQuery({
    queryKey: ["diagrams"],
    queryFn: () => apiFetch<{ diagrams: DiagramItem[] }>("/diagrams"),
  });

  const activeId = selectedId || listData?.diagrams?.[0]?.id || null;

  const { data: detailData, refetch: refetchDetail } = useQuery({
    queryKey: ["diagram", activeId],
    queryFn: () => apiFetch<{ diagram: DiagramItem }>(`/diagrams/${activeId}`),
    enabled: Boolean(activeId),
  });

  useEffect(() => {
    const g = detailData?.diagram;
    if (!g) return;
    const styledNodes: Node[] = (g.nodes_json || []).map((n) => ({
      id: n.id,
      type: n.type || "default",
      position: n.position,
      data: n.data,
      style: {
        background: "#111936",
        color: "#f8fafc",
        border: `2px solid ${n.data?.color || "#7C3AED"}`,
        borderRadius: n.data?.shape === "rounded" ? 18 : 10,
        padding: 10,
        fontSize: 12,
        fontWeight: 600,
      },
    }));
    const styledEdges: Edge[] = (g.edges_json || []).map((e) => ({
      ...e,
      animated: true,
      style: { stroke: "#22D3EE", strokeWidth: 2 },
    }));
    setNodes(styledNodes);
    setEdges(styledEdges);
    setMermaidCode(g.mermaid_code || "");
    setPlantumlCode(g.plantuml_code || "");
    setHistory([]);
    setRedoStack([]);
  }, [detailData?.diagram?.id, detailData?.diagram?.updated_at, setNodes, setEdges]);

  const pushHistory = () => {
    setHistory((h) => [...h.slice(-19), { nodes, edges }]);
    setRedoStack([]);
  };

  const onConnect = useCallback(
    (params: Connection) => {
      pushHistory();
      setEdges((eds) =>
        addEdge(
          { ...params, animated: true, style: { stroke: "#22D3EE", strokeWidth: 2 } },
          eds
        )
      );
    },
    [edges, nodes, setEdges]
  );

  const handleUndo = () => {
    if (history.length === 0) return;
    const prev = history[history.length - 1];
    setRedoStack((r) => [...r, { nodes, edges }]);
    setNodes(prev.nodes);
    setEdges(prev.edges);
    setHistory((h) => h.slice(0, -1));
  };

  const handleRedo = () => {
    if (redoStack.length === 0) return;
    const next = redoStack[redoStack.length - 1];
    setHistory((h) => [...h, { nodes, edges }]);
    setNodes(next.nodes);
    setEdges(next.edges);
    setRedoStack((r) => r.slice(0, -1));
  };

  const addNode = () => {
    const label = newNodeLabel.trim() || `Node ${nodes.length + 1}`;
    pushHistory();
    const id = `n-${Date.now()}`;
    setNodes((nds) => [
      ...nds,
      {
        id,
        type: "default",
        position: { x: 100 + (nds.length % 4) * 180, y: 80 + Math.floor(nds.length / 4) * 110 },
        data: { label, color: newNodeColor, shape: "rect" },
        style: {
          background: "#111936",
          color: "#f8fafc",
          border: `2px solid ${newNodeColor}`,
          borderRadius: 10,
          padding: 10,
          fontSize: 12,
          fontWeight: 600,
        },
      },
    ]);
    setNewNodeLabel("");
  };

  const createDiagram = useMutation({
    mutationFn: () =>
      apiFetch<{ diagram: DiagramItem }>("/diagrams", {
        method: "POST",
        body: JSON.stringify({ title: newTitle, diagram_type: newType, engine: "reactflow" }),
      }),
    onSuccess: (res) => {
      toast.success("Editable diagram created");
      setSelectedId(res.diagram.id);
      setNewTitle("");
      setCreateOpen(false);
      qc.invalidateQueries({ queryKey: ["diagrams"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const saveDiagram = useMutation({
    mutationFn: () =>
      apiFetch(`/diagrams/${activeId}`, {
        method: "PATCH",
        body: JSON.stringify({
          nodes_json: nodes.map((n) => ({
            id: n.id,
            type: n.type || "default",
            position: n.position,
            data: n.data,
          })),
          edges_json: edges.map((e) => ({
            id: e.id,
            source: e.source,
            target: e.target,
            label: typeof e.label === "string" ? e.label : "",
          })),
          mermaid_code: mermaidCode,
          plantuml_code: plantumlCode,
        }),
      }),
    onSuccess: () => {
      toast.success("Diagram saved with full editable graph data");
      qc.invalidateQueries({ queryKey: ["diagrams"] });
      refetchDetail();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const importMermaid = useMutation({
    mutationFn: () =>
      apiFetch(`/diagrams/${activeId}/import-mermaid`, {
        method: "POST",
        body: JSON.stringify({ mermaid_code: mermaidCode }),
      }),
    onSuccess: () => {
      toast.success("Imported Mermaid graph into interactive React Flow canvas");
      refetchDetail();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Interactive Diagram Studio"
        subtitle="Create editable UML, ER, DFD, Flowchart, Network, Mind Map & System Architecture diagrams with React Flow + Mermaid/PlantUML."
        badge="Module H"
        actions={
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" /> New Diagram
          </Button>
        }
      />

      <div className="grid gap-6 lg:grid-cols-12">
        {/* Saved Diagrams */}
        <div className="space-y-2.5 lg:col-span-3">
          {(listData?.diagrams || []).length === 0 ? (
            <EmptyState
              icon={<Network className="h-6 w-6" />}
              title="No diagrams yet"
              description="Start from a UML, ER, Architecture, or Flowchart template."
              action={<Button size="sm" onClick={() => setCreateOpen(true)}>Create Diagram</Button>}
            />
          ) : (
            listData?.diagrams.map((g) => (
              <div
                key={g.id}
                onClick={() => setSelectedId(g.id)}
                className={`cursor-pointer rounded-xl border p-3.5 transition ${
                  activeId === g.id
                    ? "border-violet-500/60 bg-violet-600/15"
                    : "border-[var(--border-subtle)] bg-black/20 hover:border-violet-500/30"
                }`}
              >
                <p className="truncate text-sm font-semibold">{g.title}</p>
                <div className="mt-1 flex items-center justify-between text-[11px] text-[var(--text-muted)]">
                  <Badge tone="cyan">{g.diagram_type}</Badge>
                  <span>{g.node_count ?? 0} nodes</span>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Interactive React Flow Workspace */}
        <div className="lg:col-span-9">
          {!activeId ? (
            <GlassCard>
              <p className="text-sm text-[var(--text-muted)]">
                Create or select a diagram to edit nodes, connect edges, and export SVG/PNG/PDF.
              </p>
            </GlassCard>
          ) : (
            <GlassCard className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border-subtle)] pb-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Input
                    className="w-48"
                    placeholder="New node label..."
                    value={newNodeLabel}
                    onChange={(e) => setNewNodeLabel(e.target.value)}
                  />
                  <input
                    type="color"
                    aria-label="Node border color"
                    value={newNodeColor}
                    onChange={(e) => setNewNodeColor(e.target.value)}
                    className="h-9 w-9 cursor-pointer rounded-lg border border-[var(--border-subtle)] bg-transparent"
                  />
                  <Button size="sm" variant="secondary" onClick={addNode}>
                    <Plus className="h-3.5 w-3.5" /> Add Node
                  </Button>
                  <Button size="sm" variant="ghost" onClick={handleUndo} disabled={history.length === 0} title="Undo">
                    <Undo2 className="h-3.5 w-3.5" />
                  </Button>
                  <Button size="sm" variant="ghost" onClick={handleRedo} disabled={redoStack.length === 0} title="Redo">
                    <Redo2 className="h-3.5 w-3.5" />
                  </Button>
                </div>

                <div className="flex flex-wrap items-center gap-1.5">
                  <Button size="sm" variant="secondary" onClick={() => setShowCode((v) => !v)}>
                    <Code2 className="h-3.5 w-3.5" /> Mermaid / PlantUML
                  </Button>
                  <Button size="sm" loading={saveDiagram.isPending} onClick={() => saveDiagram.mutate()}>
                    <Save className="h-3.5 w-3.5" /> Save
                  </Button>
                  <Button
                    size="sm"
                    variant="cyan"
                    onClick={() => apiDownloadBlob(`/diagrams/${activeId}/export?format=svg`, "diagram.svg")}
                  >
                    <Download className="h-3.5 w-3.5" /> SVG
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => apiDownloadBlob(`/diagrams/${activeId}/export?format=png`, "diagram.png")}
                  >
                    PNG
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => apiDownloadBlob(`/diagrams/${activeId}/export?format=pdf`, "diagram.pdf")}
                  >
                    PDF
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    onClick={async () => {
                      await apiFetch(`/diagrams/${activeId}`, { method: "DELETE" });
                      setSelectedId(null);
                      qc.invalidateQueries({ queryKey: ["diagrams"] });
                      toast.success("Diagram deleted");
                    }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>

              <div className="h-[480px] w-full overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-[#060b1d]">
                <ReactFlow
                  nodes={nodes}
                  edges={edges}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  onConnect={onConnect}
                  fitView
                >
                  <Background color="#1e293b" gap={18} />
                  <Controls />
                  <MiniMap style={{ background: "#0a1024" }} nodeColor="#7c3aed" />
                </ReactFlow>
              </div>

              {showCode && (
                <div className="grid gap-4 sm:grid-cols-2 border-t border-[var(--border-subtle)] pt-4">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-cyan-300">Mermaid Source</span>
                      <Button size="sm" variant="secondary" loading={importMermaid.isPending} onClick={() => importMermaid.mutate()}>
                        Import Mermaid → Canvas
                      </Button>
                    </div>
                    <Textarea
                      rows={6}
                      className="font-mono text-xs"
                      value={mermaidCode}
                      onChange={(e) => setMermaidCode(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <span className="text-xs font-semibold text-violet-300">PlantUML Source</span>
                    <Textarea
                      rows={6}
                      className="font-mono text-xs"
                      value={plantumlCode}
                      onChange={(e) => setPlantumlCode(e.target.value)}
                    />
                  </div>
                </div>
              )}
            </GlassCard>
          )}
        </div>
      </div>

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="Create Editable Diagram">
        <div className="space-y-3">
          <Input placeholder="Diagram Title (e.g., Smart Bus ER Schema)" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} />
          <Select value={newType} onChange={(e) => setNewType(e.target.value)}>
            {DIAGRAM_TYPES.map((t) => (
              <option key={t.id} value={t.id}>
                {t.label}
              </option>
            ))}
          </Select>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button disabled={newTitle.trim().length < 2} loading={createDiagram.isPending} onClick={() => createDiagram.mutate()}>
              Create Diagram
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
