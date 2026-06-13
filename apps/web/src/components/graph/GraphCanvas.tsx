"use client";

import { useMemo } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

export interface GraphNode {
  id: string;
  label: string;
  type: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
  confidence: number;
}

interface GraphCanvasProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

const NODE_COLORS: Record<string, string> = {
  Service: "#7c3aed",
  API: "#10b981",
  Team: "#f59e0b",
  Person: "#38bdf8",
  Rule: "#f43f5e",
  Concept: "#94a3b8",
  Other: "#64748b",
};

const DEFAULT_NODE_COLOR = "#64748b";

function getNodeColor(type: string): string {
  return NODE_COLORS[type] ?? DEFAULT_NODE_COLOR;
}

/**
 * Lightweight algorithmic layout: group nodes by type, lay each group out
 * along its own horizontal "band" (row), with even spacing within the row.
 * No external layout dependency (dagre/elkjs) is required.
 */
function layoutNodes(nodes: GraphNode[]): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();

  const groups = new Map<string, GraphNode[]>();
  for (const node of nodes) {
    const group = groups.get(node.type) ?? [];
    group.push(node);
    groups.set(node.type, group);
  }

  const ROW_HEIGHT = 160;
  const COLUMN_WIDTH = 220;

  // Order groups by the known palette order first, then any extras.
  const knownOrder = Object.keys(NODE_COLORS);
  const groupTypes = Array.from(groups.keys()).sort((a, b) => {
    const ai = knownOrder.indexOf(a);
    const bi = knownOrder.indexOf(b);
    if (ai === -1 && bi === -1) return a.localeCompare(b);
    if (ai === -1) return 1;
    if (bi === -1) return -1;
    return ai - bi;
  });

  groupTypes.forEach((type, rowIndex) => {
    const group = groups.get(type)!;
    group.forEach((node, colIndex) => {
      positions.set(node.id, {
        x: colIndex * COLUMN_WIDTH,
        y: rowIndex * ROW_HEIGHT,
      });
    });
  });

  return positions;
}

function GraphCanvasInner({ nodes, edges }: GraphCanvasProps) {
  const flowNodes = useMemo<Node[]>(() => {
    const positions = layoutNodes(nodes);
    return nodes.map((node) => {
      const color = getNodeColor(node.type);
      const position = positions.get(node.id) ?? { x: 0, y: 0 };
      return {
        id: node.id,
        position,
        data: { label: node.label },
        style: {
          background: "#161b27",
          color: "#e2e8f0",
          border: `1px solid ${color}`,
          borderRadius: 8,
          padding: "6px 12px",
          fontSize: 12,
          boxShadow: `0 0 0 1px ${color}33`,
        },
      };
    });
  }, [nodes]);

  const flowEdges = useMemo<Edge[]>(() => {
    return edges.map((edge) => ({
      id: `${edge.source}-${edge.target}-${edge.type}`,
      source: edge.source,
      target: edge.target,
      label: edge.type,
      style: { stroke: "#475569" },
      labelStyle: { fill: "#94a3b8", fontSize: 10 },
      labelBgStyle: { fill: "#161b27", fillOpacity: 0.8 },
      animated: false,
    }));
  }, [edges]);

  if (nodes.length === 0) {
    return (
      <div className="bg-[#161b27] border border-slate-700 rounded-xl">
        <div className="h-64 flex items-center justify-center">
          <span className="text-slate-600 text-sm">No entities extracted yet</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="bg-[#161b27] border border-slate-700 rounded-xl h-[600px]">
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          fitView
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#374151" gap={24} />
          <Controls />
          <MiniMap
            style={{ background: "#0f1117" }}
            maskColor="rgba(15, 17, 23, 0.6)"
            nodeColor={(node) => {
              const original = nodes.find((n) => n.id === node.id);
              return original ? getNodeColor(original.type) : DEFAULT_NODE_COLOR;
            }}
          />
        </ReactFlow>
      </div>

      <div className="flex flex-wrap gap-4">
        {Object.entries(NODE_COLORS).map(([type, color]) => (
          <div key={type} className="flex items-center gap-2 text-slate-400 text-xs">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: color }}
            />
            <span>{type}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function GraphCanvas({ nodes, edges }: GraphCanvasProps) {
  return (
    <ReactFlowProvider>
      <GraphCanvasInner nodes={nodes} edges={edges} />
    </ReactFlowProvider>
  );
}
