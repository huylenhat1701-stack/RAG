"use client";

import { useEffect, useState, useRef } from "react";
import { api, getKnowledgeGraph } from "@/lib/api";
import { 
  Graph, 
  Sparkle, 
  X, 
  Brain,
  Info,
  BookOpen
} from "@phosphor-icons/react";
import Link from "next/link";

interface KGNode {
  id: string;
  label: string;
  preview: string;
  probability: number;
  quiz_attempts: number;
  // Simulation fields
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
}

interface KGEdge {
  source: string;
  target: string;
  weight: number;
}

interface GraphData {
  nodes: KGNode[];
  edges: KGEdge[];
  total_nodes: number;
  avg_probability: number;
}

export default function KnowledgeGraphPage() {
  const [documents, setDocuments] = useState<any[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<number | "">("");
  const [loading, setLoading] = useState<boolean>(false);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  
  // Physics simulation state
  const [simulationNodes, setSimulationNodes] = useState<KGNode[]>([]);
  const [hoveredNode, setHoveredNode] = useState<KGNode | null>(null);
  const [selectedNode, setSelectedNode] = useState<KGNode | null>(null);
  const [draggedNodeId, setDraggedNodeId] = useState<string | null>(null);

  const canvasWidth = 800;
  const canvasHeight = 550;

  useEffect(() => {
    const fetchDocs = async () => {
      const { data } = await api.get("/documents");
      if (data && data.documents) {
        const indexedDocs = data.documents.filter((d: any) => d.status === "INDEXED");
        setDocuments(indexedDocs);
        if (indexedDocs.length > 0) {
          setSelectedDocId(indexedDocs[0].id);
        }
      }
    };
    fetchDocs();
  }, []);

  const handleFetchGraph = async () => {
    if (!selectedDocId) return;
    setLoading(true);
    setSelectedNode(null);
    try {
      const response = await getKnowledgeGraph(Number(selectedDocId));
      if (response && response.data) {
        setGraphData(response.data);
      }
    } catch (err) {
      console.error("Lỗi lấy dữ liệu đồ thị:", err);
    } finally {
      setLoading(false);
    }
  };

  // Run Physics Simulation
  useEffect(() => {
    if (!graphData || graphData.nodes.length === 0) {
      setSimulationNodes([]);
      return;
    }

    const center_x = canvasWidth / 2;
    const center_y = canvasHeight / 2;

    // Initialize positions in a circle layout with random offset
    const nodes: KGNode[] = graphData.nodes.map((node, idx) => {
      const angle = (idx / graphData.nodes.length) * 2 * Math.PI;
      const radius = 120 + Math.random() * 60;
      return {
        ...node,
        x: center_x + radius * Math.cos(angle),
        y: center_y + radius * Math.sin(angle),
        vx: 0,
        vy: 0
      };
    });

    const links = graphData.edges.map(e => ({ ...e }));

    let alpha = 1.0;
    const alphaDecay = 0.015;
    const k_repulsion = 180;
    const k_attraction = 0.06;
    const k_gravity = 0.04;

    let animId: number;

    const tick = () => {
      if (alpha < 0.01) {
        cancelAnimationFrame(animId);
        return;
      }

      // 1. Repulsion force between all nodes
      for (let i = 0; i < nodes.length; i++) {
        const nodeA = nodes[i];
        for (let j = i + 1; j < nodes.length; j++) {
          const nodeB = nodes[j];
          const dx = nodeB.x! - nodeA.x!;
          const dy = nodeB.y! - nodeA.y!;
          const distSq = dx * dx + dy * dy + 0.01;
          const dist = Math.sqrt(distSq);

          if (dist < 220) {
            const force = (k_repulsion / distSq) * alpha;
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;

            nodeA.vx! -= fx;
            nodeA.vy! -= fy;
            nodeB.vx! += fx;
            nodeB.vy! += fy;
          }
        }
      }

      // 2. Attraction force along edges
      for (const link of links) {
        const sourceNode = nodes.find(n => n.id === link.source);
        const targetNode = nodes.find(n => n.id === link.target);

        if (sourceNode && targetNode) {
          const dx = targetNode.x! - sourceNode.x!;
          const dy = targetNode.y! - sourceNode.y!;
          const dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
          
          // Pull connected nodes together, target distance 100px
          const force = k_attraction * (dist - 100) * alpha * link.weight;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;

          sourceNode.vx! += fx;
          sourceNode.vy! += fy;
          targetNode.vx! -= fx;
          targetNode.vy! -= fy;
        }
      }

      // 3. Center gravity & update positions
      for (const node of nodes) {
        node.vx! += (center_x - node.x!) * k_gravity * alpha;
        node.vy! += (center_y - node.y!) * k_gravity * alpha;

        // Apply friction
        node.vx! *= 0.85;
        node.vy! *= 0.85;

        // Update positions
        node.x! += node.vx!;
        node.y! += node.vy!;
      }

      setSimulationNodes([...nodes]);
      alpha -= alphaDecay;
      animId = requestAnimationFrame(tick);
    };

    animId = requestAnimationFrame(tick);

    return () => cancelAnimationFrame(animId);
  }, [graphData]);

  // Dragging support
  const handleMouseDown = (e: React.MouseEvent, nodeId: string) => {
    e.stopPropagation();
    setDraggedNodeId(nodeId);
  };

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!draggedNodeId) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    setSimulationNodes(prev => prev.map(node => {
      if (node.id === draggedNodeId) {
        return { ...node, x, y, vx: 0, vy: 0 };
      }
      return node;
    }));
  };

  const handleMouseUp = () => {
    setDraggedNodeId(null);
  };

  // Node Color Helper
  const getNodeColor = (prob: number) => {
    if (prob < 50) return "fill-rose-500 stroke-rose-400";
    if (prob < 80) return "fill-amber-400 stroke-amber-300";
    return "fill-emerald-500 stroke-emerald-400";
  };

  return (
    <div className="flex-1 w-full max-w-6xl mx-auto px-4 py-8 md:py-16 pb-32">
      {/* BACKGROUND DECORATIONS */}
      <div className="mesh-glow-violet top-20 left-10" />
      <div className="mesh-glow-emerald bottom-20 right-10" />

      {/* HEADER */}
      <div className="flex items-center gap-3 mb-8 md:mb-12">
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-500 rounded-2xl">
          <Graph weight="fill" className="w-8 h-8" />
        </div>
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight">Bản đồ Tri thức</h1>
          <p className="text-muted text-sm mt-1">Liên kết ngữ nghĩa giữa các chương và mức độ hiểu bài</p>
        </div>
      </div>

      {/* MAIN CONTAINER */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
        {/* SIDE SELECTOR */}
        <div className="lg:col-span-1 double-bezel-outer">
          <div className="double-bezel-inner p-5 border border-border space-y-6">
            <h2 className="text-base font-bold flex items-center gap-2">
              <Sparkle className="w-4.5 h-4.5 text-emerald-500" /> Chọn tài liệu
            </h2>

            <div>
              {documents.length === 0 ? (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-xs text-red-400">
                  Chưa có tài liệu hoàn tất (INDEXED). Vui lòng upload trước.
                </div>
              ) : (
                <select
                  value={selectedDocId}
                  onChange={(e) => {
                    setSelectedDocId(Number(e.target.value));
                    setGraphData(null);
                  }}
                  className="w-full bg-background border border-border rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:border-emerald-500"
                >
                  {documents.map((doc) => (
                    <option key={doc.id} value={doc.id}>
                      {doc.file_name}
                    </option>
                  ))}
                </select>
              )}
            </div>

            <button
              onClick={handleFetchGraph}
              disabled={loading || documents.length === 0 || !selectedDocId}
              className="w-full flex items-center justify-center gap-2 py-3 bg-foreground text-background font-bold rounded-full transition-premium-fast hover:scale-[1.02] active:scale-[0.99] disabled:opacity-50"
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-background border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <Graph className="w-5 h-5" /> Tải bản đồ tri thức
                </>
              )}
            </button>

            {/* LEGEND */}
            <div className="border-t border-border pt-4 space-y-2.5 text-xs">
              <span className="font-bold text-muted uppercase tracking-wider block">Chú thích độ thấu hiểu</span>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-rose-500" />
                <span className="text-muted">Lỗ hổng cần ôn tập ({"< 50%"})</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-amber-400" />
                <span className="text-muted">Đang học luyện tập (50% - 79%)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-emerald-500" />
                <span className="text-muted">Đã thấu hiểu tốt ({"≥ 80%"})</span>
              </div>
              <div className="border-t border-border pt-3">
                <p className="text-[10px] text-muted leading-relaxed">
                  * Kích thước node đại diện cho số lần làm quiz liên quan. Node càng to chứng tỏ bạn đã làm bài nhiều lần cho chunk đó.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* GRAPH CANVAS & DRAWER PANEL */}
        <div className="lg:col-span-3 space-y-4">
          {graphData && (
            <div className="flex justify-between items-center bg-card border border-border px-5 py-3 rounded-2xl text-xs text-muted">
              <div>Tổng số phân đoạn hiển thị: <span className="font-bold text-foreground">{graphData.total_nodes} nodes</span></div>
              <div>Xác suất thấu hiểu trung bình: <span className="font-bold text-foreground">{graphData.avg_probability}%</span></div>
            </div>
          )}

          <div className="relative border border-border rounded-3xl bg-card overflow-hidden shadow-inner h-[550px]">
            {!graphData ? (
              <div className="absolute inset-0 flex flex-col items-center justify-center space-y-3">
                <Graph className="w-16 h-16 text-muted" />
                <h3 className="text-lg font-bold">Chưa tải dữ liệu đồ thị</h3>
                <p className="text-sm text-muted">Bấm nút "Tải bản đồ tri thức" ở cột bên trái.</p>
              </div>
            ) : (
              <>
                {/* SVG Graph Canvas */}
                <svg
                  width="100%"
                  height="100%"
                  viewBox={`0 0 ${canvasWidth} ${canvasHeight}`}
                  onMouseMove={handleMouseMove}
                  onMouseUp={handleMouseUp}
                  className="select-none cursor-grab active:cursor-grabbing w-full h-full"
                >
                  {/* Edges layer */}
                  <g>
                    {graphData.edges.map((edge, idx) => {
                      const sourceNode = simulationNodes.find(n => n.id === edge.source);
                      const targetNode = simulationNodes.find(n => n.id === edge.target);
                      if (!sourceNode || !targetNode) return null;
                      return (
                        <line
                          key={idx}
                          x1={sourceNode.x}
                          y1={sourceNode.y}
                          x2={targetNode.x}
                          y2={targetNode.y}
                          className="stroke-border"
                          strokeWidth={1 + edge.weight * 1.5}
                          style={{ opacity: 0.15 + edge.weight * 0.45 }}
                        />
                      );
                    })}
                  </g>

                  {/* Nodes layer */}
                  <g>
                    {simulationNodes.map((node) => {
                      const radius = 8 + Math.min(node.quiz_attempts, 8) * 1.5;
                      const isHovered = hoveredNode?.id === node.id;
                      const isSelected = selectedNode?.id === node.id;

                      return (
                        <g 
                          key={node.id} 
                          transform={`translate(${node.x}, ${node.y})`}
                          className="transition-transform duration-75"
                        >
                          <circle
                            r={radius}
                            onMouseDown={(e) => handleMouseDown(e, node.id)}
                            onMouseEnter={() => setHoveredNode(node)}
                            onMouseLeave={() => setHoveredNode(null)}
                            onClick={() => setSelectedNode(node)}
                            className={`cursor-pointer stroke-2 transition-all ${getNodeColor(node.probability)} ${
                              isHovered || isSelected ? "scale-125 stroke-foreground" : ""
                            }`}
                          />
                        </g>
                      );
                    })}
                  </g>
                </svg>

                {/* Hover Tooltip */}
                {hoveredNode && hoveredNode.x && hoveredNode.y && (
                  <div 
                    className="absolute bg-foreground text-background text-xs rounded-xl p-3 shadow-lg pointer-events-none z-20 space-y-1 w-52 border border-border border-opacity-10"
                    style={{ 
                      left: `${(hoveredNode.x / canvasWidth) * 100}%`, 
                      top: `${(hoveredNode.y / canvasHeight) * 100 - 15}%`,
                      transform: 'translate(-50%, -100%)'
                    }}
                  >
                    <div className="font-bold truncate">{hoveredNode.label}</div>
                    <div className="flex justify-between items-center text-[10px] opacity-75 mt-1 border-t border-background/10 pt-1">
                      <span>Độ hiểu: {hoveredNode.probability}%</span>
                      <span>Luyện tập: {hoveredNode.quiz_attempts} lần</span>
                    </div>
                  </div>
                )}

                {/* Detail Drawer (Right Sidebar) */}
                {selectedNode && (
                  <div className="absolute top-0 right-0 h-full w-80 bg-card border-l border-border shadow-2xl p-5 flex flex-col justify-between z-30 transition-all duration-300 transform translate-x-0">
                    <div className="space-y-4 overflow-y-auto flex-1 pr-1">
                      <div className="flex justify-between items-center">
                        <h4 className="text-xs font-bold uppercase tracking-wider text-muted flex items-center gap-1">
                          <Info className="w-4 h-4 text-emerald-500" /> Chi tiết phân đoạn
                        </h4>
                        <button
                          onClick={() => setSelectedNode(null)}
                          className="p-1 hover:bg-foreground/5 rounded-full text-muted hover:text-foreground transition"
                        >
                          <X className="w-5 h-5" />
                        </button>
                      </div>

                      <div className="p-3 bg-background rounded-2xl border border-border space-y-1">
                        <div className="text-[10px] text-muted uppercase font-bold">Xác suất hiểu bài (BKT)</div>
                        <div className="text-lg font-black text-foreground flex items-center gap-1.5">
                          <span className={`w-3.5 h-3.5 rounded-full ${
                            selectedNode.probability < 50 ? "bg-rose-500" :
                            selectedNode.probability < 80 ? "bg-amber-400" : "bg-emerald-500"
                          }`} />
                          {selectedNode.probability}%
                        </div>
                        <div className="text-[10px] text-muted pt-1">
                          Lần luyện tập: {selectedNode.quiz_attempts} lần
                        </div>
                      </div>

                      <div className="space-y-2">
                        <span className="text-[10px] font-bold text-muted uppercase tracking-wider">Nội dung đầy đủ</span>
                        <p className="text-sm text-muted leading-relaxed whitespace-pre-wrap select-text bg-background p-4 border border-border rounded-2xl h-80 overflow-y-auto">
                          {selectedNode.preview}
                        </p>
                      </div>
                    </div>

                    <div className="border-t border-border pt-4 mt-4">
                      <Link
                        href="/quiz"
                        className="w-full flex items-center justify-center gap-1.5 py-3 bg-emerald-500 hover:bg-emerald-600 text-black font-bold rounded-full transition-premium-fast shadow-md"
                      >
                        <Brain className="w-5 h-5" /> Ôn tập lỗ hổng kiến thức
                      </Link>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
