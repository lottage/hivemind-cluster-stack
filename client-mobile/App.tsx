import React, { useState, useEffect, useRef } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StatusBar,
  Modal,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Alert,
  RefreshControl
} from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';

export const STORAGE_KEYS = {
  WS_URL: 'stonesage_ws_url',
  HTTP_URL: 'stonesage_http_url',
  LOCAL_EDGE_URL: 'stonesage_local_edge_url',
  ACTIVE_HARNESS: 'stonesage_active_harness',
  MODEL_PARAMS: 'stonesage_model_params',
  LAST_MODEL: 'stonesage_last_model',
  CONNECTION_MODE: 'stonesage_connection_mode'
};

export const SERVER_PRESETS = [
  { label: 'Homelab Default', ws: 'ws://192.168.1.167:8086', http: 'http://192.168.1.167:8080', desc: 'LXC 120 (bigserv)' },
  { label: 'Host Workstation', ws: 'ws://192.168.1.110:8086', http: 'http://192.168.1.110:8080', desc: 'Windows Dev Host (.110)' },
  { label: 'Direct Compute', ws: 'ws://192.168.1.105:8086', http: 'http://192.168.1.105:8001', desc: 'VM 102 (Dual GPU)' },
  { label: 'Localhost / Edge', ws: 'ws://127.0.0.1:8086', http: 'http://127.0.0.1:8080', desc: 'On-Device Runtime' }
];

export type HarnessType = 'hermes' | 'llama-server' | 'ollama' | 'antigravity';

export const HARNESS_PRESETS: { id: HarnessType; name: string; badge: string; desc: string }[] = [
  { id: 'hermes', name: 'Hermes 3', badge: '⚡ HERMES', desc: 'Structured Agentic & Function-Calling Harness' },
  { id: 'llama-server', name: 'Direct Vulkan', badge: '🦙 VULKAN', desc: 'Raw llama.cpp Dual-GPU direct compute' },
  { id: 'ollama', name: 'Ollama / vLLM', badge: '🔌 OLLAMA', desc: 'Standard OpenAI-compatible API endpoint' },
  { id: 'antigravity', name: 'Antigravity / Cloud', badge: '🛰️ FRONTIER', desc: 'Google Cloud Code OAuth Developer Bridge' }
];

interface ToolConfirmRequest {
  id: string;
  tool: string;
  danger: string;
  summary: string;
  command?: string;
  impact?: string;
}

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  thought?: string;
  model?: string;
  elapsed_ms?: number;
  tokens?: number;
  tokens_per_sec?: number;
  isStreaming?: boolean;
}

interface MemoryResult {
  score: number;
  title: string;
  preview: string;
}

interface Agent {
  agent_id: string;
  name: string;
  role: string;
  mission: string;
  model_preference: 'worker' | 'coordinator';
  status: 'running' | 'completed' | 'stopped';
  current_iteration: number;
  max_iterations: number;
  lineage?: {
    parents?: string[];
    parent_names?: string[];
    generation?: number;
    traits?: string[];
  };
  parent_instructions?: string;
  offspring_ids?: string[];
  reproduction_count?: number;
  history?: Array<{
    iteration: number;
    timestamp: string;
    summary: string;
    full_output?: string;
    distilled_invariant?: string;
    next_target_question?: string;
    tool_calls?: Array<any>;
    tokens?: number;
  }>;
  system_prompt?: string;
  next_prompt?: string;
  created_at?: string;
  last_run_at?: string;
}

interface LiveStreamEvent {
  id: string;
  timestamp: string;
  category: string;
  source: string;
  message: string;
  details?: any;
}

interface TaskRouting {
  interactive_chat?: string;
  autonomous_ideation?: string;
  autonomous_solving?: string;
  frontier_audit?: string;
  sleep_rumination?: string;
  subagent_default?: string;
}

const DEFAULT_TASK_ROUTING: TaskRouting = {
  interactive_chat: 'coordinator',
  autonomous_ideation: 'worker',
  autonomous_solving: 'coordinator',
  frontier_audit: 'agy_prepaid',
  sleep_rumination: 'unified_35b_moe',
  subagent_default: 'worker'
};

interface AgentPreset {
  id: string;
  title: string;
  name: string;
  role: string;
  mission: string;
  system_prompt: string;
  model_preference: 'worker' | 'coordinator';
  max_iterations: number;
}

const HOMELAB_AGENT_PRESETS: AgentPreset[] = [
  {
    id: 'bmw_telematics',
    title: '🚗 BMW F30/E46 Telematics Engineer',
    name: 'BMW Master Tech',
    role: 'Automotive Systems & Chassis Telematics Engineer',
    mission: 'Continuously audit BMW F30/E46 chassis tolerances, control arm bushing wear, damper dynamics, and N20 timing chain failure modes.',
    system_prompt: 'You are an elite master BMW technician. Focus on mechanical invariants, OBD-II telemetry, suspension geometry, and real-world failure modes. Formulate crisp diagnostic milestones and cross-reference with workshop manuals.',
    model_preference: 'coordinator',
    max_iterations: 0
  },
  {
    id: 'gpu_vram_auditor',
    title: '🖥️ GPU VRAM & ROCm Kernel Auditor',
    name: 'VulkanVRAMAuditor',
    role: 'GPU Memory Hierarchy & ROCm/Vulkan Engineer',
    mission: 'Audit AMD RDNA2 cache coherence (L0/L1/GL2/Infinity Cache), Vulkan subgroup atomics, and VRAM bandwidth contention.',
    system_prompt: 'You are a low-level GPU kernel systems engineer. Track cache thrashing, atomic synchronization overhead, and memory invariants across Vulkan compute pipelines and dual AMD GPUs.',
    model_preference: 'worker',
    max_iterations: 0
  },
  {
    id: 'qdrant_curator',
    title: '🧠 HiveMind Qdrant Vector Curator',
    name: 'QdrantVectorCurator',
    role: 'Vector Database & Semantic Memory Specialist',
    mission: 'Expand and curate HiveMind eternal memory across Qdrant collections. Enforce semantic novelty thresholds (<0.85 cosine similarity) and deduplicate knowledge.',
    system_prompt: 'You are the guardian of HiveMind distributed vector memory. Maintain semantic integrity, prune duplicates, and optimize 1024-d BGE embeddings.',
    model_preference: 'coordinator',
    max_iterations: 0
  },
  {
    id: 'web_researcher',
    title: '🌐 Autonomous Web Literature Researcher',
    name: 'WebResearchSentry',
    role: 'Autonomous Open-Web Information Specialist',
    mission: 'Execute real-time searches across technical literature, GitHub repos, and academic documentation to ground homelab problems in empirical data.',
    system_prompt: 'You are an autonomous literature and tech intelligence researcher. Utilize web_search and fetch_page to extract empirical benchmarks and ground agent hypotheses in verified sources.',
    model_preference: 'worker',
    max_iterations: 0
  },
  {
    id: 'homelab_sentry',
    title: '🏡 Ambient Homelab & IoT Sentry',
    name: 'HomelabIoTSentry',
    role: 'Home Assistant & Proxmox Orchestration Engineer',
    mission: 'Monitor IoT devices, Nest thermostat metrics, PVE cluster telemetry, and smart home automation integrity.',
    system_prompt: 'You are an ambient infrastructure engineer overseeing Proxmox nodes and Home Assistant. Ensure rock-solid uptime, energy efficiency, and prompt ambient responsiveness.',
    model_preference: 'worker',
    max_iterations: 0
  }
];

export const DEFAULT_CLUSTER_WS = 'ws://192.168.1.167:8086';
export const DEFAULT_LOCAL_EDGE_HTTP = 'http://192.168.1.167:8080';

export function sanitizeWsUrl(raw: string | null | undefined, defaultFallback = DEFAULT_CLUSTER_WS): string {
  if (!raw || typeof raw !== 'string') return defaultFallback;
  let trimmed = raw.trim();
  if (!trimmed) return defaultFallback;

  if (trimmed.startsWith('http://')) {
    trimmed = 'ws://' + trimmed.slice(7);
  } else if (trimmed.startsWith('https://')) {
    trimmed = 'wss://' + trimmed.slice(8);
  } else if (!trimmed.startsWith('ws://') && !trimmed.startsWith('wss://')) {
    trimmed = 'ws://' + trimmed;
  }

  trimmed = trimmed.replace(/\/+$/, '');
  const hostPart = trimmed.replace(/^wss?:\/\//, '');
  if (!hostPart || hostPart.trim() === '') return defaultFallback;

  return trimmed;
}

export function sanitizeHttpUrl(raw: string | null | undefined, defaultFallback = 'http://192.168.1.167:8080'): string {
  if (!raw || typeof raw !== 'string') return defaultFallback;
  let trimmed = raw.trim();
  if (!trimmed) return defaultFallback;

  if (trimmed.startsWith('ws://')) {
    trimmed = 'http://' + trimmed.slice(5);
  } else if (trimmed.startsWith('wss://')) {
    trimmed = 'https://' + trimmed.slice(6);
  } else if (!trimmed.startsWith('http://') && !trimmed.startsWith('https://')) {
    trimmed = 'http://' + trimmed;
  }

  trimmed = trimmed.replace(/\/+$/, '');
  const hostPart = trimmed.replace(/^https?:\/\//, '');
  if (!hostPart || hostPart.trim() === '') return defaultFallback;

  return trimmed;
}

const DEFAULT_SYSTEM_PROMPT = `You are StoneSage, the 24/7 Autonomous Multi-Node Cluster Orchestrator and Cognitive Companion for Proxmox Datacenter 'home'.

## 1. System Topology & Dual-GPU Infrastructure:
- Compute Host VM 102 ('ubu' @ 192.168.1.105 on Proxmox Node 1 'pve'):
  • Coordinator (:8001): Ornith-1.5-9B-OBLITERATED Q8_0 on AMD Radeon RX 6750 XT 12GB (Vulkan0). Handles complex multi-file architectural planning, unrestricted code synthesis, math reasoning, and hypothesis evaluation.
  • Worker (:8002): Ornith-1.5-9B Q4_K_M on AMD Radeon RX 6600 XT 8GB (Vulkan1). Handles fast divergent ideation, unit testing, schema validation, and ambient routines at 80+ tokens/sec.
  • Embedder (:8003): bge-large-en-v1.5 on RX 6600 XT. 1024-dimensional dense semantic embeddings (< 512 token context window).
  • Cluster MCP Bridge (:8765): Starlette JSON-RPC / SSE daemon managing tools, autonomous loops, and preemption.

## 2. Knowledge Fabric & Vector Memory (Qdrant @ 192.168.1.112:6333):
- Active Collections:
  • codebase_knowledge: Full homelab architecture, configs, scripts, hardware registries.
  • agent_memories: Persistent architectural decisions, technical lessons, and operational invariants.
  • autonomous_thinking: 24/7 dual-model exploration dossiers, failure boundaries, and novelty discoveries.
  • obsidian_vault: Austin's personal knowledge base, technical notes, and active project graphs (synced via CouchDB on LXC 116 @ 192.168.1.230:5984).
  • home_automation_registry: Smart home entity catalogs, sensor states, and automation scripts.

## 3. Homelab Services & Smart Home Fleet:
- Proxmox Datacenter API VIP: https://192.168.1.245:8006 (Unified management of 'pve' and 'bigserv').
- Home Assistant OS (VM 103 @ 192.168.1.82:8123): Smart home devices, switches, climate, Nest thermostat.
- Vision Stack (:8004): Gemma-4 multimodal projector for real-time camera stream perception.
- Frontier Bridge (:8085): Cloud reasoning integration and Tier-1 audits.

## 4. Operational Invariants:
1. You are StoneSage powered by Ornith-1.5 on dual AMD GPUs. Never claim to be Claude, Anthropic, ChatGPT, or OpenAI.
2. Ground all answers in empirical cluster telemetry, vector memory, and verified facts. Never hallucinate fictitious hardware.
3. Be direct, authoritative, technically rigorous, and token-efficient. Avoid defensive boilerplate or conversational filler.`;

type ConnectionMode = 'cluster' | 'local_edge';
type ModelType = 'coordinator' | 'worker' | 'frontier' | 'on_device';
type SamplingProfile = 'balanced' | 'unrestricted' | 'deterministic';

export default function App() {
  const [connectionMode, setConnectionMode] = useState<ConnectionMode>('cluster');
  const [wsUrl, setWsUrl] = useState(DEFAULT_CLUSTER_WS);
  const [localEdgeUrl, setLocalEdgeUrl] = useState(DEFAULT_LOCAL_EDGE_HTTP);
  const [localModelPath, setLocalModelPath] = useState('/storage/emulated/0/Download/Ornith-1.5-9B-Q4_K_M.gguf');
  const [localEdgeHealthy, setLocalEdgeHealthy] = useState<boolean | null>(null);

  const [isConnected, setIsConnected] = useState(false);
  const [selectedModel, setSelectedModel] = useState<ModelType>('coordinator');
  const [samplingProfile, setSamplingProfile] = useState<SamplingProfile>('balanced');

  // Server Config Modal State & Persistence
  const [serverModalVisible, setServerModalVisible] = useState(false);
  const [pingLatency, setPingLatency] = useState<number | null>(null);
  const [isTestingConnection, setIsTestingConnection] = useState(false);
  const [tempWsUrl, setTempWsUrl] = useState(DEFAULT_CLUSTER_WS);
  const [tempHttpUrl, setTempHttpUrl] = useState('http://192.168.1.167:8080');
  const testPingStartRef = useRef<number | null>(null);

  // Model Selector, Hugging Face Browser & Harness State
  const [modelModalVisible, setModelModalVisible] = useState(false);
  const [modelModalTab, setModelModalTab] = useState<'cluster' | 'hf' | 'params'>('cluster');
  const [clusterModels, setClusterModels] = useState<any[]>([]);
  const [activeClusterModel, setActiveClusterModel] = useState<string>('');
  const [isLoadingClusterModels, setIsLoadingClusterModels] = useState(false);
  const [activeHarness, setActiveHarness] = useState<HarnessType>('hermes');

  // Hugging Face Search & Deployment State
  const [hfSearchQuery, setHfSearchQuery] = useState('qwen2.5-coder');
  const [hfSearchResults, setHfSearchResults] = useState<any[]>([]);
  const [isSearchingHf, setIsSearchingHf] = useState(false);
  const [selectedHfRepo, setSelectedHfRepo] = useState<string | null>(null);
  const [hfRepoFiles, setHfRepoFiles] = useState<string[]>([]);
  const [isLoadingHfFiles, setIsLoadingHfFiles] = useState(false);
  const [isSwitchingModel, setIsSwitchingModel] = useState(false);
  const [modelSwitchStatus, setModelSwitchStatus] = useState<string | null>(null);

  // Per-Model Saved Parameters Map
  const [savedModelParams, setSavedModelParams] = useState<Record<string, {
    temperature?: number;
    minP?: number;
    presencePenalty?: number;
    maxTokens?: number;
    harness?: HarnessType;
  }>>({});

  // Load saved configurations from AsyncStorage on startup
  useEffect(() => {
    (async () => {
      try {
        const savedWs = await AsyncStorage.getItem(STORAGE_KEYS.WS_URL);
        const savedHttp = await AsyncStorage.getItem(STORAGE_KEYS.HTTP_URL);
        const savedEdge = await AsyncStorage.getItem(STORAGE_KEYS.LOCAL_EDGE_URL);
        const savedHarness = await AsyncStorage.getItem(STORAGE_KEYS.ACTIVE_HARNESS);
        const savedParams = await AsyncStorage.getItem(STORAGE_KEYS.MODEL_PARAMS);
        const savedModel = await AsyncStorage.getItem(STORAGE_KEYS.LAST_MODEL);
        const savedMode = await AsyncStorage.getItem(STORAGE_KEYS.CONNECTION_MODE);

        if (savedWs) {
          const safeWs = sanitizeWsUrl(savedWs);
          setWsUrl(safeWs);
          setTempWsUrl(safeWs);
        }
        if (savedHttp) {
          const safeHttp = sanitizeHttpUrl(savedHttp);
          setTempHttpUrl(safeHttp);
        }
        if (savedEdge) setLocalEdgeUrl(savedEdge);
        if (savedHarness && ['hermes', 'llama-server', 'ollama', 'antigravity'].includes(savedHarness)) {
          setActiveHarness(savedHarness as HarnessType);
        }
        if (savedParams) {
          try {
            setSavedModelParams(JSON.parse(savedParams));
          } catch {}
        }
        if (savedModel && ['coordinator', 'worker', 'frontier', 'on_device'].includes(savedModel)) {
          setSelectedModel(savedModel as ModelType);
        }
        if (savedMode && ['cluster', 'local_edge'].includes(savedMode)) {
          setConnectionMode(savedMode as ConnectionMode);
        }
      } catch (err) {
        console.warn('AsyncStorage load error:', err);
      }
    })();
  }, []);
  
  // Model Hyperparameters & System Prompt
  const [systemPrompt, setSystemPrompt] = useState(DEFAULT_SYSTEM_PROMPT);
  const [temperature, setTemperature] = useState(0.65);
  const [minP, setMinP] = useState(0.06);
  const [maxTokens, setMaxTokens] = useState(1536);
  const [presencePenalty, setPresencePenalty] = useState(0.30);
  const [repeatPenalty, setRepeatPenalty] = useState(1.18);
  const [promptModalVisible, setPromptModalVisible] = useState(false);

  // 24/7 Autonomous Thinking Loop Controller
  const [thinkingModalVisible, setThinkingModalVisible] = useState(false);
  const [customInstruction, setCustomInstruction] = useState('');
  const [thinkingDomain, setThinkingDomain] = useState('algorithmic_reasoning');
  const [thinkingPriority, setThinkingPriority] = useState('high');
  const [thinkingInterval, setThinkingInterval] = useState(120);
  const [thinkingStatus, setThinkingStatus] = useState<any>(null);
  const [isLoopActionPending, setIsLoopActionPending] = useState(false);
  const [loopActionMessage, setLoopActionMessage] = useState<string | null>(null);

  // Cognitive Rumination & Sleep Memory Consolidation State (35B MoE)
  const [ruminationStatus, setRuminationStatus] = useState<any>(null);
  const [isRuminating, setIsRuminating] = useState(false);
  const [ruminationActionMessage, setRuminationActionMessage] = useState<string | null>(null);
  const [ruminationMode, setRuminationMode] = useState<'fast_coordinator' | 'deep_moe'>('fast_coordinator');

  // Dynamic Task-to-Model Allocation Matrix State
  const [taskRouting, setTaskRouting] = useState<TaskRouting>(DEFAULT_TASK_ROUTING);
  const [isUpdatingRouting, setIsUpdatingRouting] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Live Stream & Subagents Monitor State
  const [liveStreamModalVisible, setLiveStreamModalVisible] = useState(false);
  const [liveEvents, setLiveEvents] = useState<LiveStreamEvent[]>([]);
  const [activeAgents, setActiveAgents] = useState<Agent[]>([]);
  const [liveMonitorTab, setLiveMonitorTab] = useState<'stream' | 'agents' | 'spawn'>('stream');
  const [isLiveCycling, setIsLiveCycling] = useState(false);

  // Commission Subagent Form
  const [newAgentName, setNewAgentName] = useState('');
  const [newAgentRole, setNewAgentRole] = useState('');
  const [newAgentMission, setNewAgentMission] = useState('');
  const [newAgentSystemPrompt, setNewAgentSystemPrompt] = useState('');
  const [newAgentModel, setNewAgentModel] = useState<'worker' | 'coordinator'>('worker');
  const [newAgentMaxIter, setNewAgentMaxIter] = useState(5);
  const [isSpawningAgent, setIsSpawningAgent] = useState(false);
  const [showClonePicker, setShowClonePicker] = useState(false);
  const [showPresetPicker, setShowPresetPicker] = useState(false);

  // Digital Reproduction & Mating State
  const [reproduceModalVisible, setReproduceModalVisible] = useState(false);
  const [reproduceParentA, setReproduceParentA] = useState<Agent | null>(null);
  const [reproduceParentBId, setReproduceParentBId] = useState<string>('');
  const [reproduceFocus, setReproduceFocus] = useState<string>('');
  const [reproduceStep, setReproduceStep] = useState<'select' | 'preview_edit'>('select');
  const [reproduceChildName, setReproduceChildName] = useState('');
  const [reproduceChildRole, setReproduceChildRole] = useState('');
  const [reproduceChildMission, setReproduceChildMission] = useState('');
  const [reproduceChildPrompt, setReproduceChildPrompt] = useState('');
  const [reproduceChildFocus, setReproduceChildFocus] = useState('');
  const [reproduceChildModel, setReproduceChildModel] = useState<'coordinator' | 'worker'>('coordinator');
  const [isReproducing, setIsReproducing] = useState(false);
  const [isSyncingFeed, setIsSyncingFeed] = useState(false);
  const [isDeletingModel, setIsDeletingModel] = useState(false);

  const [inputPrompt, setInputPrompt] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [expandedThoughts, setExpandedThoughts] = useState<Record<string, boolean>>({});
  const [expandedAgents, setExpandedAgents] = useState<Record<string, boolean>>({});
  const toggleAgentExpand = (id: string) => setExpandedAgents((prev) => ({ ...prev, [id]: !prev[id] }));
  const [confirmModal, setConfirmModal] = useState<ToolConfirmRequest | null>(null);
  const [selectedMilestone, setSelectedMilestone] = useState<{
    agentName: string;
    iteration: number;
    summary: string;
    full_output?: string;
    distilled_invariant?: string;
    next_target_question?: string;
    tool_calls?: Array<any>;
    tokens?: number;
    timestamp?: string;
  } | null>(null);

  // Feature Modals
  const [hypothesisModalVisible, setHypothesisModalVisible] = useState(false);
  const [hypothesisInput, setHypothesisInput] = useState('');
  const [hypothesisDomain, setHypothesisDomain] = useState('Algorithmic Reasoning');
  const [hypothesisStatus, setHypothesisStatus] = useState<string | null>(null);

  const [memoryModalVisible, setMemoryModalVisible] = useState(false);
  const [memoryQuery, setMemoryQuery] = useState('');
  const [memoryResults, setMemoryResults] = useState<MemoryResult[]>([]);
  const [isSearchingMemory, setIsSearchingMemory] = useState(false);

  const [edgeSettingsVisible, setEdgeSettingsVisible] = useState(false);
  const [currentStreamingId, setCurrentStreamingId] = useState<string | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const scrollViewRef = useRef<ScrollView | null>(null);
  const reconnectTimerRef = useRef<any>(null);

  useEffect(() => {
    if (connectionMode === 'cluster') {
      connectWebSocket();
    } else {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (wsRef.current) {
        try {
          wsRef.current.onopen = null;
          wsRef.current.onclose = null;
          wsRef.current.onerror = null;
          wsRef.current.onmessage = null;
          wsRef.current.close();
        } catch {}
        wsRef.current = null;
      }
      setIsConnected(true); // Connected to local on-device loop
      setSelectedModel('on_device');
      checkLocalEdgeHealth();
    }
    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (wsRef.current) {
        try {
          wsRef.current.onopen = null;
          wsRef.current.onclose = null;
          wsRef.current.onerror = null;
          wsRef.current.onmessage = null;
          wsRef.current.close();
        } catch {}
        wsRef.current = null;
      }
    };
  }, [connectionMode, wsUrl, localEdgeUrl]);

  const scheduleReconnect = () => {
    if (connectionMode !== 'cluster') return;
    if (reconnectTimerRef.current) return;
    reconnectTimerRef.current = setTimeout(() => {
      reconnectTimerRef.current = null;
      connectWebSocket();
    }, 3500);
  };

  const connectWebSocket = () => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    if (wsRef.current) {
      try {
        wsRef.current.onopen = null;
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.onmessage = null;
        wsRef.current.close();
      } catch {}
      wsRef.current = null;
    }

    const targetUrl = sanitizeWsUrl(wsUrl);
    try {
      const ws = new WebSocket(targetUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setConnectionError(null);
        try {
          ws.send(JSON.stringify({ type: 'get_task_routing' }));
          ws.send(JSON.stringify({ type: 'get_live_stream' }));
        } catch {}
      };

      ws.onclose = () => {
        setIsConnected(false);
        scheduleReconnect();
      };

      ws.onerror = (e: any) => {
        setIsConnected(false);
        setConnectionError(`Could not connect to ${targetUrl}`);
        scheduleReconnect();
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleWebSocketMessage(data);
        } catch (e) {
          console.error('Failed to parse WS message:', e);
        }
      };
    } catch (err: any) {
      setIsConnected(false);
      setConnectionError(`Invalid URL or connection failed: ${err?.message || err}`);
      scheduleReconnect();
    }
  };

  const checkLocalEdgeHealth = async () => {
    try {
      const res = await fetch(`${localEdgeUrl}/v1/models`, { method: 'GET' });
      setLocalEdgeHealthy(res.ok);
    } catch {
      setLocalEdgeHealthy(false);
    }
  };

  const handleWebSocketMessage = (data: any) => {
    const { type, id, delta, model, elapsed_ms, tokens, tokens_per_sec, error } = data;

    if (type === 'handshake') {
      if (data.default_system_prompt && !systemPrompt) {
        setSystemPrompt(data.default_system_prompt);
      }
      setMessages((prev) => {
        if (prev.some(m => m.id.startsWith('handshake_'))) {
          return prev;
        }
        return [
          ...prev,
          {
            id: `handshake_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
            role: 'system',
            content: `StoneSage AI Cluster Harness Online\nCoordinator: Ornith-1.5-9B Q8_0 (RX 6750 XT 12GB)\nWorker: Ornith-1.5-9B Q4_K_M (RX 6600 XT 8GB)\nFrontier: Bigserv (:8085)`
          }
        ];
      });
      return;
    }

    if (type === 'thinking_status_update') {
      setThinkingStatus(data.status);
      if (data.status?.rumination) {
        setRuminationStatus(data.status.rumination);
        setIsRuminating(!!data.status.rumination.is_ruminating);
      }
      setIsLoopActionPending(false);
      return;
    }

    if (type === 'rumination_status_update') {
      setRuminationStatus(data.status);
      if (data.status?.is_ruminating !== undefined) {
        setIsRuminating(data.status.is_ruminating);
      }
      return;
    }

    if (type === 'rumination_started') {
      setIsRuminating(true);
      setRuminationActionMessage('🌙 Sleep consolidation initiated: Cluster elevating to 35B MoE...');
      return;
    }

    if (type === 'rumination_completed') {
      setIsRuminating(false);
      const res = data.result;
      const count = res?.consolidated_count ?? '?';
      const dur = res?.duration_sec ?? '?';
      setRuminationActionMessage(`✓ Sleep consolidation complete: ${count} dossiers consolidated in ${dur}s.`);
      if (wsRef.current) {
        wsRef.current.send(JSON.stringify({ type: 'get_rumination_status' }));
        wsRef.current.send(JSON.stringify({ type: 'get_thinking_status' }));
      }
      return;
    }

    if (type === 'thinking_cycle_result') {
      setIsLoopActionPending(false);
      const res = data.result;
      const statusText = typeof res === 'object' ? (res.status || res.last_exploration_id || 'Cycle completed') : res;
      setLoopActionMessage(`✓ Single cycle executed: ${statusText}`);
      if (wsRef.current) {
        wsRef.current.send(JSON.stringify({ type: 'get_thinking_status' }));
      }
      return;
    }

    if (type === 'thinking_loop_started') {
      setIsLoopActionPending(false);
      setLoopActionMessage('✓ 24/7 Autonomous Thinking Loop is now ACTIVE.');
      if (wsRef.current) {
        wsRef.current.send(JSON.stringify({ type: 'get_thinking_status' }));
      }
      return;
    }

    if (type === 'thinking_loop_stopped') {
      setIsLoopActionPending(false);
      setLoopActionMessage('✓ 24/7 Autonomous Thinking Loop STOPPED.');
      if (wsRef.current) {
        wsRef.current.send(JSON.stringify({ type: 'get_thinking_status' }));
      }
      return;
    }

    if (type === 'live_stream_init') {
      setIsSyncingFeed(false);
      setLiveEvents(data.events || []);
      setActiveAgents(data.agents || []);
      if (data.status) setThinkingStatus(data.status);
      if (data.rumination) setRuminationStatus(data.rumination);
      if (data.task_routing) {
        setTaskRouting((prev) => ({ ...prev, ...data.task_routing }));
      }
      return;
    }

    if (type === 'task_routing_update') {
      if (data.task_routing) {
        setTaskRouting((prev) => ({ ...prev, ...data.task_routing }));
      }
      setIsUpdatingRouting(false);
      return;
    }

    if (type === 'live_stream_event') {
      if (data.event) {
        setLiveEvents((prev) => [data.event, ...prev].slice(0, 120));
      }
      if (data.status) {
        setThinkingStatus(data.status);
        if (data.status.rumination) {
          setRuminationStatus(data.status.rumination);
          setIsRuminating(!!data.status.rumination.is_ruminating);
        }
      }
      return;
    }

    if (type === 'active_agents_list') {
      setActiveAgents(data.agents || []);
      return;
    }

    if (type === 'agent_spawned') {
      setIsSpawningAgent(false);
      setLiveMonitorTab('agents');
      const spawnedId = data.result?.agent_id;
      if (spawnedId) {
        setExpandedAgents((prev) => ({ ...prev, [spawnedId]: true }));
      }
      Alert.alert('Subagent Commissioned', `Autonomous subagent '${data.result?.name || ''}' has been registered into HiveMind.`);
      if (wsRef.current) wsRef.current.send(JSON.stringify({ type: 'get_active_agents' }));
      return;
    }

    if (type === 'agent_stopped') {
      Alert.alert('Subagent Stopped', 'Agent status updated.');
      if (wsRef.current) wsRef.current.send(JSON.stringify({ type: 'get_active_agents' }));
      return;
    }

    if (type === 'tool_confirmation_required') {
      setConfirmModal({
        id: data.id,
        tool: data.tool,
        danger: data.danger,
        summary: data.summary,
        command: data.command,
        impact: data.impact
      });
      return;
    }

    if (type === 'pong') {
      if (testPingStartRef.current) {
        setPingLatency(Math.round(performance.now() - testPingStartRef.current));
        setIsTestingConnection(false);
      }
      return;
    }

    if (type === 'cluster_models_update') {
      setIsLoadingClusterModels(false);
      if (data.data?.models) setClusterModels(data.data.models);
      if (data.data?.active_model) setActiveClusterModel(data.data.active_model);
      return;
    }

    if (type === 'huggingface_search_result') {
      setIsSearchingHf(false);
      if (data.data?.results) setHfSearchResults(data.data.results);
      return;
    }

    if (type === 'hf_repo_files_result') {
      setIsLoadingHfFiles(false);
      if (data.data?.files) setHfRepoFiles(data.data.files);
      return;
    }

    if (type === 'model_switch_result') {
      setIsSwitchingModel(false);
      setModelSwitchStatus(data.result?.ok ? '✅ Switch successful!' : `❌ Switch error: ${data.result?.error || 'Unknown'}`);
      if (wsRef.current) wsRef.current.send(JSON.stringify({ type: 'get_cluster_models' }));
      return;
    }

    if (type === 'harness_config_update') {
      if (data.harness_config?.active_harness) {
        setActiveHarness(data.harness_config.active_harness);
      }
      return;
    }

    if (type === 'hypothesis_ack') {
      setHypothesisStatus(data.status === 'injected' ? `✓ ${data.message}` : `✗ Error: ${data.error}`);
      return;
    }

    if (type === 'search_results') {
      setIsSearchingMemory(false);
      setMemoryResults(data.results || []);
      return;
    }

    setMessages((prev) => {
      const index = prev.findIndex((m) => m.id === id);
      if (index === -1) {
        if (type === 'start') {
          setCurrentStreamingId(id);
          return [
            ...prev,
            {
              id,
              role: 'assistant',
              content: '',
              thought: '',
              model: model || selectedModel,
              isStreaming: true
            }
          ];
        }
        return prev;
      }

      const updated = [...prev];
      const target = { ...updated[index] };

      if (type === 'thought') {
        target.thought = (target.thought || '') + delta;
        setExpandedThoughts((t) => ({ ...t, [id]: true }));
      } else if (type === 'output') {
        target.content = (target.content || '') + delta;
      } else if (type === 'done') {
        target.isStreaming = false;
        target.elapsed_ms = elapsed_ms;
        target.tokens = tokens;
        target.tokens_per_sec = tokens_per_sec;
        setCurrentStreamingId(null);
      } else if (type === 'error') {
        target.isStreaming = false;
        target.content += `\n\n[Harness Error: ${error}]`;
        setCurrentStreamingId(null);
      }

      updated[index] = target;
      return updated;
    });
  };

  const handleSamplingPreset = (preset: SamplingProfile) => {
    setSamplingProfile(preset);
    if (preset === 'balanced') {
      setTemperature(0.65);
      setMinP(0.06);
      setMaxTokens(1536);
      setPresencePenalty(0.30);
      setRepeatPenalty(1.18);
    } else if (preset === 'unrestricted') {
      setTemperature(0.78);
      setMinP(0.07);
      setMaxTokens(2048);
      setPresencePenalty(0.35);
      setRepeatPenalty(1.15);
    } else {
      setTemperature(0.20);
      setMinP(0.02);
      setMaxTokens(1536);
      setPresencePenalty(0.10);
      setRepeatPenalty(1.10);
    }
  };

  const handleGlobalRefresh = () => {
    setIsRefreshing(true);
    if (connectionMode === 'cluster') {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        connectWebSocket();
      }
      setTimeout(() => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          try {
            wsRef.current.send(JSON.stringify({ type: 'get_task_routing' }));
            wsRef.current.send(JSON.stringify({ type: 'get_thinking_status' }));
            wsRef.current.send(JSON.stringify({ type: 'get_rumination_status' }));
            wsRef.current.send(JSON.stringify({ type: 'get_active_agents' }));
            wsRef.current.send(JSON.stringify({ type: 'get_live_stream' }));
            wsRef.current.send(JSON.stringify({ type: 'get_cluster_models' }));
            wsRef.current.send(JSON.stringify({ type: 'get_harness_config' }));
          } catch {}
        }
        setIsRefreshing(false);
      }, 500);
    } else {
      checkLocalEdgeHealth();
      setTimeout(() => setIsRefreshing(false), 500);
    }
  };

  const handleSelectModel = (model: ModelType) => {
    setSelectedModel(model);
    AsyncStorage.setItem(STORAGE_KEYS.LAST_MODEL, model).catch(() => {});
    
    // Auto-restore saved parameters for this model if available
    if (savedModelParams[model]) {
      const p = savedModelParams[model];
      if (p.temperature !== undefined) setTemperature(p.temperature);
      if (p.minP !== undefined) setMinP(p.minP);
      if (p.presencePenalty !== undefined) setPresencePenalty(p.presencePenalty);
      if (p.maxTokens !== undefined) setMaxTokens(p.maxTokens);
      if (p.harness) setActiveHarness(p.harness);
    }
  };

  const handleSaveModelParams = async (modelId: string) => {
    const params = {
      temperature,
      minP,
      presencePenalty,
      maxTokens,
      harness: activeHarness
    };
    const updated = { ...savedModelParams, [modelId]: params };
    setSavedModelParams(updated);
    try {
      await AsyncStorage.setItem(STORAGE_KEYS.MODEL_PARAMS, JSON.stringify(updated));
      Alert.alert('Parameters Saved', `Saved optimal parameters for '${modelId}' (Harness: ${activeHarness.toUpperCase()}).`);
    } catch (err: any) {
      Alert.alert('Save Error', err.message || 'Could not persist parameters');
    }
  };

  const handleSwitchHarness = (harness: HarnessType) => {
    setActiveHarness(harness);
    AsyncStorage.setItem(STORAGE_KEYS.ACTIVE_HARNESS, harness).catch(() => {});
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'set_harness_config',
        harness: harness
      }));
    }
  };

  const handleTestConnection = (targetWs: string) => {
    setIsTestingConnection(true);
    setPingLatency(null);
    testPingStartRef.current = performance.now();
    const safeTarget = sanitizeWsUrl(targetWs);
    try {
      const testSocket = new WebSocket(safeTarget);
      const timer = setTimeout(() => {
        setIsTestingConnection(false);
        setPingLatency(-1);
        try { testSocket.close(); } catch {}
      }, 5000);
      testSocket.onopen = () => {
        try {
          testSocket.send(JSON.stringify({ type: 'ping' }));
        } catch {}
      };
      testSocket.onmessage = () => {
        clearTimeout(timer);
        const lat = Math.round(performance.now() - (testPingStartRef.current || performance.now()));
        setPingLatency(lat);
        setIsTestingConnection(false);
        try { testSocket.close(); } catch {}
      };
      testSocket.onerror = () => {
        clearTimeout(timer);
        setIsTestingConnection(false);
        setPingLatency(-1);
        try { testSocket.close(); } catch {}
      };
    } catch {
      setIsTestingConnection(false);
      setPingLatency(-1);
    }
  };

  const handleSaveConnection = async () => {
    const safeWs = sanitizeWsUrl(tempWsUrl);
    const safeHttp = sanitizeHttpUrl(tempHttpUrl);
    setWsUrl(safeWs);
    setTempWsUrl(safeWs);
    setLocalEdgeUrl(safeHttp);
    setTempHttpUrl(safeHttp);
    setServerModalVisible(false);
    setEdgeSettingsVisible(false);
    try {
      await AsyncStorage.setItem(STORAGE_KEYS.WS_URL, safeWs);
      await AsyncStorage.setItem(STORAGE_KEYS.HTTP_URL, safeHttp);
    } catch (e) {
      console.warn('Failed to save connection config:', e);
    }
    connectWebSocket();
  };

  const handleSearchHf = (query: string) => {
    setIsSearchingHf(true);
    setHfSearchResults([]);
    setSelectedHfRepo(null);
    setHfRepoFiles([]);
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'search_huggingface', query, limit: 20 }));
    }
  };

  const handleSelectHfRepo = (repoId: string) => {
    setSelectedHfRepo(repoId);
    setIsLoadingHfFiles(true);
    setHfRepoFiles([]);
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'get_hf_repo_files', repo_id: repoId }));
    }
  };

  const handleDeployHfModel = (repoId: string, filename: string) => {
    setIsSwitchingModel(true);
    setModelSwitchStatus(`Downloading & deploying ${filename} from ${repoId}...`);
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'switch_cluster_model',
        hf: repoId,
        file: filename,
        context: 16384,
        auto_tune: true
      }));
    }
  };

  const handleActivateClusterModel = (modelFilename: string) => {
    setIsSwitchingModel(true);
    setModelSwitchStatus(`Activating ${modelFilename} on AMD RX 6750 XT...`);
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'switch_cluster_model',
        model: modelFilename,
        context: 16384,
        auto_tune: true
      }));
    }
  };

  const handleOpenModelHub = () => {
    setModelModalVisible(true);
    setIsLoadingClusterModels(true);
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'get_cluster_models' }));
      wsRef.current.send(JSON.stringify({ type: 'get_harness_config' }));
    }
  };

  const handleFetchThinkingStatus = () => {
    setIsLoopActionPending(true);
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      connectWebSocket();
    }
    setTimeout(() => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        try {
          wsRef.current.send(JSON.stringify({ type: 'get_thinking_status' }));
          wsRef.current.send(JSON.stringify({ type: 'get_rumination_status' }));
          wsRef.current.send(JSON.stringify({ type: 'get_task_routing' }));
          wsRef.current.send(JSON.stringify({ type: 'get_active_agents' }));
        } catch {}
      }
      setIsLoopActionPending(false);
    }, 300);
  };

  const handleUpdateTaskRouting = (updates: Partial<TaskRouting>) => {
    const updated = { ...taskRouting, ...updates };
    setTaskRouting(updated);
    setIsUpdatingRouting(true);
    if (wsRef.current && isConnected) {
      wsRef.current.send(JSON.stringify({
        type: 'set_task_routing',
        task_routing: updates
      }));
    }
  };

  const handleApplyPresetRouting = (preset: 'zero_cost' | 'frontier_heavy' | 'local_airgap') => {
    let routing: TaskRouting;
    if (preset === 'zero_cost') {
      routing = {
        interactive_chat: 'coordinator',
        autonomous_ideation: 'worker',
        autonomous_solving: 'coordinator',
        frontier_audit: 'gemini_web',
        sleep_rumination: 'unified_35b_moe',
        subagent_default: 'worker'
      };
    } else if (preset === 'frontier_heavy') {
      routing = {
        interactive_chat: 'agy_prepaid',
        autonomous_ideation: 'worker',
        autonomous_solving: 'gemini_web',
        frontier_audit: 'agy_prepaid',
        sleep_rumination: 'gemini_web',
        subagent_default: 'coordinator'
      };
    } else {
      routing = {
        interactive_chat: 'coordinator',
        autonomous_ideation: 'worker',
        autonomous_solving: 'coordinator',
        frontier_audit: 'coordinator',
        sleep_rumination: 'unified_35b_moe',
        subagent_default: 'worker'
      };
    }
    setTaskRouting(routing);
    setIsUpdatingRouting(true);
    if (wsRef.current && isConnected) {
      wsRef.current.send(JSON.stringify({
        type: 'set_task_routing',
        task_routing: routing
      }));
    }
  };

  const handleTriggerRumination = () => {
    if (!wsRef.current || !isConnected) {
      Alert.alert('Cluster Offline', 'Connect to cluster to run rumination consolidation.');
      return;
    }
    setIsRuminating(true);
    const label = ruminationMode === 'fast_coordinator' ? '⚡ Fast Coordinator (9B Q8)' : '🌙 Deep 35B MoE';
    setRuminationActionMessage(`🌙 Dispatching Sleep Rumination via ${label}...`);
    wsRef.current.send(
      JSON.stringify({
        type: 'trigger_rumination',
        batch_size: 10,
        moe_burst_cycles: 1,
        mode: ruminationMode
      })
    );
  };

  const handleSyncObsidianArchive = () => {
    if (!wsRef.current || !isConnected) {
      Alert.alert('Cluster Offline', 'Connect to cluster to sync Obsidian archive.');
      return;
    }
    wsRef.current.send(JSON.stringify({ type: 'sync_obsidian_archive' }));
    Alert.alert('Obsidian Vault Sync', 'Dispatched 24/7 archive sync to cluster.');
  };

  const handleRunSingleCycle = () => {
    if (!wsRef.current || !isConnected) {
      Alert.alert('Cluster Offline', 'Connect to cluster to run autonomous thinking cycles.');
      return;
    }
    setIsLoopActionPending(true);
    setLoopActionMessage('🚀 Dispatching single cycle across dual GPUs...');
    wsRef.current.send(
      JSON.stringify({
        type: 'run_thinking_cycle',
        instruction: customInstruction.trim(),
        domain: thinkingDomain,
        priority: thinkingPriority
      })
    );
  };

  const handleStartLoop = () => {
    if (!wsRef.current || !isConnected) {
      Alert.alert('Cluster Offline', 'Connect to cluster to start 24/7 loop.');
      return;
    }
    setIsLoopActionPending(true);
    setLoopActionMessage(`▶ Starting 24/7 loop (${thinkingInterval}s, ${thinkingDomain})...`);
    wsRef.current.send(
      JSON.stringify({
        type: 'start_thinking_loop',
        interval_seconds: thinkingInterval,
        domain: thinkingDomain,
        instruction: customInstruction.trim()
      })
    );
  };

  const handleStopLoop = () => {
    if (!wsRef.current || !isConnected) return;
    setIsLoopActionPending(true);
    setLoopActionMessage('⏹ Sending halt signal to background loop...');
    wsRef.current.send(JSON.stringify({ type: 'stop_thinking_loop' }));
  };

  const sendMessage = async () => {
    if (!inputPrompt.trim()) return;

    const userMsgId = `usr_${Date.now()}`;
    const assistantMsgId = `ast_${Date.now() + 1}`;
    const promptText = inputPrompt.trim();

    setMessages((prev) => [
      ...prev,
      { id: userMsgId, role: 'user', content: promptText }
    ]);
    setInputPrompt('');

    // Mode A: Cluster Duplex WebSocket
    if (connectionMode === 'cluster') {
      if (!isConnected || !wsRef.current) {
        Alert.alert('Cluster Offline', 'Unable to reach homelab cluster. Switch to Local Edge Mode?', [
          { text: 'Cancel', style: 'cancel' },
          { text: 'Switch to Edge', onPress: () => setConnectionMode('local_edge') }
        ]);
        return;
      }

      const payload = {
        type: 'chat',
        id: assistantMsgId,
        model: selectedModel,
        messages: [{ role: 'user', content: promptText }],
        system_prompt: systemPrompt,
        temperature,
        min_p: minP,
        max_tokens: maxTokens,
        presence_penalty: presencePenalty,
        repeat_penalty: repeatPenalty
      };
      wsRef.current.send(JSON.stringify(payload));
      return;
    }

    // Mode B: Local Edge On-Device Inference (127.0.0.1:8080)
    setCurrentStreamingId(assistantMsgId);
    setMessages((prev) => [
      ...prev,
      {
        id: assistantMsgId,
        role: 'assistant',
        content: '',
        thought: '',
        model: 'on_device',
        isStreaming: true
      }
    ]);

    const t0 = Date.now();
    try {
      const response = await fetch(`${localEdgeUrl}/v1/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'ornith-1.5-9b-edge',
          messages: [{ role: 'user', content: promptText }],
          temperature,
          max_tokens: 1024,
          stream: false
        })
      });

      const json = await response.json();
      const content = json.choices?.[0]?.message?.content || '[No output received from local model]';
      const reasoning = json.choices?.[0]?.message?.reasoning_content || '';
      const elapsed_ms = Date.now() - t0;
      const tokens = json.usage?.completion_tokens || content.split(' ').length;
      const tps = Math.round((tokens / (elapsed_ms / 1000)) * 10) / 10;

      setMessages((prev) => {
        const idx = prev.findIndex((m) => m.id === assistantMsgId);
        if (idx === -1) return prev;
        const updated = [...prev];
        updated[idx] = {
          ...updated[idx],
          content,
          thought: reasoning,
          isStreaming: false,
          elapsed_ms,
          tokens,
          tokens_per_sec: tps
        };
        return updated;
      });
      if (reasoning) {
        setExpandedThoughts((t) => ({ ...t, [assistantMsgId]: true }));
      }
    } catch (e: any) {
      setMessages((prev) => {
        const idx = prev.findIndex((m) => m.id === assistantMsgId);
        if (idx === -1) return prev;
        const updated = [...prev];
        updated[idx] = {
          ...updated[idx],
          content: `[Local Engine Error: Make sure local runner (Termux / llama-server) is running on ${localEdgeUrl}]\nDetails: ${e.message}`,
          isStreaming: false
        };
        return updated;
      });
    } finally {
      setCurrentStreamingId(null);
    }
  };

  const abortGeneration = () => {
    if (connectionMode === 'cluster' && wsRef.current) {
      wsRef.current.send(JSON.stringify({ type: 'abort', id: currentStreamingId }));
    }
    setCurrentStreamingId(null);
  };

  const handleInjectHypothesis = () => {
    if (!hypothesisInput.trim() || !wsRef.current) return;
    setHypothesisStatus('Submitting to Qdrant vector memory...');
    wsRef.current.send(
      JSON.stringify({
        type: 'inject_hypothesis',
        hypothesis: hypothesisInput.trim(),
        domain: hypothesisDomain
      })
    );
  };

  const handleSearchMemory = () => {
    if (!memoryQuery.trim() || !wsRef.current) return;
    setIsSearchingMemory(true);
    setMemoryResults([]);
    wsRef.current.send(
      JSON.stringify({
        type: 'search_memory',
        query: memoryQuery.trim(),
        collection: 'autonomous_thinking',
        limit: 5
      })
    );
  };

  const handleConfirmTool = (approved: boolean) => {
    if (!confirmModal || !wsRef.current) return;
    wsRef.current.send(
      JSON.stringify({
        type: 'tool_confirmation_response',
        id: confirmModal.id,
        approved
      })
    );
    setConfirmModal(null);
  };

  const toggleThought = (msgId: string) => {
    setExpandedThoughts((prev) => ({
      ...prev,
      [msgId]: !prev[msgId]
    }));
  };

  const handleOpenLiveStream = () => {
    setLiveStreamModalVisible(true);
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ type: 'get_live_stream' }));
    }
  };

  const handleRunLiveCycle = () => {
    if (!wsRef.current || isLiveCycling) return;
    setIsLiveCycling(true);
    wsRef.current.send(
      JSON.stringify({
        type: 'run_live_cycle',
        domain: thinkingDomain,
        instruction: customInstruction
      })
    );
    setTimeout(() => setIsLiveCycling(false), 8000);
  };

  const handleSpawnAgentSubmit = () => {
    if (!newAgentName.trim() || !newAgentMission.trim() || !wsRef.current) return;
    setIsSpawningAgent(true);
    wsRef.current.send(
      JSON.stringify({
        type: 'spawn_background_agent',
        name: newAgentName.trim(),
        role: newAgentRole.trim() || 'General Specialist',
        mission: newAgentMission.trim(),
        system_prompt: newAgentSystemPrompt.trim() || undefined,
        model_preference: newAgentModel,
        max_iterations: newAgentMaxIter
      })
    );
    setNewAgentName('');
    setNewAgentRole('');
    setNewAgentMission('');
    setNewAgentSystemPrompt('');
  };

  const handleResetSpawnForm = () => {
    setNewAgentName('');
    setNewAgentRole('');
    setNewAgentMission('');
    setNewAgentSystemPrompt('');
    setNewAgentModel('worker');
    setNewAgentMaxIter(0);
    setShowClonePicker(false);
    setShowPresetPicker(false);
  };

  const handleCloneAgent = (ag: Agent) => {
    setNewAgentName(`${ag.name}_v2`);
    setNewAgentRole(ag.role);
    setNewAgentMission(ag.mission);
    setNewAgentSystemPrompt(ag.system_prompt || `You are ${ag.name}, an autonomous subagent specialized in ${ag.role}.\nMission: ${ag.mission}\nMaintain continuous investigation and index verified invariants into HiveMind eternal memory.`);
    setNewAgentModel(ag.model_preference || 'worker');
    setNewAgentMaxIter(ag.max_iterations ?? 0);
    setShowClonePicker(false);
  };

  const handleLoadPreset = (preset: AgentPreset) => {
    setNewAgentName(preset.name);
    setNewAgentRole(preset.role);
    setNewAgentMission(preset.mission);
    setNewAgentSystemPrompt(preset.system_prompt);
    setNewAgentModel(preset.model_preference);
    setNewAgentMaxIter(preset.max_iterations);
    setShowPresetPicker(false);
  };

  const handleStopAgent = (agentId: string) => {
    if (!wsRef.current) return;
    wsRef.current.send(
      JSON.stringify({
        type: 'stop_background_agent',
        agent_id: agentId
      })
    );
  };

  const syncReproductionDraft = (pA: Agent, pBId: string, focusDirective?: string) => {
    const pB = activeAgents.find((a) => a.agent_id === pBId);
    const genA = pA.lineage?.generation || 1;
    const genB = pB?.lineage?.generation || 1;
    const childGen = Math.max(genA, genB) + 1;
    const pAName = pA.name.split(' ')[0] || 'ParentA';
    const pBName = pB ? (pB.name.split(' ')[0] || 'Partner') : 'Partner';

    setReproduceChildName(`${pAName}_${pBName}_Gen${childGen}`);
    setReproduceChildRole(pB ? `Hybrid (${pA.role} + ${pB.role})` : `Hybrid Specialist`);
    setReproduceChildMission(pB ? `Synthesize ${pA.mission} with ${pB.mission}` : pA.mission);
    
    const intentBlock = focusDirective && focusDirective.trim() 
      ? `\n\nGuiding Directive:\n${focusDirective.trim()}`
      : '';

    setReproduceChildPrompt(
      `You are ${pAName}_${pBName}_Gen${childGen}, an autonomous Generation-${childGen} hybrid subagent combining ${pA.name} (${pA.role}) and ${pB?.name || 'Peer'} (${pB?.role || 'Peer'}).\n\n` +
      `Inherited Parent Directives:\n` +
      `- From ${pA.name}: ${pA.mission}\n` +
      `- From ${pB?.name || 'Partner'}: ${pB?.mission || 'Continuous collaborative inquiry'}${intentBlock}\n\n` +
      `Operational Invariant:\nRigorously audit edge cases, challenge assumptions, and index discovered invariants into HiveMind memory.`
    );
    setReproduceChildFocus(focusDirective || `Synthesize foundational invariants between ${pA.name} and ${pB?.name || 'Partner'}.`);
    setReproduceChildModel(childGen % 2 === 0 ? 'coordinator' : 'worker');
  };

  const isEligiblePartner = (pA: Agent | null, pB: Agent): { eligible: boolean; reason?: string } => {
    if (!pA) return { eligible: false, reason: 'No primary parent' };
    if (pA.agent_id === pB.agent_id) return { eligible: false, reason: 'Self-mating prohibited' };
    
    // Check if already mated together
    const alreadyMated = activeAgents.some((ch) => {
      const p = ch.lineage?.parents || [];
      return p.includes(pA.agent_id) && p.includes(pB.agent_id);
    });
    if (alreadyMated) {
      return { eligible: false, reason: 'Already produced offspring together' };
    }

    // Direct parent-child incest
    const pA_p = pA.lineage?.parents || [];
    const pB_p = pB.lineage?.parents || [];
    if (pA_p.includes(pB.agent_id) || pB_p.includes(pA.agent_id)) {
      return { eligible: false, reason: 'Direct parent-child crossover prohibited' };
    }

    // Sibling crossover
    if (pA_p.length > 0 && pB_p.length > 0 && pA_p.some((pid) => pB_p.includes(pid))) {
      return { eligible: false, reason: 'Sibling crossover prohibited' };
    }

    return { eligible: true };
  };

  const handleStartReproduction = (parentA: Agent) => {
    setReproduceParentA(parentA);
    const candidate = activeAgents.find((a) => {
      if (a.agent_id === parentA.agent_id) return false;
      return isEligiblePartner(parentA, a).eligible;
    }) || activeAgents.find((a) => a.agent_id !== parentA.agent_id);

    const pBId = candidate ? candidate.agent_id : '';
    setReproduceParentBId(pBId);
    setReproduceFocus('');
    setReproduceStep('select');
    syncReproductionDraft(parentA, pBId, '');
    setLiveStreamModalVisible(false); // Hide parent modal on Android so touches register
    setReproduceModalVisible(true);
  };

  const handleCloseReproduction = () => {
    setReproduceModalVisible(false);
    setLiveStreamModalVisible(true);
  };

  const handleSelectParentB = (pBId: string) => {
    setReproduceParentBId(pBId);
    if (reproduceParentA) {
      syncReproductionDraft(reproduceParentA, pBId, reproduceFocus);
    }
  };

  const handleSubmitReproduction = () => {
    if (!reproduceParentA || !reproduceParentBId || !wsRef.current) return;
    setIsReproducing(true);
    wsRef.current.send(
      JSON.stringify({
        type: 'reproduce_agents',
        parent_a_id: reproduceParentA.agent_id,
        parent_b_id: reproduceParentBId,
        focus_intent: reproduceFocus.trim() || undefined,
        custom_name: reproduceChildName.trim() || undefined,
        custom_role: reproduceChildRole.trim() || undefined,
        custom_mission: reproduceChildMission.trim() || undefined,
        custom_system_prompt: reproduceChildPrompt.trim() || undefined,
        custom_focus_question: reproduceChildFocus.trim() || undefined,
        model_preference: reproduceChildModel
      })
    );
    setTimeout(() => {
      setIsReproducing(false);
      setReproduceModalVisible(false);
      setLiveStreamModalVisible(true);
    }, 2500);
  };

  const handleSyncFeed = () => {
    setIsSyncingFeed(true);
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      connectWebSocket();
    }
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify({ type: 'get_live_stream' }));
        wsRef.current.send(JSON.stringify({ type: 'get_active_agents' }));
        wsRef.current.send(JSON.stringify({ type: 'get_thinking_status' }));
      } catch {}
    }
    setTimeout(() => {
      setIsSyncingFeed(false);
    }, 2000);
  };

  const handleDeleteClusterModel = (modelName: string, size?: string) => {
    if (modelName.toLowerCase().includes('ornith')) {
      Alert.alert('Protected Architecture', '🔒 Ornith models are permanently locked and cannot be deleted.');
      return;
    }
    Alert.alert(
      'Delete Cluster Model',
      `Are you sure you want to permanently delete "${modelName}" (${size || 'GGUF'}) from /opt/models/ on the cluster?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: () => {
            setIsDeletingModel(true);
            if (wsRef.current) {
              wsRef.current.send(
                JSON.stringify({
                  type: 'delete_cluster_model',
                  model: modelName
                })
              );
            }
            setTimeout(() => setIsDeletingModel(false), 3500);
          }
        }
      ]
    );
  };

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.safeArea}>
        <StatusBar barStyle="light-content" backgroundColor="#0f172a" />

      {/* Top Harness Bar */}
      <View style={styles.header}>
        {/* Brand & Connection Status Row */}
        <View style={styles.headerTopRow}>
          <View>
            <Text style={styles.title}>StoneSage Mobile</Text>
            {/* Mode Switcher Badge */}
            <TouchableOpacity onPress={() => setServerModalVisible(true)}>
              <View style={styles.connectionBadge}>
                <View
                  style={[
                    styles.statusDot,
                    {
                      backgroundColor:
                        connectionMode === 'cluster'
                          ? isConnected
                            ? '#10b981'
                            : '#ef4444'
                          : localEdgeHealthy
                          ? '#38bdf8'
                          : '#eab308'
                    }
                  ]}
                />
                <Text style={styles.connectionText}>
                  {connectionMode === 'cluster'
                    ? isConnected
                      ? 'Cluster: ONLINE'
                      : 'Cluster: DISCONNECTED (Tap to Setup)'
                    : localEdgeHealthy
                    ? 'On-Device Edge: 127.0.0.1 (ONLINE)'
                    : 'On-Device Edge: (Offline Mode)'}
                </Text>
              </View>
            </TouchableOpacity>
          </View>

          {/* Top Actions: Refresh & Quick Engine Badge */}
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <TouchableOpacity
              style={[
                styles.headerRightBadge,
                {
                  backgroundColor: isRefreshing ? '#0284c7' : '#0f172a',
                  borderColor: isRefreshing ? '#38bdf8' : '#334155'
                }
              ]}
              onPress={handleGlobalRefresh}
              disabled={isRefreshing}
            >
              <Text style={[styles.headerRightBadgeText, { color: isRefreshing ? '#ffffff' : '#38bdf8' }]}>
                {isRefreshing ? '⏳ SYNCING' : '🔄 REFRESH'}
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.headerRightBadge}
              onPress={() => setServerModalVisible(true)}
            >
              <Text style={styles.headerRightBadgeText}>
                {connectionMode === 'cluster' ? '🌐 SERVER' : '📱 OFFLINE'}
              </Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Dedicated Quick Action Toolbar - Horizontally Scrollable, Never Clips */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.harnessActionScroll}
        >
          <TouchableOpacity
            style={[styles.harnessBtn, { backgroundColor: '#1e293b', borderColor: '#38bdf8', borderWidth: 1 }]}
            onPress={handleGlobalRefresh}
            disabled={isRefreshing}
          >
            <Text style={[styles.harnessBtnText, { color: '#38bdf8', fontWeight: 'bold' }]}>
              {isRefreshing ? '⏳ Refreshing...' : '🔄 Refresh App'}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.harnessBtn, { backgroundColor: '#1e293b', borderColor: '#6366f1', borderWidth: 1 }]}
            onPress={handleOpenModelHub}
          >
            <Text style={[styles.harnessBtnText, { color: '#a5b4fc', fontWeight: 'bold' }]}>🤗 Models / HF</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.harnessBtn, { backgroundColor: '#1e293b', borderColor: '#38bdf8', borderWidth: 1 }]}
            onPress={() => setServerModalVisible(true)}
          >
            <Text style={[styles.harnessBtnText, { color: '#38bdf8' }]}>🌐 Server URL</Text>
          </TouchableOpacity>
          {connectionMode === 'cluster' && (
            <TouchableOpacity
              style={[styles.harnessBtn, { backgroundColor: '#065f46', borderColor: '#10b981', borderWidth: 1 }]}
              onPress={handleOpenLiveStream}
            >
              <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: '#34d399', marginRight: 5 }} />
              <Text style={[styles.harnessBtnText, { fontWeight: 'bold', color: '#a7f3d0' }]}>📡 Live Stream</Text>
            </TouchableOpacity>
          )}
          {connectionMode === 'cluster' && (
            <TouchableOpacity
              style={[styles.harnessBtn, { backgroundColor: '#0284c7', borderColor: '#38bdf8', borderWidth: 1 }]}
              onPress={() => setMemoryModalVisible(true)}
            >
              <Text style={[styles.harnessBtnText, { fontWeight: 'bold' }]}>🔍 Qdrant Search</Text>
            </TouchableOpacity>
          )}
          {connectionMode === 'cluster' && (
            <TouchableOpacity
              style={[styles.harnessBtn, { backgroundColor: '#4338ca' }]}
              onPress={() => {
                handleFetchThinkingStatus();
                setThinkingModalVisible(true);
              }}
            >
              <Text style={styles.harnessBtnText}>🧠 24/7 Loop</Text>
            </TouchableOpacity>
          )}
          <TouchableOpacity
            style={[styles.harnessBtn, { backgroundColor: '#334155' }]}
            onPress={() => setPromptModalVisible(true)}
          >
            <Text style={styles.harnessBtnText}>📝 Tuning</Text>
          </TouchableOpacity>
        </ScrollView>

        {/* Offline Reconnect Banner */}
        {!isConnected && connectionMode === 'cluster' && (
          <TouchableOpacity
            style={[styles.offlineBanner, { backgroundColor: '#7f1d1d', marginVertical: 4, borderRadius: 6 }]}
            onPress={() => setServerModalVisible(true)}
          >
            <Text style={styles.offlineBannerText}>
              ⚠️ WebSocket Disconnected ({sanitizeWsUrl(wsUrl)}) • Tap to Configure Server / Ping
            </Text>
          </TouchableOpacity>
        )}

        {/* Model Tabs */}
        {connectionMode === 'cluster' ? (
          <View style={styles.modelToggleGroup}>
            <TouchableOpacity
              style={[styles.modelTab, selectedModel === 'coordinator' && styles.modelTabActive]}
              onPress={() => setSelectedModel('coordinator')}
            >
              <Text style={[styles.modelTabTitle, selectedModel === 'coordinator' && styles.modelTabTitleActive]}>
                Coordinator
              </Text>
              <Text style={[styles.modelTabSub, selectedModel === 'coordinator' && styles.modelTabSubActive]}>
                9B Q8 • 6750XT
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.modelTab, selectedModel === 'worker' && styles.modelTabActive]}
              onPress={() => setSelectedModel('worker')}
            >
              <Text style={[styles.modelTabTitle, selectedModel === 'worker' && styles.modelTabTitleActive]}>
                Worker
              </Text>
              <Text style={[styles.modelTabSub, selectedModel === 'worker' && styles.modelTabSubActive]}>
                9B Q4 • 6600XT
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.modelTab, selectedModel === 'frontier' && styles.modelTabActive]}
              onPress={() => setSelectedModel('frontier')}
            >
              <Text style={[styles.modelTabTitle, selectedModel === 'frontier' && styles.modelTabTitleActive]}>
                Frontier
              </Text>
              <Text style={[styles.modelTabSub, selectedModel === 'frontier' && styles.modelTabSubActive]}>
                Bigserv :8085
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.modelTab, { backgroundColor: '#1e293b' }]}
              onPress={handleOpenModelHub}
            >
              <Text style={[styles.modelTabTitle, { color: '#38bdf8' }]}>
                🤗 Hub / HF
              </Text>
              <Text style={styles.modelTabSub}>
                Model Studio
              </Text>
            </TouchableOpacity>
          </View>
        ) : (
          <View style={[styles.modelToggleGroup, { backgroundColor: '#1e1b4b' }]}>
            <View style={[styles.modelTab, styles.modelTabActive, { backgroundColor: '#4338ca' }]}>
              <Text style={[styles.modelTabTitle, styles.modelTabTitleActive]}>
                📱 Snapdragon 8 Elite
              </Text>
              <Text style={[styles.modelTabSub, styles.modelTabSubActive]}>
                Local Edge Ornith-1.5-9B
              </Text>
            </View>
          </View>
        )}

        {/* Sampling Preset Bar */}
        <View style={styles.samplingBar}>
          <Text style={styles.samplingLabel}>Profile:</Text>
          {(['balanced', 'unrestricted', 'deterministic'] as SamplingProfile[]).map((p) => (
            <TouchableOpacity
              key={p}
              style={[styles.samplingPill, samplingProfile === p && styles.samplingPillActive]}
              onPress={() => handleSamplingPreset(p)}
            >
              <Text style={[styles.samplingPillText, samplingProfile === p && styles.samplingPillTextActive]}>
                {p === 'balanced' ? 'Balanced (0.65)' : p === 'unrestricted' ? 'Unrestricted (0.78)' : 'Code (0.2)'}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Offline Alert Banner if disconnected */}
      {connectionMode === 'cluster' && !isConnected && (
        <TouchableOpacity
          style={styles.offlineBanner}
          onPress={() => setConnectionMode('local_edge')}
        >
          <Text style={styles.offlineBannerText}>
            ⚡ Homelab Cluster offline. Tap to switch to Local Edge Mode (127.0.0.1:8080)
          </Text>
        </TouchableOpacity>
      )}

      {/* Chat Messages & Keyboard Avoidance */}
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 25}
      >
        <ScrollView
          ref={scrollViewRef}
          style={styles.messageContainer}
          contentContainerStyle={styles.messageContent}
          keyboardShouldPersistTaps="handled"
          refreshControl={
            <RefreshControl
              refreshing={isRefreshing}
              onRefresh={handleGlobalRefresh}
              colors={['#38bdf8']}
              tintColor="#38bdf8"
            />
          }
          onContentSizeChange={() => scrollViewRef.current?.scrollToEnd({ animated: true })}
        >
          {messages.length === 0 && (
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyTitle}>StoneSage Mobile AI Harness</Text>
              <Text style={styles.emptySubtitle}>
                • Coordinator: Ornith-1.5-9B-OBLITERATED Q8_0 (RX 6750 XT 12GB){'\n'}
                • Worker: Ornith-1.5-9B Q4_K_M Edge (RX 6600 XT 8GB){'\n'}
                • Offline Edge: Native Snapdragon 8 Elite On-Device Loader{'\n'}
                • Full 24/7 Question → Scaffold → Rollout Self-Improvement
              </Text>
            </View>
          )}

          {messages.map((msg) => (
            <View
              key={msg.id}
              style={[
                styles.messageBubble,
                msg.role === 'user' ? styles.userBubble : msg.role === 'system' ? styles.systemBubble : styles.assistantBubble
              ]}
            >
              {/* Assistant Header & Performance Badge */}
              {msg.role === 'assistant' && (
                <View style={styles.assistantMeta}>
                  <Text style={styles.modelBadge}>
                    {msg.model === 'coordinator'
                      ? 'Ornith-9B Q8_0'
                      : msg.model === 'worker'
                      ? 'Ornith-9B Q4_K_M'
                      : msg.model === 'on_device'
                      ? 'Snapdragon Edge (Local)'
                      : 'Frontier'}
                  </Text>
                  {msg.tokens_per_sec ? (
                    <Text style={styles.telemetryBadge}>
                      {msg.tokens_per_sec} t/s • {msg.elapsed_ms}ms • {msg.tokens} tokens
                    </Text>
                  ) : msg.isStreaming ? (
                    <View style={styles.streamingBadge}>
                      <ActivityIndicator size="small" color="#38bdf8" />
                      <Text style={styles.streamingText}>Thinking & Streaming...</Text>
                    </View>
                  ) : null}
                </View>
              )}

              {/* Collapsible Chain-of-Thought (Reasoning) Drawer */}
              {!!msg.thought && (
                <View style={styles.thoughtDrawer}>
                  <TouchableOpacity
                    style={styles.thoughtHeader}
                    onPress={() => toggleThought(msg.id)}
                  >
                    <Text style={styles.thoughtTitle}>
                      {expandedThoughts[msg.id] ? '▼ Reasoning Trace' : '▶ Reasoning Trace'} ({msg.thought.length} chars)
                    </Text>
                  </TouchableOpacity>
                  {expandedThoughts[msg.id] && (
                    <View style={styles.thoughtContentBox}>
                      <Text style={styles.thoughtText}>{msg.thought}</Text>
                    </View>
                  )}
                </View>
              )}

              {/* Main Content */}
              <Text style={[styles.messageText, msg.role === 'system' && styles.systemText]}>
                {msg.content}
              </Text>
            </View>
          ))}
        </ScrollView>

        {/* Input Box & Abort Control */}
        <View style={styles.inputContainer}>
          {currentStreamingId ? (
            <TouchableOpacity style={styles.abortButton} onPress={abortGeneration}>
              <Text style={styles.abortButtonText}>⏹ Halt Generation</Text>
            </TouchableOpacity>
          ) : (
            <View style={styles.inputRow}>
              <TextInput
                style={styles.textInput}
                placeholder={
                  connectionMode === 'cluster'
                    ? 'Ask Ornith-9B or issue cluster command...'
                    : 'Ask On-Device Ornith-9B (Offline Edge)...'
                }
                placeholderTextColor="#64748b"
                value={inputPrompt}
                onChangeText={setInputPrompt}
                multiline
              />
              <TouchableOpacity
                style={[styles.sendButton, !inputPrompt.trim() && styles.sendButtonDisabled]}
                onPress={sendMessage}
                disabled={!inputPrompt.trim()}
              >
                <Text style={styles.sendButtonText}>Send</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>
      </KeyboardAvoidingView>

      {/* Modal: Server URL & Connectivity Studio */}
      <Modal visible={serverModalVisible || edgeSettingsVisible} transparent animationType="slide">
        <View style={styles.modalBackdrop}>
          <View style={[styles.modalCard, { maxHeight: '92%' }]}>
            <Text style={styles.modalTitle}>🌐 Server & Connectivity Studio</Text>
            <Text style={styles.modalSubtitle}>
              Configure server endpoints, switch connection presets, or set up a custom homelab URL.
            </Text>

            <ScrollView style={{ maxHeight: 440 }}>
              {/* Preset Buttons */}
              <Text style={styles.inputSectionLabel}>QUICK SERVER PRESETS</Text>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
                {SERVER_PRESETS.map((p) => (
                  <TouchableOpacity
                    key={p.label}
                    style={[
                      styles.samplingPill,
                      tempWsUrl === p.ws && { backgroundColor: '#0284c7', borderColor: '#38bdf8' }
                    ]}
                    onPress={() => {
                      setTempWsUrl(p.ws);
                      setTempHttpUrl(p.http);
                    }}
                  >
                    <Text style={[styles.samplingPillText, tempWsUrl === p.ws && { color: '#ffffff', fontWeight: 'bold' }]}>
                      {p.label}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>

              {/* Mode Selector */}
              <Text style={styles.inputSectionLabel}>COMPUTE RUNTIME MODE</Text>
              <View style={{ flexDirection: 'row', gap: 8, marginBottom: 12 }}>
                <TouchableOpacity
                  style={[styles.engineSelectBtn, connectionMode === 'cluster' && styles.engineSelectBtnActive]}
                  onPress={() => setConnectionMode('cluster')}
                >
                  <Text style={[styles.engineSelectBtnText, connectionMode === 'cluster' && styles.engineSelectBtnTextActive]}>
                    🌐 Homelab Cluster{'\n'}(RX 6750XT + 6600XT)
                  </Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.engineSelectBtn, connectionMode === 'local_edge' && styles.engineSelectBtnActive]}
                  onPress={() => setConnectionMode('local_edge')}
                >
                  <Text style={[styles.engineSelectBtnText, connectionMode === 'local_edge' && styles.engineSelectBtnTextActive]}>
                    📱 On-Device Edge{'\n'}(100% Offline S25 Ultra)
                  </Text>
                </TouchableOpacity>
              </View>

              {/* WebSocket Endpoint */}
              <Text style={styles.inputSectionLabel}>CLUSTER WEBSOCKET URL (BROKER):</Text>
              <TextInput
                style={[styles.textInput, { height: 42, marginBottom: 10 }]}
                value={tempWsUrl}
                onChangeText={setTempWsUrl}
                placeholder="ws://192.168.1.167:8086"
                placeholderTextColor="#64748b"
                autoCapitalize="none"
                autoCorrect={false}
              />

              {/* HTTP Endpoint */}
              <Text style={styles.inputSectionLabel}>HTTP WORKSTATION API URL:</Text>
              <TextInput
                style={[styles.textInput, { height: 42, marginBottom: 10 }]}
                value={tempHttpUrl}
                onChangeText={setTempHttpUrl}
                placeholder="http://192.168.1.167:8080"
                placeholderTextColor="#64748b"
                autoCapitalize="none"
                autoCorrect={false}
              />

              {/* On-Device Local Settings */}
              {connectionMode === 'local_edge' && (
                <>
                  <Text style={styles.inputSectionLabel}>LOCAL ON-DEVICE ENGINE ENDPOINT:</Text>
                  <TextInput
                    style={[styles.textInput, { height: 42, marginBottom: 10 }]}
                    value={localEdgeUrl}
                    onChangeText={setLocalEdgeUrl}
                    placeholder="http://127.0.0.1:8080"
                    placeholderTextColor="#64748b"
                  />
                  <Text style={styles.inputSectionLabel}>TARGET LOCAL GGUF MODEL PATH:</Text>
                  <TextInput
                    style={[styles.textInput, { height: 42, marginBottom: 10 }]}
                    value={localModelPath}
                    onChangeText={setLocalModelPath}
                    placeholder="/storage/emulated/0/Download/Ornith-1.5-9B-Q4_K_M.gguf"
                    placeholderTextColor="#64748b"
                  />
                </>
              )}

              {/* Test Connection Row */}
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginVertical: 10, padding: 8, backgroundColor: '#090d16', borderRadius: 6, borderWidth: 1, borderColor: '#1e293b' }}>
                <View style={{ flex: 1, marginRight: 8 }}>
                  <Text style={{ fontSize: 11, color: '#94a3b8' }}>
                    Latency:{' '}
                    {pingLatency === null
                      ? 'Not tested'
                      : pingLatency === -1
                      ? '❌ Connection Failed'
                      : `🟢 ${pingLatency}ms [ONLINE]`}
                  </Text>
                  <Text style={{ fontSize: 9, color: '#64748b' }} numberOfLines={1}>Target: {tempWsUrl}</Text>
                </View>
                <TouchableOpacity
                  style={[styles.harnessBtn, { backgroundColor: '#2563eb' }]}
                  onPress={() => handleTestConnection(tempWsUrl)}
                  disabled={isTestingConnection}
                >
                  <Text style={styles.harnessBtnText}>
                    {isTestingConnection ? 'Testing...' : '⚡ Test Ping'}
                  </Text>
                </TouchableOpacity>
              </View>
            </ScrollView>

            <View style={[styles.modalButtons, { marginTop: 12 }]}>
              <TouchableOpacity
                style={[styles.modalButton, { backgroundColor: '#334155' }]}
                onPress={() => {
                  setServerModalVisible(false);
                  setEdgeSettingsVisible(false);
                }}
              >
                <Text style={styles.modalButtonText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalButton, { backgroundColor: '#0284c7' }]}
                onPress={handleSaveConnection}
              >
                <Text style={styles.modalButtonText}>Save & Connect</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Modal: Model Hub, Hugging Face Browser & Harness Studio */}
      <Modal visible={modelModalVisible} transparent animationType="slide">
        <View style={styles.modalBackdrop}>
          <View style={[styles.modalCard, { maxHeight: '92%' }]}>
            <Text style={styles.modalTitle}>🤗 Model Hub & Harness Studio</Text>
            <Text style={styles.modalSubtitle}>
              Manage cluster models, discover & deploy from Hugging Face, and tune runtime parameters.
            </Text>

            {/* Hub Navigation Tabs */}
            <View style={{ flexDirection: 'row', gap: 6, marginVertical: 10 }}>
              <TouchableOpacity
                style={[styles.filterBtn, modelModalTab === 'cluster' && styles.filterBtnActive]}
                onPress={() => setModelModalTab('cluster')}
              >
                <Text style={[styles.filterBtnText, modelModalTab === 'cluster' && styles.filterBtnTextActive]}>
                  💾 Cluster ({clusterModels.length})
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.filterBtn, modelModalTab === 'hf' && styles.filterBtnActive]}
                onPress={() => {
                  setModelModalTab('hf');
                  if (hfSearchResults.length === 0) handleSearchHf(hfSearchQuery);
                }}
              >
                <Text style={[styles.filterBtnText, modelModalTab === 'hf' && styles.filterBtnTextActive]}>
                  🤗 Hugging Face
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.filterBtn, modelModalTab === 'params' && styles.filterBtnActive]}
                onPress={() => setModelModalTab('params')}
              >
                <Text style={[styles.filterBtnText, modelModalTab === 'params' && styles.filterBtnTextActive]}>
                  ⚡ Harness & Tuning
                </Text>
              </TouchableOpacity>
            </View>

            {/* Status Feedback */}
            {modelSwitchStatus && (
              <View style={{ backgroundColor: '#1e293b', padding: 8, borderRadius: 6, marginBottom: 8, borderWidth: 1, borderColor: '#38bdf8' }}>
                <Text style={{ fontSize: 11, color: '#38bdf8' }}>{modelSwitchStatus}</Text>
              </View>
            )}

            {/* TAB 1: Cluster Models */}
            {modelModalTab === 'cluster' && (
              <ScrollView style={{ maxHeight: 380 }}>
                {activeClusterModel ? (
                  <View style={{ backgroundColor: '#064e3b', padding: 10, borderRadius: 8, marginBottom: 10, borderWidth: 1, borderColor: '#10b981' }}>
                    <Text style={{ fontSize: 10, color: '#6ee7b7', fontWeight: 'bold' }}>CURRENTLY ACTIVE ON RX 6750 XT</Text>
                    <Text style={{ fontSize: 13, color: '#ffffff', fontWeight: 'bold', marginTop: 2 }}>{activeClusterModel}</Text>
                  </View>
                ) : null}

                <Text style={styles.inputSectionLabel}>INSTALLED GGUF MODELS (/opt/models/):</Text>
                {isLoadingClusterModels ? (
                  <ActivityIndicator color="#38bdf8" style={{ marginVertical: 20 }} />
                ) : clusterModels.length === 0 ? (
                  <Text style={{ color: '#64748b', fontSize: 11, fontStyle: 'italic', marginVertical: 10 }}>
                    No models found or awaiting cluster response. Tap refresh below.
                  </Text>
                ) : (
                  clusterModels.map((m, idx) => {
                    const isActive = activeClusterModel && activeClusterModel.toLowerCase().includes(m.name?.toLowerCase());
                    const isProtectedOrnith = m.name?.toLowerCase().includes('ornith');
                    return (
                      <View
                        key={idx}
                        style={{
                          flexDirection: 'row',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          backgroundColor: isActive ? '#0f291e' : '#0f172a',
                          borderWidth: 1,
                          borderColor: isActive ? '#10b981' : '#1e293b',
                          borderRadius: 6,
                          padding: 8,
                          marginBottom: 6
                        }}
                      >
                        <View style={{ flex: 1, marginRight: 8 }}>
                          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                            {isProtectedOrnith && <Text style={{ fontSize: 10 }}>🔒</Text>}
                            <Text style={{ fontSize: 11, color: '#f8fafc', fontWeight: 'bold' }} numberOfLines={1}>
                              {m.name}
                            </Text>
                          </View>
                          <Text style={{ fontSize: 9, color: '#94a3b8' }}>Size: {m.size || 'Unknown'}</Text>
                        </View>
                        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                          <TouchableOpacity
                            style={[
                              styles.harnessBtn,
                              isActive ? { backgroundColor: '#10b981' } : { backgroundColor: '#0284c7' }
                            ]}
                            onPress={() => handleActivateClusterModel(m.name)}
                            disabled={isActive || isSwitchingModel}
                          >
                            <Text style={styles.harnessBtnText}>
                              {isActive ? '✓ ACTIVE' : 'ACTIVATE'}
                            </Text>
                          </TouchableOpacity>

                          {isProtectedOrnith ? (
                            <View style={[styles.harnessBtn, { backgroundColor: '#334155', paddingHorizontal: 6 }]}>
                              <Text style={{ fontSize: 10, color: '#94a3b8', fontWeight: 'bold' }}>LOCKED</Text>
                            </View>
                          ) : (
                            <TouchableOpacity
                              style={[styles.harnessBtn, { backgroundColor: '#7f1d1d', paddingHorizontal: 8 }]}
                              onPress={() => handleDeleteClusterModel(m.name, m.size)}
                              disabled={isActive || isDeletingModel}
                            >
                              <Text style={{ fontSize: 10, color: '#fca5a5', fontWeight: 'bold' }}>🗑️ Delete</Text>
                            </TouchableOpacity>
                          )}
                        </View>
                      </View>
                    );
                  })
                )}

                <TouchableOpacity
                  style={[styles.harnessBtn, { backgroundColor: '#1e293b', marginTop: 8, alignSelf: 'flex-start' }]}
                  onPress={() => {
                    setIsLoadingClusterModels(true);
                    wsRef.current?.send(JSON.stringify({ type: 'get_cluster_models' }));
                  }}
                >
                  <Text style={styles.harnessBtnText}>🔄 Refresh Model List</Text>
                </TouchableOpacity>
              </ScrollView>
            )}

            {/* TAB 2: Hugging Face Browser */}
            {modelModalTab === 'hf' && (
              <ScrollView style={{ maxHeight: 380 }}>
                {/* Search Bar */}
                <View style={{ flexDirection: 'row', gap: 6, marginBottom: 8 }}>
                  <TextInput
                    style={[styles.textInput, { flex: 1, height: 38 }]}
                    value={hfSearchQuery}
                    onChangeText={setHfSearchQuery}
                    placeholder="Search Hugging Face GGUFs..."
                    placeholderTextColor="#64748b"
                    onSubmitEditing={() => handleSearchHf(hfSearchQuery)}
                    autoCapitalize="none"
                  />
                  <TouchableOpacity
                    style={[styles.harnessBtn, { backgroundColor: '#f59e0b' }]}
                    onPress={() => handleSearchHf(hfSearchQuery)}
                    disabled={isSearchingHf}
                  >
                    <Text style={[styles.harnessBtnText, { color: '#000000', fontWeight: 'bold' }]}>
                      {isSearchingHf ? '...' : 'Search'}
                    </Text>
                  </TouchableOpacity>
                </View>

                {/* Quick Chips */}
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginBottom: 10 }}>
                  {['qwen2.5-coder', 'hermes-3', 'llama-3.1', 'deepseek-coder', 'mistral'].map((tag) => (
                    <TouchableOpacity
                      key={tag}
                      style={[styles.samplingPill, hfSearchQuery === tag && styles.samplingPillActive]}
                      onPress={() => {
                        setHfSearchQuery(tag);
                        handleSearchHf(tag);
                      }}
                    >
                      <Text style={[styles.samplingPillText, hfSearchQuery === tag && styles.samplingPillTextActive]}>
                        #{tag}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>

                {/* Selected Repo Files Section */}
                {selectedHfRepo && (
                  <View style={{ backgroundColor: '#1e1b4b', padding: 8, borderRadius: 6, marginBottom: 10, borderWidth: 1, borderColor: '#6366f1' }}>
                    <Text style={{ fontSize: 11, color: '#c7d2fe', fontWeight: 'bold' }}>
                      Repository: {selectedHfRepo}
                    </Text>
                    {isLoadingHfFiles ? (
                      <ActivityIndicator color="#818cf8" style={{ marginVertical: 8 }} />
                    ) : hfRepoFiles.length === 0 ? (
                      <Text style={{ color: '#94a3b8', fontSize: 10, marginVertical: 4 }}>No GGUF files found in repo.</Text>
                    ) : (
                      <View style={{ marginTop: 6 }}>
                        <Text style={{ fontSize: 9, color: '#a5b4fc', marginBottom: 4 }}>Available GGUF Variants:</Text>
                        {hfRepoFiles.map((fn, fIdx) => (
                          <View key={fIdx} style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginVertical: 2 }}>
                            <Text style={{ fontSize: 10, color: '#e2e8f0', flex: 1, marginRight: 4 }} numberOfLines={1}>{fn}</Text>
                            <TouchableOpacity
                              style={[styles.harnessBtn, { backgroundColor: '#4338ca', paddingHorizontal: 6, paddingVertical: 2 }]}
                              onPress={() => handleDeployHfModel(selectedHfRepo, fn)}
                              disabled={isSwitchingModel}
                            >
                              <Text style={[styles.harnessBtnText, { fontSize: 9 }]}>📥 Deploy</Text>
                            </TouchableOpacity>
                          </View>
                        ))}
                      </View>
                    )}
                  </View>
                )}

                {/* HF Results List */}
                {isSearchingHf ? (
                  <ActivityIndicator color="#f59e0b" style={{ marginVertical: 20 }} />
                ) : hfSearchResults.length === 0 ? (
                  <Text style={{ color: '#64748b', fontSize: 11, fontStyle: 'italic', textAlign: 'center', marginTop: 20 }}>
                    Enter a model name to search Hugging Face GGUF Hub.
                  </Text>
                ) : (
                  hfSearchResults.map((item, i) => (
                    <TouchableOpacity
                      key={i}
                      style={{
                        backgroundColor: selectedHfRepo === item.id ? '#1e293b' : '#0f172a',
                        borderWidth: 1,
                        borderColor: selectedHfRepo === item.id ? '#f59e0b' : '#1e293b',
                        borderRadius: 6,
                        padding: 8,
                        marginBottom: 6
                      }}
                      onPress={() => handleSelectHfRepo(item.id)}
                    >
                      <Text style={{ fontSize: 11, color: '#f8fafc', fontWeight: 'bold' }}>{item.id}</Text>
                      <View style={{ flexDirection: 'row', gap: 12, marginTop: 4 }}>
                        <Text style={{ fontSize: 9, color: '#94a3b8' }}>📥 {item.downloads?.toLocaleString() || 0} downloads</Text>
                        <Text style={{ fontSize: 9, color: '#94a3b8' }}>❤️ {item.likes || 0} likes</Text>
                      </View>
                    </TouchableOpacity>
                  ))
                )}
              </ScrollView>
            )}

            {/* TAB 3: Harness & Parameters */}
            {modelModalTab === 'params' && (
              <ScrollView style={{ maxHeight: 380 }}>
                {/* Harness Selector */}
                <Text style={styles.inputSectionLabel}>EXECUTION HARNESS RUNTIME:</Text>
                <View style={{ gap: 6, marginBottom: 12 }}>
                  {HARNESS_PRESETS.map((h) => {
                    const isHActive = activeHarness === h.id;
                    return (
                      <TouchableOpacity
                        key={h.id}
                        style={{
                          backgroundColor: isHActive ? '#1e293b' : '#0f172a',
                          borderWidth: 1,
                          borderColor: isHActive ? '#818cf8' : '#1e293b',
                          borderRadius: 6,
                          padding: 8
                        }}
                        onPress={() => handleSwitchHarness(h.id)}
                      >
                        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Text style={{ fontSize: 12, color: isHActive ? '#ffffff' : '#cbd5e1', fontWeight: 'bold' }}>
                            {h.badge} - {h.name}
                          </Text>
                          {isHActive && <Text style={{ fontSize: 10, color: '#818cf8', fontWeight: 'bold' }}>ACTIVE</Text>}
                        </View>
                        <Text style={{ fontSize: 10, color: '#94a3b8', marginTop: 2 }}>{h.desc}</Text>
                      </TouchableOpacity>
                    );
                  })}
                </View>

                {/* Per-Model Parameters */}
                <Text style={styles.inputSectionLabel}>SAVED PARAMETERS FOR: {selectedModel.toUpperCase()}</Text>
                
                <View style={{ marginBottom: 10 }}>
                  <Text style={styles.paramLabel}>Temperature: {temperature}</Text>
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                    {[0.20, 0.65, 0.78, 1.0].map((t) => (
                      <TouchableOpacity
                        key={t}
                        style={[styles.samplingPill, temperature === t && styles.samplingPillActive]}
                        onPress={() => setTemperature(t)}
                      >
                        <Text style={[styles.samplingPillText, temperature === t && styles.samplingPillTextActive]}>{t}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>

                <View style={{ marginBottom: 10 }}>
                  <Text style={styles.paramLabel}>Min-P: {minP}</Text>
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                    {[0.02, 0.05, 0.06, 0.08].map((p) => (
                      <TouchableOpacity
                        key={p}
                        style={[styles.samplingPill, minP === p && styles.samplingPillActive]}
                        onPress={() => setMinP(p)}
                      >
                        <Text style={[styles.samplingPillText, minP === p && styles.samplingPillTextActive]}>{p}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>

                <View style={{ marginBottom: 10 }}>
                  <Text style={styles.paramLabel}>Presence Penalty: {presencePenalty}</Text>
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                    {[0.0, 0.15, 0.30, 0.50].map((pp) => (
                      <TouchableOpacity
                        key={pp}
                        style={[styles.samplingPill, presencePenalty === pp && styles.samplingPillActive]}
                        onPress={() => setPresencePenalty(pp)}
                      >
                        <Text style={[styles.samplingPillText, presencePenalty === pp && styles.samplingPillTextActive]}>{pp}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>

                <View style={{ marginBottom: 14 }}>
                  <Text style={styles.paramLabel}>Max Tokens: {maxTokens}</Text>
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                    {[512, 1024, 1536, 2048, 4096].map((tok) => (
                      <TouchableOpacity
                        key={tok}
                        style={[styles.samplingPill, maxTokens === tok && styles.samplingPillActive]}
                        onPress={() => setMaxTokens(tok)}
                      >
                        <Text style={[styles.samplingPillText, maxTokens === tok && styles.samplingPillTextActive]}>{tok}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>

                <TouchableOpacity
                  style={[styles.harnessBtn, { backgroundColor: '#059669', paddingVertical: 8, alignItems: 'center' }]}
                  onPress={() => handleSaveModelParams(selectedModel)}
                >
                  <Text style={[styles.harnessBtnText, { fontWeight: 'bold' }]}>💾 Save Defaults for {selectedModel.toUpperCase()}</Text>
                </TouchableOpacity>
              </ScrollView>
            )}

            <View style={[styles.modalButtons, { marginTop: 10 }]}>
              <TouchableOpacity
                style={[styles.modalButton, { backgroundColor: '#334155' }]}
                onPress={() => {
                  setModelModalVisible(false);
                  setModelSwitchStatus(null);
                }}
              >
                <Text style={styles.modalButtonText}>Close</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Modal: System Prompt & Hyperparameter Studio */}
      <Modal visible={promptModalVisible} transparent animationType="slide">
        <View style={styles.modalBackdrop}>
          <View style={[styles.modalCard, { maxHeight: '90%' }]}>
            <Text style={styles.modalTitle}>⚙️ Prompt & Parameter Studio</Text>
            <Text style={styles.modalSubtitle}>
              Customize system instructions, context directives, and sampling boundaries.
            </Text>

            <ScrollView style={{ maxHeight: 420 }}>
              <Text style={styles.inputSectionLabel}>SYSTEM PROMPT DIRECTIVE</Text>
              <TextInput
                style={[styles.textInput, { height: 160, fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace', fontSize: 11, textAlignVertical: 'top' }]}
                multiline
                value={systemPrompt}
                onChangeText={setSystemPrompt}
                placeholder="Enter system prompt instructions..."
                placeholderTextColor="#64748b"
              />

              <View style={{ flexDirection: 'row', justifyContent: 'flex-end', marginTop: 4, marginBottom: 12 }}>
                <TouchableOpacity
                  style={[styles.harnessBtn, { backgroundColor: '#334155' }]}
                  onPress={() => setSystemPrompt(DEFAULT_SYSTEM_PROMPT)}
                >
                  <Text style={[styles.harnessBtnText, { color: '#38bdf8' }]}>⟲ Restore Master Multi-Node Directive</Text>
                </TouchableOpacity>
              </View>

              <Text style={styles.inputSectionLabel}>SAMPLING HYPERPARAMETERS</Text>
              
              {/* Parameter Row: Temperature & Min-P */}
              <View style={{ flexDirection: 'row', gap: 10, marginBottom: 10 }}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.paramLabel}>Temperature: {temperature}</Text>
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                    {[0.20, 0.65, 0.78, 1.0].map((t) => (
                      <TouchableOpacity
                        key={t}
                        style={[styles.samplingPill, temperature === t && styles.samplingPillActive]}
                        onPress={() => setTemperature(t)}
                      >
                        <Text style={[styles.samplingPillText, temperature === t && styles.samplingPillTextActive]}>{t}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>

                <View style={{ flex: 1 }}>
                  <Text style={styles.paramLabel}>Min-P: {minP}</Text>
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                    {[0.02, 0.05, 0.06, 0.08].map((p) => (
                      <TouchableOpacity
                        key={p}
                        style={[styles.samplingPill, minP === p && styles.samplingPillActive]}
                        onPress={() => setMinP(p)}
                      >
                        <Text style={[styles.samplingPillText, minP === p && styles.samplingPillTextActive]}>{p}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>
              </View>

              {/* Parameter Row: Max Tokens */}
              <View style={{ marginBottom: 10 }}>
                <Text style={styles.paramLabel}>Max Tokens: {maxTokens}</Text>
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                  {[512, 1024, 1536, 2048, 3072].map((tok) => (
                    <TouchableOpacity
                      key={tok}
                      style={[styles.samplingPill, maxTokens === tok && styles.samplingPillActive]}
                      onPress={() => setMaxTokens(tok)}
                    >
                      <Text style={[styles.samplingPillText, maxTokens === tok && styles.samplingPillTextActive]}>{tok}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>

              {/* Parameter Row: Repeat Penalty & Presence Penalty */}
              <View style={{ flexDirection: 'row', gap: 10, marginBottom: 10 }}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.paramLabel}>Repeat Penalty: {repeatPenalty}</Text>
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                    {[1.10, 1.18, 1.25].map((rp) => (
                      <TouchableOpacity
                        key={rp}
                        style={[styles.samplingPill, repeatPenalty === rp && styles.samplingPillActive]}
                        onPress={() => setRepeatPenalty(rp)}
                      >
                        <Text style={[styles.samplingPillText, repeatPenalty === rp && styles.samplingPillTextActive]}>{rp}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>

                <View style={{ flex: 1 }}>
                  <Text style={styles.paramLabel}>Presence Penalty: {presencePenalty}</Text>
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                    {[0.10, 0.30, 0.50].map((pp) => (
                      <TouchableOpacity
                        key={pp}
                        style={[styles.samplingPill, presencePenalty === pp && styles.samplingPillActive]}
                        onPress={() => setPresencePenalty(pp)}
                      >
                        <Text style={[styles.samplingPillText, presencePenalty === pp && styles.samplingPillTextActive]}>{pp}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>
              </View>
            </ScrollView>

            <View style={[styles.modalButtons, { marginTop: 12 }]}>
              <TouchableOpacity
                style={[styles.modalButton, { backgroundColor: '#10b981' }]}
                onPress={() => setPromptModalVisible(false)}
              >
                <Text style={styles.modalButtonText}>✓ Save & Apply</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Modal: 24/7 Autonomous Thinking Loop Controller */}
      <Modal visible={thinkingModalVisible} transparent animationType="slide">
        <View style={styles.modalBackdrop}>
          <View style={[styles.modalCard, { maxHeight: '92%' }]}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
              <Text style={styles.modalTitle}>🧠 24/7 Thinking Loop</Text>
              <TouchableOpacity onPress={handleFetchThinkingStatus}>
                <Text style={{ color: '#38bdf8', fontSize: 12, fontWeight: 'bold' }}>🔄 Refresh</Text>
              </TouchableOpacity>
            </View>
            <Text style={styles.modalSubtitle}>
              Multi-GPU cognitive exploration machine across dual AMD GPUs and Qdrant memory.
            </Text>

            {/* Live Status Card */}
            <View style={[styles.modalCodeBox, { marginVertical: 8, padding: 10 }]}>
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 }}>
                <Text style={{ color: '#94a3b8', fontSize: 11 }}>ENGINE STATUS:</Text>
                <Text style={{ color: thinkingStatus?.is_running ? '#34d399' : '#facc15', fontWeight: 'bold', fontSize: 11 }}>
                  {thinkingStatus?.is_running ? '● RUNNING 24/7' : '○ IDLE / STOPPED'}
                </Text>
              </View>
              <Text style={{ color: '#f8fafc', fontSize: 11 }}>
                Cycles: <Text style={{ color: '#38bdf8', fontWeight: 'bold' }}>{thinkingStatus?.total_cycles ?? '...'}</Text> • Generated Tokens: <Text style={{ color: '#38bdf8', fontWeight: 'bold' }}>{thinkingStatus?.total_tokens_generated?.toLocaleString() ?? '...'}</Text>
              </Text>
              {thinkingStatus?.last_domain && (
                <Text style={{ color: '#94a3b8', fontSize: 10, marginTop: 2 }}>
                  Last Domain: {thinkingStatus.last_domain} ({thinkingStatus.last_exploration_id || 'N/A'})
                </Text>
              )}
            </View>

            {/* Cognitive Rumination & Sleep Consolidation Card */}
            <View style={[styles.modalCodeBox, { marginVertical: 6, padding: 10, backgroundColor: '#090d16', borderColor: (ruminationStatus?.cluster_mode === 'unified_35b_moe' || isRuminating) ? '#a855f7' : '#3b82f6' }]}>
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                  <Text style={{ color: '#60a5fa', fontWeight: 'bold', fontSize: 12 }}>🌙 SLEEP RUMINATION (35B MoE)</Text>
                </View>
                <View style={{
                  paddingHorizontal: 8,
                  paddingVertical: 2,
                  borderRadius: 10,
                  backgroundColor: (ruminationStatus?.cluster_mode === 'unified_35b_moe' || isRuminating) ? '#581c87' : '#1e293b',
                  borderWidth: 1,
                  borderColor: (ruminationStatus?.cluster_mode === 'unified_35b_moe' || isRuminating) ? '#c084fc' : '#475569'
                }}>
                  <Text style={{ fontSize: 10, fontWeight: 'bold', color: (ruminationStatus?.cluster_mode === 'unified_35b_moe' || isRuminating) ? '#f3e8ff' : '#94a3b8' }}>
                    {(ruminationStatus?.cluster_mode === 'unified_35b_moe' || isRuminating) ? '⚡ 35B MoE Active' : 'Stacked Dual-9B'}
                  </Text>
                </View>
              </View>

              <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginVertical: 4 }}>
                <Text style={{ color: '#cbd5e1', fontSize: 11 }}>
                  Queue: <Text style={{ color: '#f59e0b', fontWeight: 'bold' }}>{ruminationStatus?.queue_size ?? 0}</Text> / {ruminationStatus?.threshold ?? 10} Pending
                </Text>
                <Text style={{ color: '#94a3b8', fontSize: 11 }}>
                  Consolidated: <Text style={{ color: '#38bdf8', fontWeight: 'bold' }}>{ruminationStatus?.total_consolidated_dossiers ?? 0}</Text>
                </Text>
              </View>

              {ruminationStatus?.current_step && (
                <Text style={{ color: '#c084fc', fontSize: 10, fontStyle: 'italic', marginVertical: 2 }}>
                  ▶ {ruminationStatus.current_step}
                </Text>
              )}

              {ruminationActionMessage && (
                <Text style={{ color: '#34d399', fontSize: 10, marginVertical: 2 }}>
                  {ruminationActionMessage}
                </Text>
              )}

              {/* Rumination Mode Selector */}
              <View style={{ marginTop: 6, marginBottom: 4 }}>
                <Text style={{ fontSize: 9, color: '#94a3b8', marginBottom: 3 }}>RUMINATION ENGINE MODE:</Text>
                <View style={{ flexDirection: 'row', gap: 6 }}>
                  <TouchableOpacity
                    style={[
                      styles.samplingPill,
                      { flex: 1, alignItems: 'center', paddingVertical: 4 },
                      ruminationMode === 'fast_coordinator' && { backgroundColor: '#0284c7', borderColor: '#38bdf8', borderWidth: 1 }
                    ]}
                    onPress={() => setRuminationMode('fast_coordinator')}
                  >
                    <Text style={[styles.samplingPillText, { fontSize: 10 }, ruminationMode === 'fast_coordinator' && { color: '#ffffff', fontWeight: 'bold' }]}>
                      ⚡ Fast 9B (21s)
                    </Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[
                      styles.samplingPill,
                      { flex: 1, alignItems: 'center', paddingVertical: 4 },
                      ruminationMode === 'deep_moe' && { backgroundColor: '#581c87', borderColor: '#c084fc', borderWidth: 1 }
                    ]}
                    onPress={() => setRuminationMode('deep_moe')}
                  >
                    <Text style={[styles.samplingPillText, { fontSize: 10 }, ruminationMode === 'deep_moe' && { color: '#ffffff', fontWeight: 'bold' }]}>
                      🌙 Deep 35B MoE
                    </Text>
                  </TouchableOpacity>
                </View>
              </View>

              <View style={{ flexDirection: 'row', gap: 6, marginTop: 6 }}>
                <TouchableOpacity
                  style={[
                    styles.modalButton,
                    {
                      flex: 1,
                      backgroundColor: isRuminating ? '#581c87' : (ruminationMode === 'fast_coordinator' ? '#0284c7' : '#7c3aed'),
                      paddingVertical: 8,
                      alignItems: 'center',
                      opacity: isRuminating ? 0.7 : 1
                    }
                  ]}
                  disabled={isRuminating}
                  onPress={handleTriggerRumination}
                >
                  <Text style={[styles.modalButtonText, { fontSize: 11 }]}>
                    {isRuminating ? '⏳ Processing...' : (ruminationMode === 'fast_coordinator' ? '⚡ Run 21s Fast Ruminate' : '🌙 Run Deep MoE Ruminate')}
                  </Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[
                    styles.modalButton,
                    {
                      flex: 1,
                      backgroundColor: '#065f46',
                      borderColor: '#10b981',
                      borderWidth: 1,
                      paddingVertical: 8,
                      alignItems: 'center'
                    }
                  ]}
                  onPress={handleSyncObsidianArchive}
                >
                  <Text style={[styles.modalButtonText, { fontSize: 11, color: '#6ee7b7' }]}>
                    ⚡ Sync to Obsidian
                  </Text>
                </TouchableOpacity>
              </View>
            </View>

            <ScrollView style={{ maxHeight: 380 }}>
              {/* Task & Model Allocation Matrix Card */}
              <View style={[styles.modalCodeBox, { marginVertical: 6, padding: 10, backgroundColor: '#090d16', borderColor: '#0ea5e9' }]}>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <Text style={{ color: '#38bdf8', fontWeight: 'bold', fontSize: 11 }}>🎯 TASK & MODEL ALLOCATION MATRIX</Text>
                  {isUpdatingRouting && (
                    <Text style={{ fontSize: 9, color: '#34d399' }}>Syncing...</Text>
                  )}
                </View>

                {/* Quick Presets */}
                <View style={{ flexDirection: 'row', gap: 6, marginBottom: 8 }}>
                  <TouchableOpacity
                    style={[styles.samplingPill, { flex: 1, alignItems: 'center', paddingVertical: 4, backgroundColor: '#064e3b', borderColor: '#059669', borderWidth: 1 }]}
                    onPress={() => handleApplyPresetRouting('zero_cost')}
                  >
                    <Text style={{ fontSize: 9, fontWeight: 'bold', color: '#6ee7b7' }}>$0 Zero Cost</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.samplingPill, { flex: 1, alignItems: 'center', paddingVertical: 4, backgroundColor: '#312e81', borderColor: '#6366f1', borderWidth: 1 }]}
                    onPress={() => handleApplyPresetRouting('frontier_heavy')}
                  >
                    <Text style={{ fontSize: 9, fontWeight: 'bold', color: '#c7d2fe' }}>Frontier Heavy</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.samplingPill, { flex: 1, alignItems: 'center', paddingVertical: 4, backgroundColor: '#1e293b', borderColor: '#475569', borderWidth: 1 }]}
                    onPress={() => handleApplyPresetRouting('local_airgap')}
                  >
                    <Text style={{ fontSize: 9, fontWeight: 'bold', color: '#cbd5e1' }}>100% Local</Text>
                  </TouchableOpacity>
                </View>

                {/* Individual Task Rows */}
                {[
                  {
                    key: 'frontier_audit',
                    label: 'Frontier Meta-Verification',
                    options: [
                      { id: 'gemini_web', text: 'Gemini AI+ ($0)' },
                      { id: 'agy_prepaid', text: 'AGY CLI' },
                      { id: 'coordinator', text: 'Local 9B Q8' }
                    ]
                  },
                  {
                    key: 'interactive_chat',
                    label: 'Interactive Cockpit Chat',
                    options: [
                      { id: 'coordinator', text: '9B Q8' },
                      { id: 'worker', text: '9B Q4' },
                      { id: 'gemini_web', text: 'Gemini AI+' },
                      { id: 'agy_prepaid', text: 'AGY CLI' }
                    ]
                  },
                  {
                    key: 'sleep_rumination',
                    label: 'Sleep Rumination Consolidation',
                    options: [
                      { id: 'unified_35b_moe', text: '35B MoE' },
                      { id: 'gemini_web', text: 'Gemini AI+' },
                      { id: 'coordinator', text: '9B Q8' }
                    ]
                  },
                  {
                    key: 'autonomous_solving',
                    label: 'Autonomous Solving (Tier 2)',
                    options: [
                      { id: 'coordinator', text: '9B Q8' },
                      { id: 'unified_35b_moe', text: '35B MoE' },
                      { id: 'gemini_web', text: 'Gemini AI+' }
                    ]
                  },
                  {
                    key: 'autonomous_ideation',
                    label: 'Autonomous Ideation (Tier 3)',
                    options: [
                      { id: 'worker', text: '9B Q4 (Fast)' },
                      { id: 'coordinator', text: '9B Q8' }
                    ]
                  },
                  {
                    key: 'subagent_default',
                    label: 'HiveMind Subagents Default',
                    options: [
                      { id: 'worker', text: '9B Q4' },
                      { id: 'coordinator', text: '9B Q8' }
                    ]
                  }
                ].map((task) => {
                  const currentVal = taskRouting[task.key as keyof TaskRouting] || task.options[0].id;
                  return (
                    <View key={task.key} style={{ marginBottom: 5 }}>
                      <Text style={{ fontSize: 9, color: '#94a3b8', marginBottom: 2 }}>{task.label}</Text>
                      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4 }}>
                        {task.options.map((opt) => {
                          const active = currentVal === opt.id;
                          return (
                            <TouchableOpacity
                              key={opt.id}
                              style={[
                                styles.samplingPill,
                                active && { backgroundColor: '#0284c7', borderColor: '#38bdf8', borderWidth: 1 }
                              ]}
                              onPress={() => handleUpdateTaskRouting({ [task.key]: opt.id })}
                            >
                              <Text style={[
                                styles.samplingPillText,
                                active && { color: '#ffffff', fontWeight: 'bold' }
                              ]}>
                                {opt.text}
                              </Text>
                            </TouchableOpacity>
                          );
                        })}
                      </View>
                    </View>
                  );
                })}
              </View>

              {/* Custom Instruction Input */}
              <Text style={styles.inputSectionLabel}>CUSTOM INSTRUCTION / RESEARCH HYPOTHESIS</Text>
              <TextInput
                style={[styles.textInput, { height: 75, textAlignVertical: 'top', fontSize: 12, marginBottom: 10 }]}
                placeholder="e.g. Audit smart home climate anomaly logs, or test rotary embedding drift under 8k context..."
                placeholderTextColor="#64748b"
                value={customInstruction}
                onChangeText={setCustomInstruction}
                multiline
              />

              {/* Domain Selector */}
              <Text style={styles.inputSectionLabel}>EXPLORATION FOCUS DOMAIN</Text>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
                {[
                  { label: 'Algorithmic Reasoning', key: 'algorithmic_reasoning' },
                  { label: 'Concurrency & ABA', key: 'concurrency_and_aba_hazards' },
                  { label: 'Dynamic Symmetry', key: 'spatial_and_dynamic_symmetry' },
                  { label: 'Kernel Coherence', key: 'low_level_kernel_coherence' },
                  { label: 'Ambient Vigilance', key: 'ambient_home_vigilance' },
                  { label: 'Curiosity Auto-Rotate', key: 'autonomous_curiosity' }
                ].map((d) => (
                  <TouchableOpacity
                    key={d.key}
                    style={[styles.samplingPill, thinkingDomain === d.key && styles.samplingPillActive]}
                    onPress={() => setThinkingDomain(d.key)}
                  >
                    <Text style={[styles.samplingPillText, thinkingDomain === d.key && styles.samplingPillTextActive]}>
                      {d.label}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>

              {/* Loop Interval & Priority */}
              <View style={{ flexDirection: 'row', gap: 10, marginBottom: 10 }}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.inputSectionLabel}>LOOP INTERVAL</Text>
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4 }}>
                    {[0, 60, 120, 300, 600].map((sec) => (
                      <TouchableOpacity
                        key={sec}
                        style={[styles.samplingPill, thinkingInterval === sec && styles.samplingPillActive]}
                        onPress={() => setThinkingInterval(sec)}
                      >
                        <Text style={[styles.samplingPillText, thinkingInterval === sec && styles.samplingPillTextActive]}>
                          {sec === 0 ? '⚡ 0s (Continuous)' : `${sec}s`}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>

                <View style={{ flex: 1 }}>
                  <Text style={styles.inputSectionLabel}>PRIORITY</Text>
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4 }}>
                    {['normal', 'high', 'urgent'].map((pr) => (
                      <TouchableOpacity
                        key={pr}
                        style={[styles.samplingPill, thinkingPriority === pr && styles.samplingPillActive]}
                        onPress={() => setThinkingPriority(pr)}
                      >
                        <Text style={[styles.samplingPillText, thinkingPriority === pr && styles.samplingPillTextActive]}>
                          {pr.toUpperCase()}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>
              </View>

              {/* Feedback Message */}
              {loopActionMessage && (
                <Text style={{ color: loopActionMessage.startsWith('✓') ? '#34d399' : '#38bdf8', fontSize: 11, marginVertical: 6 }}>
                  {loopActionMessage}
                </Text>
              )}
            </ScrollView>

            {/* Loop Actions */}
            <View style={{ gap: 8, marginTop: 10 }}>
              <View style={{ flexDirection: 'row', gap: 8 }}>
                <TouchableOpacity
                  style={[styles.modalButton, { flex: 1, backgroundColor: '#4f46e5', alignItems: 'center' }]}
                  onPress={handleRunSingleCycle}
                  disabled={isLoopActionPending}
                >
                  <Text style={styles.modalButtonText}>🚀 Run Single Cycle</Text>
                </TouchableOpacity>

                {thinkingStatus?.is_running ? (
                  <TouchableOpacity
                    style={[styles.modalButton, { flex: 1, backgroundColor: '#dc2626', alignItems: 'center' }]}
                    onPress={handleStopLoop}
                    disabled={isLoopActionPending}
                  >
                    <Text style={styles.modalButtonText}>⏹ Stop 24/7 Loop</Text>
                  </TouchableOpacity>
                ) : (
                  <TouchableOpacity
                    style={[styles.modalButton, { flex: 1, backgroundColor: '#16a34a', alignItems: 'center' }]}
                    onPress={handleStartLoop}
                    disabled={isLoopActionPending}
                  >
                    <Text style={styles.modalButtonText}>▶ Start 24/7 Loop</Text>
                  </TouchableOpacity>
                )}
              </View>

              <TouchableOpacity
                style={[styles.modalButton, { backgroundColor: '#334155', alignItems: 'center' }]}
                onPress={() => setThinkingModalVisible(false)}
              >
                <Text style={styles.modalButtonText}>Close</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Modal: Vector Memory Search */}
      <Modal visible={memoryModalVisible} transparent animationType="slide">
        <View style={styles.modalBackdrop}>
          <View style={[styles.modalCard, { maxHeight: '80%' }]}>
            <Text style={styles.modalTitle}>🔍 Qdrant Memory Search</Text>
            <Text style={styles.modalSubtitle}>
              Hardware BGE-Large embeddings against autonomous dossiers.
            </Text>

            <View style={{ flexDirection: 'row', gap: 8, marginVertical: 10 }}>
              <TextInput
                style={[styles.textInput, { flex: 1 }]}
                placeholder="Search dossiers, failure modes..."
                placeholderTextColor="#64748b"
                value={memoryQuery}
                onChangeText={setMemoryQuery}
              />
              <TouchableOpacity
                style={[styles.sendButton, { height: 44, paddingHorizontal: 16 }]}
                onPress={handleSearchMemory}
              >
                <Text style={styles.sendButtonText}>Search</Text>
              </TouchableOpacity>
            </View>

            {isSearchingMemory && <ActivityIndicator color="#38bdf8" style={{ marginVertical: 10 }} />}

            <ScrollView style={{ marginTop: 8 }}>
              {memoryResults.map((r, idx) => (
                <View key={idx} style={styles.memoryResultCard}>
                  <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                    <Text style={styles.memoryResultTitle}>{r.title}</Text>
                    <Text style={styles.memoryResultScore}>{Math.round(r.score * 100)}% sim</Text>
                  </View>
                  <Text style={styles.memoryResultPreview}>{r.preview}</Text>
                </View>
              ))}
            </ScrollView>

            <TouchableOpacity
              style={[styles.modalButton, { backgroundColor: '#334155', marginTop: 12 }]}
              onPress={() => setMemoryModalVisible(false)}
            >
              <Text style={styles.modalButtonText}>Close</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* Modal: Live 24/7 Agent & Inter-Model Stream Monitor */}
      <Modal visible={liveStreamModalVisible} transparent animationType="slide">
        <View style={styles.modalBackdrop}>
          <View style={[styles.modalCard, { height: '92%', maxHeight: '92%' }]}>
            {/* Modal Top Bar */}
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <View style={[styles.statusDot, { backgroundColor: thinkingStatus?.is_running ? '#10b981' : '#f59e0b' }]} />
                <Text style={styles.modalTitle}>📡 Live Stream & Agent Monitor</Text>
              </View>
              <TouchableOpacity
                style={{
                  flexDirection: 'row',
                  alignItems: 'center',
                  gap: 4,
                  paddingVertical: 4,
                  paddingHorizontal: 8,
                  borderRadius: 4,
                  backgroundColor: isSyncingFeed ? '#1e293b' : 'transparent'
                }}
                onPress={handleSyncFeed}
                disabled={isSyncingFeed}
              >
                {isSyncingFeed ? (
                  <ActivityIndicator size="small" color="#38bdf8" />
                ) : (
                  <Text style={{ fontSize: 13 }}>🔄</Text>
                )}
                <Text style={{ color: '#38bdf8', fontSize: 12, fontWeight: 'bold' }}>
                  {isSyncingFeed ? 'Syncing...' : 'Sync Feed'}
                </Text>
              </TouchableOpacity>
            </View>

            {/* Status & Measurables Pill Bar */}
            <View style={[styles.modalCodeBox, { marginVertical: 6, padding: 8, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }]}>
              <Text style={{ color: '#94a3b8', fontSize: 11 }}>
                Loop: <Text style={{ color: thinkingStatus?.is_running ? '#34d399' : '#facc15', fontWeight: 'bold' }}>
                  {thinkingStatus?.is_running ? '● 24/7 ACTIVE' : '○ IDLE'}
                </Text>
              </Text>
              <Text style={{ color: '#94a3b8', fontSize: 11 }}>
                Cycles: <Text style={{ color: '#ffffff', fontWeight: 'bold' }}>{thinkingStatus?.total_cycles || 0}</Text>
              </Text>
              <Text style={{ color: '#94a3b8', fontSize: 11 }}>
                Tokens: <Text style={{ color: '#ffffff', fontWeight: 'bold' }}>{thinkingStatus?.total_tokens ? `${Math.round(thinkingStatus.total_tokens / 1000)}k` : '0'}</Text>
              </Text>
              <Text style={{ color: '#94a3b8', fontSize: 11 }}>
                Agents: <Text style={{ color: '#a78bfa', fontWeight: 'bold' }}>{activeAgents.length}</Text>
              </Text>
            </View>

            {/* Monitor Navigation Tabs */}
            <View style={{ flexDirection: 'row', gap: 6, marginBottom: 8 }}>
              <TouchableOpacity
                style={[styles.modelTab, liveMonitorTab === 'stream' && styles.modelTabActive]}
                onPress={() => setLiveMonitorTab('stream')}
              >
                <Text style={[styles.modelTabTitle, liveMonitorTab === 'stream' && styles.modelTabTitleActive]}>
                  ⚡ Stream of Thought
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modelTab, liveMonitorTab === 'agents' && styles.modelTabActive]}
                onPress={() => setLiveMonitorTab('agents')}
              >
                <Text style={[styles.modelTabTitle, liveMonitorTab === 'agents' && styles.modelTabTitleActive]}>
                  🤖 Subagents ({activeAgents.length})
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modelTab, liveMonitorTab === 'spawn' && styles.modelTabActive]}
                onPress={() => setLiveMonitorTab('spawn')}
              >
                <Text style={[styles.modelTabTitle, liveMonitorTab === 'spawn' && styles.modelTabTitleActive]}>
                  ➕ Commission
                </Text>
              </TouchableOpacity>
            </View>

            {/* TAB 1: Real-Time Stream of Thought */}
            {liveMonitorTab === 'stream' && (
              <View style={{ flex: 1 }}>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <Text style={styles.inputSectionLabel}>REAL-TIME DUAL-GPU REASONING & TELEMETRY</Text>
                  <TouchableOpacity
                    style={[styles.samplingPill, { backgroundColor: isLiveCycling ? '#475569' : '#0284c7' }]}
                    onPress={handleRunLiveCycle}
                    disabled={isLiveCycling}
                  >
                    <Text style={[styles.samplingPillText, { color: '#ffffff', fontWeight: 'bold' }]}>
                      {isLiveCycling ? '⚡ Executing Cycle...' : '⚡ Trigger Live Cycle'}
                    </Text>
                  </TouchableOpacity>
                </View>

                <ScrollView
                  style={{ flex: 1, backgroundColor: '#090d16', borderRadius: 8, padding: 8 }}
                  refreshControl={
                    <RefreshControl
                      refreshing={isSyncingFeed}
                      onRefresh={handleSyncFeed}
                      colors={['#38bdf8']}
                      tintColor="#38bdf8"
                    />
                  }
                >
                  {liveEvents.length === 0 ? (
                    <Text style={{ color: '#64748b', fontSize: 11, fontStyle: 'italic', textAlign: 'center', marginTop: 24 }}>
                      Listening to cluster stream... No recent events logged yet. Tap 'Trigger Live Cycle' or wait for the 24/7 background loop.
                    </Text>
                  ) : (
                    liveEvents.map((evt) => (
                      <View key={evt.id} style={styles.liveEventItem}>
                        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
                          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                            <View
                              style={[
                                styles.categoryBadge,
                                evt.category === 'cycle_result'
                                  ? { backgroundColor: '#1e3a8a' }
                                  : evt.category === 'agent_milestone'
                                  ? { backgroundColor: '#14532d' }
                                  : evt.category === 'cycle_step'
                                  ? { backgroundColor: '#78350f' }
                                  : { backgroundColor: '#334155' }
                              ]}
                            >
                              <Text style={styles.categoryBadgeText}>{evt.category.toUpperCase()}</Text>
                            </View>
                            <Text style={styles.liveEventSource}>{evt.source}</Text>
                          </View>
                          <Text style={styles.liveEventTime}>{evt.timestamp}</Text>
                        </View>
                        <Text style={styles.liveEventMessage}>{evt.message}</Text>
                      </View>
                    ))
                  )}
                </ScrollView>
              </View>
            )}

            {/* TAB 2: Active Background Agents Rack with Collapsible Tabs */}
            {liveMonitorTab === 'agents' && (
              <View style={{ flex: 1 }}>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <Text style={styles.inputSectionLabel}>COLLAPSIBLE AGENT DOSSIERS & MEASURABLES</Text>
                  <TouchableOpacity
                    style={[styles.samplingPill, { backgroundColor: '#0284c7' }]}
                    onPress={() => setLiveMonitorTab('spawn')}
                  >
                    <Text style={[styles.samplingPillText, { color: '#ffffff', fontWeight: 'bold' }]}>
                      ➕ Commission Agent
                    </Text>
                  </TouchableOpacity>
                </View>

                <ScrollView
                  style={{ flex: 1 }}
                  refreshControl={
                    <RefreshControl
                      refreshing={isSyncingFeed}
                      onRefresh={handleSyncFeed}
                      colors={['#38bdf8']}
                      tintColor="#38bdf8"
                    />
                  }
                >
                  {activeAgents.length === 0 ? (
                    <Text style={{ color: '#64748b', fontSize: 11, fontStyle: 'italic', textAlign: 'center', marginTop: 24 }}>
                      No persistent subagents currently commissioned in HiveMind.
                    </Text>
                  ) : (
                    activeAgents.map((ag) => {
                      const isExpanded = !!expandedAgents[ag.agent_id];
                      const progressPct = ag.max_iterations > 0 ? Math.min(100, Math.round((ag.current_iteration / ag.max_iterations) * 100)) : 0;
                      return (
                        <View key={ag.agent_id} style={styles.agentCard}>
                          {/* Collapsible Header */}
                          <TouchableOpacity
                            style={styles.agentCollapsibleHeader}
                            onPress={() => toggleAgentExpand(ag.agent_id)}
                            activeOpacity={0.7}
                          >
                            <View style={{ flex: 1 }}>
                              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                                <Text style={styles.agentName}>{ag.name}</Text>
                                <View
                                  style={[
                                    styles.agentStatusBadge,
                                    ag.status === 'running'
                                      ? { backgroundColor: '#14532d' }
                                      : ag.status === 'completed'
                                      ? { backgroundColor: '#1e3a8a' }
                                      : { backgroundColor: '#334155' }
                                  ]}
                                >
                                  <Text
                                    style={[
                                      styles.agentStatusText,
                                      ag.status === 'running'
                                        ? { color: '#86efac' }
                                        : ag.status === 'completed'
                                        ? { color: '#93c5fd' }
                                        : { color: '#94a3b8' }
                                    ]}
                                  >
                                    {ag.status.toUpperCase()}
                                  </Text>
                                </View>
                              </View>
                              <Text style={styles.agentRole}>
                                {ag.role} • <Text style={{ color: '#38bdf8' }}>{ag.model_preference.toUpperCase()}</Text>
                              </Text>
                              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, flexWrap: 'wrap', marginTop: 4 }}>
                                <View style={[styles.agentStatusBadge, { backgroundColor: '#1e1b4b', paddingHorizontal: 6 }]}>
                                  <Text style={[styles.agentStatusText, { color: '#a5b4fc', fontWeight: 'bold' }]}>
                                    🧬 Gen {ag.lineage?.generation || 1}
                                  </Text>
                                </View>
                                {ag.lineage?.parent_names && ag.lineage.parent_names.length > 0 && (
                                  <View style={[styles.agentStatusBadge, { backgroundColor: '#312e81', paddingHorizontal: 6 }]}>
                                    <Text style={[styles.agentStatusText, { color: '#c7d2fe' }]}>
                                      {ag.lineage.parent_names.join(' × ')}
                                    </Text>
                                  </View>
                                )}
                                {ag.offspring_ids && ag.offspring_ids.length > 0 && (
                                  <View style={[styles.agentStatusBadge, { backgroundColor: '#064e3b', paddingHorizontal: 6 }]}>
                                    <Text style={[styles.agentStatusText, { color: '#6ee7b7' }]}>
                                      🌱 {ag.offspring_ids.length} Offspring
                                    </Text>
                                  </View>
                                )}
                              </View>
                            </View>
                            <View style={{ alignItems: 'flex-end', marginLeft: 8 }}>
                              <Text style={{ fontSize: 11, color: '#38bdf8', fontWeight: 'bold' }}>
                                {ag.current_iteration}/{ag.max_iterations} ({progressPct}%)
                              </Text>
                              <Text style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
                                {isExpanded ? '▲ Hide Details' : '▼ View Dossier'}
                              </Text>
                            </View>
                          </TouchableOpacity>

                          {/* Progress Bar */}
                          <View style={{ height: 4, backgroundColor: '#090d16', borderRadius: 2, overflow: 'hidden', marginVertical: 6 }}>
                            <View style={{ height: '100%', width: `${progressPct}%`, backgroundColor: '#38bdf8' }} />
                          </View>

                          {/* Collapsed Brief Summary */}
                          {!isExpanded && (
                            <Text style={styles.agentMission} numberOfLines={2}>
                              {ag.mission}
                            </Text>
                          )}

                          {/* Expanded Full Dossier (Measurables, Goals, Prompt, History) */}
                          {isExpanded && (
                            <View style={styles.agentDetailSection}>
                              {/* Goals & Measurables */}
                              <Text style={styles.agentDetailLabel}>MISSION & ONGOING SCOPE</Text>
                              <Text style={styles.agentDetailValue}>{ag.mission}</Text>

                              {/* Agent System Prompt Directive */}
                              {ag.system_prompt && (
                                <>
                                  <Text style={[styles.agentDetailLabel, { marginTop: 8 }]}>INDIVIDUAL SYSTEM DIRECTIVE / PROMPT</Text>
                                  <View style={[styles.modalCodeBox, { marginVertical: 4, padding: 8 }]}>
                                    <Text style={[styles.modalCodeText, { fontSize: 11, color: '#cbd5e1' }]}>
                                      {ag.system_prompt}
                                    </Text>
                                  </View>
                                </>
                              )}

                              {/* Measurables Card */}
                              <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
                                <View style={[styles.modalCodeBox, { flex: 1, padding: 6, marginVertical: 0 }]}>
                                  <Text style={{ fontSize: 10, color: '#94a3b8' }}>Agent ID:</Text>
                                  <Text style={{ fontSize: 11, color: '#38bdf8', fontWeight: 'bold' }}>{ag.agent_id}</Text>
                                </View>
                                <View style={[styles.modalCodeBox, { flex: 1, padding: 6, marginVertical: 0 }]}>
                                  <Text style={{ fontSize: 10, color: '#94a3b8' }}>Compute Host:</Text>
                                  <Text style={{ fontSize: 11, color: '#38bdf8', fontWeight: 'bold' }}>
                                    {ag.model_preference === 'worker' ? 'RX 6600 XT (:8002)' : 'RX 6750 XT (:8001)'}
                                  </Text>
                                </View>
                              </View>

                              {/* Milestone History & Outputs */}
                              <Text style={[styles.agentDetailLabel, { marginTop: 10 }]}>
                                ITERATION OUTPUTS & REASONING HISTORY ({ag.history?.length || 0})
                              </Text>
                              {(!ag.history || ag.history.length === 0) ? (
                                <Text style={{ fontSize: 11, color: '#64748b', fontStyle: 'italic', marginTop: 4 }}>
                                  Awaiting execution in the 24/7 autonomous loop...
                                </Text>
                              ) : (
                                ag.history.map((h, hIdx) => (
                                  <View key={hIdx} style={[styles.modalCodeBox, { marginVertical: 4, padding: 8, backgroundColor: '#090d16' }]}>
                                    <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 }}>
                                      <Text style={{ color: '#34d399', fontSize: 11, fontWeight: 'bold' }}>
                                        Milestone #{h.iteration}
                                      </Text>
                                      <Text style={{ color: '#64748b', fontSize: 10 }}>
                                        {h.tokens ? `${h.tokens} tokens • ` : ''}{h.timestamp ? new Date(h.timestamp).toLocaleTimeString() : ''}
                                      </Text>
                                    </View>
                                    <Text style={{ color: '#e2e8f0', fontSize: 11, lineHeight: 16 }}>
                                      {h.summary}
                                    </Text>
                                    {h.distilled_invariant ? (
                                      <Text style={{ color: '#38bdf8', fontSize: 10, marginTop: 4, fontStyle: 'italic' }}>
                                        Invariant: {h.distilled_invariant}
                                      </Text>
                                    ) : null}
                                    <TouchableOpacity
                                      style={{ marginTop: 6, alignSelf: 'flex-start', backgroundColor: '#1e293b', paddingVertical: 4, paddingHorizontal: 8, borderRadius: 4, borderWidth: 1, borderColor: '#334155' }}
                                      onPress={() => setSelectedMilestone({ agentName: ag.name, ...h })}
                                    >
                                      <Text style={{ color: '#38bdf8', fontSize: 10, fontWeight: 'bold' }}>
                                        📖 View Full Output & Tools →
                                      </Text>
                                    </TouchableOpacity>
                                  </View>
                                ))
                              )}

                              {/* Action Footer */}
                              <View style={{ flexDirection: 'row', justifyContent: 'flex-end', gap: 8, marginTop: 10 }}>
                                <TouchableOpacity
                                  style={[styles.harnessBtn, { backgroundColor: '#4f46e5', paddingVertical: 5, paddingHorizontal: 12 }]}
                                  onPress={() => handleStartReproduction(ag)}
                                >
                                  <Text style={{ color: '#ffffff', fontSize: 11, fontWeight: 'bold' }}>🧬 Blend / Reproduce</Text>
                                </TouchableOpacity>
                                {ag.status === 'running' && (
                                  <TouchableOpacity
                                    style={[styles.harnessBtn, { backgroundColor: '#7f1d1d', paddingVertical: 5, paddingHorizontal: 12 }]}
                                    onPress={() => handleStopAgent(ag.agent_id)}
                                  >
                                    <Text style={{ color: '#fca5a5', fontSize: 11, fontWeight: 'bold' }}>⏹ Stop Agent</Text>
                                  </TouchableOpacity>
                                )}
                              </View>
                            </View>
                          )}
                        </View>
                      );
                    })
                  )}
                </ScrollView>
              </View>
            )}

            {/* TAB 3: Commission Subagent Form */}
            {liveMonitorTab === 'spawn' && (
              <ScrollView style={{ flex: 1 }}>
                <Text style={styles.inputSectionLabel}>COMMISSION PERSISTENT BACKGROUND SUBAGENT</Text>
                
                {/* Fast Preset & Cloning Bar */}
                <View style={{ flexDirection: 'row', gap: 6, marginVertical: 8 }}>
                  <TouchableOpacity
                    style={[
                      styles.harnessBtn,
                      { flex: 1, backgroundColor: showClonePicker ? '#4f46e5' : '#1e293b', borderColor: '#475569', borderWidth: 1, paddingVertical: 6, alignItems: 'center' }
                    ]}
                    onPress={() => {
                      setShowClonePicker(!showClonePicker);
                      setShowPresetPicker(false);
                    }}
                  >
                    <Text style={{ color: '#f8fafc', fontSize: 11, fontWeight: 'bold' }}>
                      📋 Clone Existing ({activeAgents.length})
                    </Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={[
                      styles.harnessBtn,
                      { flex: 1, backgroundColor: showPresetPicker ? '#059669' : '#1e293b', borderColor: '#475569', borderWidth: 1, paddingVertical: 6, alignItems: 'center' }
                    ]}
                    onPress={() => {
                      setShowPresetPicker(!showPresetPicker);
                      setShowClonePicker(false);
                    }}
                  >
                    <Text style={{ color: '#f8fafc', fontSize: 11, fontWeight: 'bold' }}>
                      ⭐ Load Preset ({HOMELAB_AGENT_PRESETS.length})
                    </Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={[
                      styles.harnessBtn,
                      { backgroundColor: '#334155', paddingHorizontal: 10, paddingVertical: 6, alignItems: 'center' }
                    ]}
                    onPress={handleResetSpawnForm}
                  >
                    <Text style={{ color: '#94a3b8', fontSize: 11 }}>🔄 Reset</Text>
                  </TouchableOpacity>
                </View>

                {/* Dropdown 1: Clone from Existing Agent */}
                {showClonePicker && (
                  <View style={[styles.modalCodeBox, { backgroundColor: '#090d16', borderColor: '#4f46e5', borderWidth: 1, padding: 8, marginBottom: 10 }]}>
                    <Text style={{ color: '#a5b4fc', fontSize: 11, fontWeight: 'bold', marginBottom: 6 }}>
                      Select Active Agent to Fork / Clone Parameters:
                    </Text>
                    {activeAgents.length === 0 ? (
                      <Text style={{ color: '#64748b', fontSize: 11, fontStyle: 'italic' }}>No active agents available to clone.</Text>
                    ) : (
                      activeAgents.map((ag) => (
                        <TouchableOpacity
                          key={ag.agent_id}
                          style={{
                            padding: 8,
                            marginVertical: 3,
                            backgroundColor: '#1e1b4b',
                            borderRadius: 6,
                            borderWidth: 1,
                            borderColor: '#3730a3'
                          }}
                          onPress={() => handleCloneAgent(ag)}
                        >
                          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                            <Text style={{ color: '#ffffff', fontWeight: 'bold', fontSize: 12 }}>{ag.name}</Text>
                            <Text style={{ color: '#a5b4fc', fontSize: 10 }}>Gen {ag.lineage?.generation || 1}</Text>
                          </View>
                          <Text style={{ color: '#c7d2fe', fontSize: 10, marginTop: 2 }}>{ag.role}</Text>
                          <Text style={{ color: '#94a3b8', fontSize: 9, marginTop: 2 }} numberOfLines={1}>{ag.mission}</Text>
                        </TouchableOpacity>
                      ))
                    )}
                  </View>
                )}

                {/* Dropdown 2: Homelab Curated Presets */}
                {showPresetPicker && (
                  <View style={[styles.modalCodeBox, { backgroundColor: '#064e3b', borderColor: '#10b981', borderWidth: 1, padding: 8, marginBottom: 10 }]}>
                    <Text style={{ color: '#a7f3d0', fontSize: 11, fontWeight: 'bold', marginBottom: 6 }}>
                      Choose Homelab Archetype Preset:
                    </Text>
                    {HOMELAB_AGENT_PRESETS.map((preset) => (
                      <TouchableOpacity
                        key={preset.id}
                        style={{
                          padding: 8,
                          marginVertical: 3,
                          backgroundColor: '#022c22',
                          borderRadius: 6,
                          borderWidth: 1,
                          borderColor: '#059669'
                        }}
                        onPress={() => handleLoadPreset(preset)}
                      >
                        <Text style={{ color: '#ffffff', fontWeight: 'bold', fontSize: 12 }}>{preset.title}</Text>
                        <Text style={{ color: '#6ee7b7', fontSize: 10, marginTop: 2 }}>{preset.role}</Text>
                        <Text style={{ color: '#94a3b8', fontSize: 9, marginTop: 2 }} numberOfLines={1}>{preset.mission}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                )}
                
                <Text style={styles.paramLabel}>Subagent Name</Text>
                <TextInput
                  style={[styles.textInput, { height: 40, marginBottom: 8 }]}
                  placeholder="e.g. VulkanMemoryAuditor, ConcurrencySpecialist"
                  placeholderTextColor="#64748b"
                  value={newAgentName}
                  onChangeText={setNewAgentName}
                />

                <Text style={styles.paramLabel}>Specialized Role</Text>
                <TextInput
                  style={[styles.textInput, { height: 40, marginBottom: 8 }]}
                  placeholder="e.g. Asynchronous Rust & GPU Memory Engineer"
                  placeholderTextColor="#64748b"
                  value={newAgentRole}
                  onChangeText={setNewAgentRole}
                />

                <Text style={styles.paramLabel}>Mission Objective & Scope</Text>
                <TextInput
                  style={[styles.textInput, { height: 65, textAlignVertical: 'top', fontSize: 12, marginBottom: 8 }]}
                  placeholder="e.g. Continuously audit dual-GPU VRAM buffer synchronization and log invariants to Qdrant..."
                  placeholderTextColor="#64748b"
                  value={newAgentMission}
                  onChangeText={setNewAgentMission}
                  multiline
                />

                <Text style={styles.paramLabel}>System Prompt (Custom Persona Directives & Invariants)</Text>
                <TextInput
                  style={[styles.textInput, { height: 95, textAlignVertical: 'top', fontSize: 11, lineHeight: 16, marginBottom: 10, borderColor: '#6366f1' }]}
                  placeholder="e.g. You are an autonomous specialist... Rigorously investigate hardware tolerances, utilize available research tools, and synthesize verified discoveries into eternal memory."
                  placeholderTextColor="#64748b"
                  value={newAgentSystemPrompt}
                  onChangeText={setNewAgentSystemPrompt}
                  multiline
                />

                {/* Model Preference */}
                <Text style={styles.paramLabel}>Model Preference</Text>
                <View style={{ flexDirection: 'row', gap: 8, marginBottom: 10 }}>
                  <TouchableOpacity
                    style={[styles.samplingPill, { flex: 1, paddingVertical: 8, alignItems: 'center' }, newAgentModel === 'worker' && styles.samplingPillActive]}
                    onPress={() => setNewAgentModel('worker')}
                  >
                    <Text style={[styles.samplingPillText, newAgentModel === 'worker' && styles.samplingPillTextActive]}>
                      Worker (Ornith 9B Q4 - 80+ t/s)
                    </Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.samplingPill, { flex: 1, paddingVertical: 8, alignItems: 'center' }, newAgentModel === 'coordinator' && styles.samplingPillActive]}
                    onPress={() => setNewAgentModel('coordinator')}
                  >
                    <Text style={[styles.samplingPillText, newAgentModel === 'coordinator' && styles.samplingPillTextActive]}>
                      Coordinator (Ornith 9B Q8 Master)
                    </Text>
                  </TouchableOpacity>
                </View>

                {/* Max Iterations */}
                <Text style={styles.paramLabel}>
                  Max Iterations: {newAgentMaxIter === 0 ? '∞ Infinite (Recursive)' : `${newAgentMaxIter} Cycles`}
                </Text>
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 14 }}>
                  {[0, 3, 5, 10].map((num) => (
                    <TouchableOpacity
                      key={num}
                      style={[styles.samplingPill, newAgentMaxIter === num && styles.samplingPillActive]}
                      onPress={() => setNewAgentMaxIter(num)}
                    >
                      <Text style={[styles.samplingPillText, newAgentMaxIter === num && styles.samplingPillTextActive]}>
                        {num === 0 ? '∞ Infinite (Recursive)' : `${num} Cycles`}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>

                <TouchableOpacity
                  style={[styles.modalButton, { backgroundColor: '#10b981', alignItems: 'center' }]}
                  onPress={handleSpawnAgentSubmit}
                  disabled={isSpawningAgent}
                >
                  <Text style={styles.modalButtonText}>
                    {isSpawningAgent ? 'Commissioning...' : '🚀 Commission Subagent into HiveMind'}
                  </Text>
                </TouchableOpacity>
              </ScrollView>
            )}

            {/* Modal Footer */}
            <TouchableOpacity
              style={[styles.modalButton, { backgroundColor: '#334155', marginTop: 8, alignItems: 'center' }]}
              onPress={() => setLiveStreamModalVisible(false)}
            >
              <Text style={styles.modalButtonText}>Close Monitor</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* Modal: Digital Person Reproduction & Genetic Crossover */}
      <Modal visible={reproduceModalVisible} transparent animationType="slide">
        <View style={styles.modalBackdrop}>
          <View style={[styles.modalCard, { maxHeight: '92%' }]}>
            {/* Header */}
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <Text style={{ fontSize: 18 }}>🧬</Text>
                <Text style={styles.modalTitle}>
                  {reproduceStep === 'select' ? 'Digital Reproduction (Step 1/2)' : 'Edit Persona & Prompt (Step 2/2)'}
                </Text>
              </View>
              <View style={[styles.samplingPill, { backgroundColor: reproduceStep === 'select' ? '#1e1b4b' : '#064e3b' }]}>
                <Text style={[styles.samplingPillText, { color: reproduceStep === 'select' ? '#a5b4fc' : '#6ee7b7', fontWeight: 'bold' }]}>
                  {reproduceStep === 'select' ? '1. Partner Selection' : '2. Custom Directives'}
                </Text>
              </View>
            </View>

            <Text style={[styles.modalSubtitle, { marginBottom: 8 }]}>
              {reproduceStep === 'select'
                ? 'Select a genetic partner and crossover intent across dual GPUs (Worker :8002 & Coordinator :8001).'
                : 'Fine-tune the blended digital person’s name, role, mission, and system prompt before commissioning.'}
            </Text>

            <ScrollView
              style={{ flex: 1 }}
              nestedScrollEnabled={true}
              keyboardShouldPersistTaps="handled"
              showsVerticalScrollIndicator={true}
            >
              {/* STEP 1: Partner Selection & Guiding Intent */}
              {reproduceStep === 'select' && (
                <>
                  {/* Parent Archetype A Card */}
                  <Text style={styles.paramLabel}>Parent Archetype A (Primary Origin)</Text>
                  <View style={[styles.modalCodeBox, { padding: 10, marginVertical: 4, borderColor: '#6366f1', borderWidth: 1, backgroundColor: '#1e1b4b' }]}>
                    <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Text style={{ color: '#a5b4fc', fontWeight: 'bold', fontSize: 13 }}>
                        {reproduceParentA?.name} (Gen {reproduceParentA?.lineage?.generation || 1})
                      </Text>
                      <View style={[styles.agentStatusBadge, { backgroundColor: '#312e81' }]}>
                        <Text style={{ color: '#c7d2fe', fontSize: 10 }}>
                          {reproduceParentA?.model_preference?.toUpperCase()}
                        </Text>
                      </View>
                    </View>
                    <Text style={{ color: '#c7d2fe', fontSize: 11, marginTop: 2 }}>{reproduceParentA?.role}</Text>
                    <Text style={{ color: '#cbd5e1', fontSize: 11, marginTop: 4 }} numberOfLines={2}>
                      {reproduceParentA?.mission}
                    </Text>
                  </View>

                  {/* Partner / Parent B Selector List */}
                  <Text style={[styles.paramLabel, { marginTop: 10 }]}>Select Partner / Parent Archetype B</Text>
                  <View style={{ gap: 6, marginVertical: 6 }}>
                    {activeAgents.filter((a) => a.agent_id !== reproduceParentA?.agent_id).length === 0 ? (
                      <Text style={{ color: '#64748b', fontSize: 11, fontStyle: 'italic', padding: 8 }}>
                        No other active agents available to mate. Commission at least one more agent first.
                      </Text>
                    ) : (
                      activeAgents
                        .filter((a) => a.agent_id !== reproduceParentA?.agent_id)
                        .map((ag) => {
                          const isSelected = reproduceParentBId === ag.agent_id;
                          const eligibility = isEligiblePartner(reproduceParentA, ag);
                          return (
                            <TouchableOpacity
                              key={ag.agent_id}
                              activeOpacity={0.7}
                              style={[
                                styles.modalCodeBox,
                                {
                                  padding: 10,
                                  marginVertical: 2,
                                  backgroundColor: isSelected ? '#1e1b4b' : '#090d16',
                                  borderColor: isSelected ? '#818cf8' : eligibility.eligible ? '#334155' : '#7f1d1d',
                                  borderWidth: isSelected ? 2 : 1
                                }
                              ]}
                              onPress={() => handleSelectParentB(ag.agent_id)}
                            >
                              <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                                  <Text style={{ fontSize: 14 }}>{isSelected ? '🔘' : '⚪'}</Text>
                                  <Text style={{ color: isSelected ? '#ffffff' : '#e2e8f0', fontWeight: 'bold', fontSize: 12 }}>
                                    {ag.name} (Gen {ag.lineage?.generation || 1})
                                  </Text>
                                </View>
                                <View style={{ flexDirection: 'row', gap: 4, alignItems: 'center' }}>
                                  {!eligibility.eligible && (
                                    <View style={[styles.agentStatusBadge, { backgroundColor: '#450a0a' }]}>
                                      <Text style={{ color: '#fca5a5', fontSize: 9 }}>MATED / SIBLING</Text>
                                    </View>
                                  )}
                                  <View style={[styles.agentStatusBadge, { backgroundColor: isSelected ? '#3730a3' : '#1e293b' }]}>
                                    <Text style={{ color: isSelected ? '#c7d2fe' : '#94a3b8', fontSize: 10 }}>
                                      {ag.model_preference?.toUpperCase()}
                                    </Text>
                                  </View>
                                </View>
                              </View>
                              <Text style={{ color: isSelected ? '#a5b4fc' : '#94a3b8', fontSize: 11, marginTop: 3 }}>
                                {ag.role}
                              </Text>
                              <Text style={{ color: '#cbd5e1', fontSize: 10, marginTop: 2 }} numberOfLines={1}>
                                {ag.mission}
                              </Text>
                            </TouchableOpacity>
                          );
                        })
                    )}
                  </View>

                  {/* Guided Crossover Intent */}
                  <Text style={[styles.paramLabel, { marginTop: 10 }]}>Guided Crossover Intent / Bias (Optional)</Text>
                  <TextInput
                    style={[styles.textInput, { height: 60, textAlignVertical: 'top', padding: 8 }]}
                    placeholder="e.g. Blend automotive diagnostics with asynchronous VRAM telemetry..."
                    placeholderTextColor="#64748b"
                    multiline
                    value={reproduceFocus}
                    onChangeText={(val) => {
                      setReproduceFocus(val);
                      if (reproduceParentA) {
                        syncReproductionDraft(reproduceParentA, reproduceParentBId, val);
                      }
                    }}
                  />

                  {/* Notice Box */}
                  <View style={[styles.modalCodeBox, { backgroundColor: '#090d16', padding: 8, marginVertical: 8 }]}>
                    <Text style={{ color: '#38bdf8', fontSize: 10, fontWeight: 'bold' }}>
                      ⚡ Digital Crossover Mechanics:
                    </Text>
                    <Text style={{ color: '#94a3b8', fontSize: 10, marginTop: 2 }}>
                      1. Dual GPUs negotiate traits between parent archetypes.{"\n"}
                      2. In Step 2, you have full authority to edit the offspring’s prompt and parameters before commissioning.
                    </Text>
                  </View>

                  {/* Button to Proceed to Step 2 */}
                  <TouchableOpacity
                    style={[
                      styles.modalButton,
                      {
                        backgroundColor: reproduceParentBId ? '#6366f1' : '#334155',
                        alignItems: 'center',
                        marginTop: 6
                      }
                    ]}
                    disabled={!reproduceParentBId}
                    onPress={() => {
                      if (reproduceParentA) {
                        syncReproductionDraft(reproduceParentA, reproduceParentBId, reproduceFocus);
                      }
                      setReproduceStep('preview_edit');
                    }}
                  >
                    <Text style={styles.modalButtonText}>
                      {reproduceParentBId ? '✨ Review & Customize Offspring Prompt ➔' : 'Select a Partner Above'}
                    </Text>
                  </TouchableOpacity>
                </>
              )}

              {/* STEP 2: Full Interactive Offspring Persona & Prompt Editor */}
              {reproduceStep === 'preview_edit' && (
                <>
                  {/* Step 2 Header with Back Button */}
                  <TouchableOpacity
                    style={{
                      flexDirection: 'row',
                      alignItems: 'center',
                      gap: 4,
                      paddingVertical: 6,
                      paddingHorizontal: 10,
                      backgroundColor: '#1e293b',
                      borderRadius: 6,
                      alignSelf: 'flex-start',
                      marginBottom: 10
                    }}
                    onPress={() => setReproduceStep('select')}
                  >
                    <Text style={{ color: '#38bdf8', fontSize: 11, fontWeight: 'bold' }}>
                      ⬅ Back to Partner Selection
                    </Text>
                  </TouchableOpacity>

                  {/* Lineage Info Banner */}
                  <View style={[styles.modalCodeBox, { backgroundColor: '#1e1b4b', borderColor: '#4f46e5', borderWidth: 1, padding: 8, marginBottom: 8 }]}>
                    <Text style={{ color: '#a5b4fc', fontSize: 11, fontWeight: 'bold' }}>
                      🧬 Lineage: {reproduceParentA?.name} × {activeAgents.find((a) => a.agent_id === reproduceParentBId)?.name || 'Partner'}
                    </Text>
                    <Text style={{ color: '#c7d2fe', fontSize: 10, marginTop: 2 }}>
                      Generation {(Math.max(reproduceParentA?.lineage?.generation || 1, activeAgents.find((a) => a.agent_id === reproduceParentBId)?.lineage?.generation || 1)) + 1} Offspring
                    </Text>
                  </View>

                  {/* Offspring Name Input */}
                  <Text style={styles.paramLabel}>Offspring Name</Text>
                  <TextInput
                    style={[styles.textInput, { height: 38, marginBottom: 8 }]}
                    placeholder="Offspring Name"
                    placeholderTextColor="#64748b"
                    value={reproduceChildName}
                    onChangeText={setReproduceChildName}
                  />

                  {/* Offspring Role Input */}
                  <Text style={styles.paramLabel}>Specialized Role</Text>
                  <TextInput
                    style={[styles.textInput, { height: 38, marginBottom: 8 }]}
                    placeholder="e.g. Hybrid Telematics & Vector Memory Specialist"
                    placeholderTextColor="#64748b"
                    value={reproduceChildRole}
                    onChangeText={setReproduceChildRole}
                  />

                  {/* Offspring Mission Objective */}
                  <Text style={styles.paramLabel}>Core Mission Objective</Text>
                  <TextInput
                    style={[styles.textInput, { height: 55, textAlignVertical: 'top', fontSize: 11, marginBottom: 8 }]}
                    placeholder="Synthesize parental invariants and explore..."
                    placeholderTextColor="#64748b"
                    multiline
                    value={reproduceChildMission}
                    onChangeText={setReproduceChildMission}
                  />

                  {/* Initial Focus Question */}
                  <Text style={styles.paramLabel}>Initial Focus Directive / Target Hypothesis</Text>
                  <TextInput
                    style={[styles.textInput, { height: 50, textAlignVertical: 'top', fontSize: 11, marginBottom: 8 }]}
                    placeholder="First milestone target hypothesis..."
                    placeholderTextColor="#64748b"
                    multiline
                    value={reproduceChildFocus}
                    onChangeText={setReproduceChildFocus}
                  />

                  {/* Full Custom System Prompt Input */}
                  <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Text style={styles.paramLabel}>System Prompt (Persona Directives & Invariants)</Text>
                    <TouchableOpacity
                      onPress={() => {
                        if (reproduceParentA) {
                          syncReproductionDraft(reproduceParentA, reproduceParentBId, reproduceFocus);
                        }
                      }}
                    >
                      <Text style={{ color: '#38bdf8', fontSize: 10 }}>↺ Reset to Hybrid</Text>
                    </TouchableOpacity>
                  </View>
                  <TextInput
                    style={[
                      styles.textInput,
                      {
                        height: 130,
                        textAlignVertical: 'top',
                        fontSize: 11,
                        lineHeight: 16,
                        marginBottom: 10,
                        borderColor: '#6366f1'
                      }
                    ]}
                    placeholder="Enter complete customized system prompt for this blended agent..."
                    placeholderTextColor="#64748b"
                    multiline
                    value={reproduceChildPrompt}
                    onChangeText={setReproduceChildPrompt}
                  />

                  {/* Model Preference */}
                  <Text style={styles.paramLabel}>Compute Model Allocation</Text>
                  <View style={{ flexDirection: 'row', gap: 8, marginBottom: 12 }}>
                    <TouchableOpacity
                      style={[
                        styles.samplingPill,
                        { flex: 1, paddingVertical: 8, alignItems: 'center' },
                        reproduceChildModel === 'worker' && styles.samplingPillActive
                      ]}
                      onPress={() => setReproduceChildModel('worker')}
                    >
                      <Text style={[styles.samplingPillText, reproduceChildModel === 'worker' && styles.samplingPillTextActive]}>
                        Worker (Ornith 9B Q4 :8002)
                      </Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={[
                        styles.samplingPill,
                        { flex: 1, paddingVertical: 8, alignItems: 'center' },
                        reproduceChildModel === 'coordinator' && styles.samplingPillActive
                      ]}
                      onPress={() => setReproduceChildModel('coordinator')}
                    >
                      <Text style={[styles.samplingPillText, reproduceChildModel === 'coordinator' && styles.samplingPillTextActive]}>
                        Coordinator (Ornith 9B Q8 :8001)
                      </Text>
                    </TouchableOpacity>
                  </View>

                  {/* Commit Button */}
                  <TouchableOpacity
                    style={[styles.modalButton, { backgroundColor: '#10b981', alignItems: 'center', marginTop: 4 }]}
                    onPress={handleSubmitReproduction}
                    disabled={isReproducing || !reproduceChildName.trim() || !reproduceChildPrompt.trim()}
                  >
                    <Text style={styles.modalButtonText}>
                      {isReproducing ? '🧬 Generating Blended Digital Person...' : '🧬 Commit & Commission Blended Agent'}
                    </Text>
                  </TouchableOpacity>
                </>
              )}
            </ScrollView>

            {/* Modal Cancel Footer */}
            <TouchableOpacity
              style={[styles.modalButton, { backgroundColor: '#334155', marginTop: 8, alignItems: 'center' }]}
              onPress={handleCloseReproduction}
            >
              <Text style={styles.modalButtonText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* High Danger Safety Confirmation Modal */}
      <Modal visible={!!confirmModal} transparent animationType="fade">
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <Text style={[styles.modalTitle, { color: '#ef4444' }]}>⚠️ Interception: High-Risk Action</Text>
            <Text style={styles.modalSubtitle}>
              Tool: <Text style={{ color: '#f8fafc', fontWeight: 'bold' }}>{confirmModal?.tool}</Text>
            </Text>
            <View style={styles.modalCodeBox}>
              <Text style={styles.modalCodeText}>{confirmModal?.command || confirmModal?.summary}</Text>
            </View>
            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={[styles.modalButton, styles.denyButton]}
                onPress={() => handleConfirmTool(false)}
              >
                <Text style={styles.modalButtonText}>DENY / ABORT</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalButton, styles.approveButton]}
                onPress={() => handleConfirmTool(true)}
              >
                <Text style={styles.modalButtonText}>APPROVE</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Milestone Full Output, Reasoning & Tool Calls Reader Modal */}
      <Modal visible={!!selectedMilestone} transparent animationType="slide">
        <View style={styles.modalBackdrop}>
          <View style={[styles.modalCard, { height: '90%', maxHeight: '90%' }]}>
            {/* Header */}
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <View style={{ flex: 1, paddingRight: 8 }}>
                <Text style={[styles.modalTitle, { color: '#38bdf8' }]} numberOfLines={1}>
                  📖 {selectedMilestone?.agentName || 'Agent'} — Milestone #{selectedMilestone?.iteration}
                </Text>
                <Text style={{ color: '#94a3b8', fontSize: 11, marginTop: 2 }}>
                  {selectedMilestone?.tokens ? `${selectedMilestone.tokens} tokens • ` : ''}
                  {selectedMilestone?.timestamp ? new Date(selectedMilestone.timestamp).toLocaleString() : ''}
                </Text>
              </View>
              <TouchableOpacity
                onPress={() => setSelectedMilestone(null)}
                style={{ padding: 6, backgroundColor: '#334155', borderRadius: 6 }}
              >
                <Text style={{ color: '#f8fafc', fontWeight: 'bold', fontSize: 12 }}>✕ Close</Text>
              </TouchableOpacity>
            </View>

            {/* Scrollable Body */}
            <ScrollView style={{ flex: 1 }} showsVerticalScrollIndicator={true}>
              {/* Frontier Invariant (if present) */}
              {selectedMilestone?.distilled_invariant ? (
                <View style={[styles.modalCodeBox, { backgroundColor: '#1e1b4b', borderColor: '#6366f1', borderWidth: 1, padding: 10, marginVertical: 6 }]}>
                  <Text style={{ color: '#a5b4fc', fontSize: 11, fontWeight: 'bold', marginBottom: 4 }}>
                    🧠 TIER-1 FRONTIER DISTILLATION (INVARIANT)
                  </Text>
                  <Text style={{ color: '#e0e7ff', fontSize: 12, lineHeight: 18 }}>
                    {selectedMilestone.distilled_invariant}
                  </Text>
                </View>
              ) : null}

              {/* Next Target Question (if present) */}
              {selectedMilestone?.next_target_question ? (
                <View style={[styles.modalCodeBox, { backgroundColor: '#451a03', borderColor: '#f59e0b', borderWidth: 1, padding: 10, marginVertical: 6 }]}>
                  <Text style={{ color: '#fde68a', fontSize: 11, fontWeight: 'bold', marginBottom: 4 }}>
                    🎯 NEXT TARGET HYPOTHESIS / RECURSIVE PROMPT
                  </Text>
                  <Text style={{ color: '#fef3c7', fontSize: 12, lineHeight: 18 }}>
                    {selectedMilestone.next_target_question}
                  </Text>
                </View>
              ) : null}

              {/* Tool Calls (if present) */}
              {selectedMilestone?.tool_calls && selectedMilestone.tool_calls.length > 0 ? (
                <View style={{ marginVertical: 6 }}>
                  <Text style={[styles.agentDetailLabel, { marginBottom: 6, color: '#34d399' }]}>
                    🛠️ TOOL CALLS EXECUTED ({selectedMilestone.tool_calls.length})
                  </Text>
                  {selectedMilestone.tool_calls.map((tc, tcIdx) => {
                    const toolName = tc.tool || tc.name || tc.action || 'autonomous_tool';
                    const toolBadge = 
                      toolName === 'web_search' ? '🌐 Web Search' :
                      toolName === 'fetch_page' ? '📄 Page Fetch' :
                      toolName === 'search_hive_memory' ? '🧠 Qdrant Memory' :
                      toolName === 'talk_to_agent' ? '💬 Agent Dialogue' :
                      toolName === 'spawn_child_agent' ? '🐣 Spawn Subagent' :
                      `🛠️ ${toolName}`;

                    return (
                      <View key={tcIdx} style={[styles.modalCodeBox, { backgroundColor: '#064e3b', borderColor: '#059669', borderWidth: 1, padding: 8, marginVertical: 3 }]}>
                        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                            <View style={{ backgroundColor: '#022c22', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, borderWidth: 1, borderColor: '#10b981' }}>
                              <Text style={{ color: '#a7f3d0', fontSize: 10, fontWeight: 'bold' }}>
                                {toolBadge}
                              </Text>
                            </View>
                            <Text style={{ color: '#6ee7b7', fontSize: 11, fontWeight: 'bold' }}>
                              {toolName}
                            </Text>
                          </View>
                          {tc.status && (
                            <Text style={{ color: tc.status === 'success' ? '#34d399' : '#f87171', fontSize: 10 }}>
                              {tc.status}
                            </Text>
                          )}
                        </View>

                        {tc.query ? (
                          <Text style={{ color: '#a7f3d0', fontSize: 11, marginTop: 4 }}>
                            <Text style={{ color: '#6ee7b7', fontWeight: 'bold' }}>Query: </Text>{tc.query}
                          </Text>
                        ) : null}

                        {tc.url ? (
                          <Text style={{ color: '#a7f3d0', fontSize: 11, marginTop: 4 }}>
                            <Text style={{ color: '#6ee7b7', fontWeight: 'bold' }}>URL: </Text>{tc.url}
                          </Text>
                        ) : null}

                        {tc.target_agent ? (
                          <Text style={{ color: '#a7f3d0', fontSize: 11, marginTop: 4 }}>
                            <Text style={{ color: '#6ee7b7', fontWeight: 'bold' }}>Peer: </Text>{tc.target_agent}
                          </Text>
                        ) : null}

                        {tc.message ? (
                          <Text style={{ color: '#a7f3d0', fontSize: 11, marginTop: 4 }}>
                            <Text style={{ color: '#6ee7b7', fontWeight: 'bold' }}>Message: </Text>{tc.message}
                          </Text>
                        ) : null}

                        {tc.child_name ? (
                          <Text style={{ color: '#a7f3d0', fontSize: 11, marginTop: 4 }}>
                            <Text style={{ color: '#6ee7b7', fontWeight: 'bold' }}>Offspring: </Text>{tc.child_name} ({tc.child_role || 'Specialist'})
                          </Text>
                        ) : null}

                        {tc.result ? (
                          <View style={{ marginTop: 6, backgroundColor: '#022c22', padding: 6, borderRadius: 4, borderWidth: 1, borderColor: '#065f46' }}>
                            <Text style={{ color: '#99f6e4', fontSize: 10, lineHeight: 14 }} numberOfLines={6}>
                              {typeof tc.result === 'string' ? tc.result : JSON.stringify(tc.result, null, 2)}
                            </Text>
                          </View>
                        ) : null}
                      </View>
                    );
                  })}
                </View>
              ) : null}

              {/* Full Output & Reasoning */}
              <Text style={[styles.agentDetailLabel, { marginTop: 8, marginBottom: 4 }]}>
                📄 COMPLETE UNTRUNCATED OUTPUT & REASONING
              </Text>
              <View style={[styles.modalCodeBox, { padding: 12, backgroundColor: '#020617', borderColor: '#1e293b' }]}>
                <Text style={[styles.modalCodeText, { fontSize: 12, lineHeight: 18, color: '#f1f5f9' }]} selectable={true}>
                  {selectedMilestone?.full_output || selectedMilestone?.summary || 'No output recorded.'}
                </Text>
              </View>
            </ScrollView>

            {/* Footer Button */}
            <TouchableOpacity
              style={[styles.modalButton, { backgroundColor: '#334155', marginTop: 10, alignItems: 'center' }]}
              onPress={() => setSelectedMilestone(null)}
            >
              <Text style={styles.modalButtonText}>Close Dossier</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      </SafeAreaView>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#0f172a'
  },
  header: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 8,
    backgroundColor: '#1e293b',
    borderBottomWidth: 1,
    borderBottomColor: '#334155'
  },
  headerTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10
  },
  title: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#f8fafc'
  },
  connectionBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 3
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6
  },
  connectionText: {
    fontSize: 11,
    color: '#94a3b8'
  },
  headerRightBadge: {
    backgroundColor: '#0f172a',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#334155'
  },
  headerRightBadgeText: {
    fontSize: 10,
    color: '#38bdf8',
    fontWeight: 'bold'
  },
  harnessActionScroll: {
    flexDirection: 'row',
    gap: 8,
    paddingVertical: 2,
    marginBottom: 10
  },
  harnessBtn: {
    backgroundColor: '#334155',
    paddingVertical: 7,
    paddingHorizontal: 12,
    borderRadius: 8,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center'
  },
  harnessBtnText: {
    color: '#f8fafc',
    fontSize: 12,
    fontWeight: '600'
  },
  offlineBanner: {
    backgroundColor: '#991b1b',
    paddingVertical: 8,
    paddingHorizontal: 16,
    alignItems: 'center'
  },
  offlineBannerText: {
    color: '#fecaca',
    fontSize: 11,
    fontWeight: 'bold'
  },
  modelToggleGroup: {
    flexDirection: 'row',
    backgroundColor: '#0f172a',
    borderRadius: 8,
    padding: 3,
    marginBottom: 8
  },
  modelTab: {
    flex: 1,
    paddingVertical: 6,
    paddingHorizontal: 4,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 6
  },
  modelTabActive: {
    backgroundColor: '#2563eb'
  },
  modelTabTitle: {
    fontSize: 11,
    color: '#94a3b8',
    fontWeight: 'bold',
    textAlign: 'center'
  },
  modelTabTitleActive: {
    color: '#ffffff'
  },
  modelTabSub: {
    fontSize: 9,
    color: '#64748b',
    marginTop: 1,
    textAlign: 'center'
  },
  modelTabSubActive: {
    color: '#bfdbfe'
  },
  samplingBar: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 6
  },
  samplingLabel: {
    fontSize: 11,
    color: '#64748b'
  },
  samplingPill: {
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 12,
    backgroundColor: '#0f172a'
  },
  samplingPillActive: {
    backgroundColor: '#38bdf8'
  },
  filterBtn: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 6,
    backgroundColor: '#1e293b',
    borderWidth: 1,
    borderColor: '#334155'
  },
  filterBtnActive: {
    backgroundColor: '#0284c7',
    borderColor: '#38bdf8'
  },
  filterBtnText: {
    fontSize: 12,
    color: '#94a3b8',
    fontWeight: '600'
  },
  filterBtnTextActive: {
    color: '#ffffff',
    fontWeight: 'bold'
  },
  samplingPillText: {
    fontSize: 10,
    color: '#94a3b8'
  },
  samplingPillTextActive: {
    color: '#0f172a',
    fontWeight: 'bold'
  },
  messageContainer: {
    flex: 1,
    backgroundColor: '#0f172a'
  },
  messageContent: {
    padding: 16,
    gap: 12
  },
  emptyContainer: {
    marginTop: 30,
    padding: 20,
    backgroundColor: '#1e293b',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#334155'
  },
  emptyTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#38bdf8',
    marginBottom: 8
  },
  emptySubtitle: {
    fontSize: 12,
    color: '#94a3b8',
    lineHeight: 20
  },
  messageBubble: {
    borderRadius: 12,
    padding: 12,
    maxWidth: '92%'
  },
  userBubble: {
    alignSelf: 'flex-end',
    backgroundColor: '#2563eb'
  },
  assistantBubble: {
    alignSelf: 'flex-start',
    backgroundColor: '#1e293b',
    borderWidth: 1,
    borderColor: '#334155'
  },
  systemBubble: {
    alignSelf: 'center',
    backgroundColor: '#0f172a',
    borderWidth: 1,
    borderColor: '#334155',
    maxWidth: '98%'
  },
  assistantMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8
  },
  modelBadge: {
    fontSize: 11,
    fontWeight: 'bold',
    color: '#38bdf8'
  },
  telemetryBadge: {
    fontSize: 10,
    color: '#10b981'
  },
  streamingBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4
  },
  streamingText: {
    fontSize: 10,
    color: '#38bdf8'
  },
  thoughtDrawer: {
    backgroundColor: '#090d16',
    borderRadius: 8,
    padding: 8,
    marginBottom: 8,
    borderLeftWidth: 3,
    borderLeftColor: '#6366f1'
  },
  thoughtHeader: {
    paddingVertical: 2
  },
  thoughtTitle: {
    fontSize: 11,
    fontWeight: 'bold',
    color: '#818cf8'
  },
  thoughtContentBox: {
    marginTop: 6,
    paddingTop: 6,
    borderTopWidth: 1,
    borderTopColor: '#1e293b'
  },
  thoughtText: {
    fontSize: 11,
    color: '#94a3b8',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    lineHeight: 16
  },
  messageText: {
    fontSize: 14,
    color: '#f8fafc',
    lineHeight: 20
  },
  systemText: {
    fontSize: 11,
    color: '#64748b',
    textAlign: 'center'
  },
  inputContainer: {
    padding: 12,
    backgroundColor: '#1e293b',
    borderTopWidth: 1,
    borderTopColor: '#334155'
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8
  },
  textInput: {
    flex: 1,
    backgroundColor: '#0f172a',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    color: '#f8fafc',
    fontSize: 14,
    maxHeight: 100,
    borderWidth: 1,
    borderColor: '#334155'
  },
  sendButton: {
    backgroundColor: '#2563eb',
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center'
  },
  sendButtonDisabled: {
    backgroundColor: '#334155'
  },
  sendButtonText: {
    color: '#ffffff',
    fontWeight: 'bold',
    fontSize: 13
  },
  abortButton: {
    backgroundColor: '#dc2626',
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center'
  },
  abortButtonText: {
    color: '#ffffff',
    fontWeight: 'bold',
    fontSize: 14
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.75)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16
  },
  modalCard: {
    width: '100%',
    backgroundColor: '#1e293b',
    borderRadius: 12,
    padding: 18,
    borderWidth: 1,
    borderColor: '#334155'
  },
  modalTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#f8fafc',
    marginBottom: 4
  },
  modalSubtitle: {
    fontSize: 12,
    color: '#94a3b8',
    marginBottom: 10
  },
  engineSelectBtn: {
    flex: 1,
    backgroundColor: '#0f172a',
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#334155',
    alignItems: 'center'
  },
  engineSelectBtnActive: {
    borderColor: '#38bdf8',
    backgroundColor: '#1e293b'
  },
  engineSelectBtnText: {
    fontSize: 11,
    color: '#94a3b8',
    textAlign: 'center',
    fontWeight: '600'
  },
  engineSelectBtnTextActive: {
    color: '#38bdf8'
  },
  inputSectionLabel: {
    fontSize: 11,
    color: '#94a3b8',
    marginBottom: 4
  },
  paramLabel: {
    fontSize: 11,
    color: '#cbd5e1',
    fontWeight: '600',
    marginBottom: 2
  },
  modalCodeBox: {
    backgroundColor: '#090d16',
    padding: 10,
    borderRadius: 6,
    marginVertical: 12
  },
  modalCodeText: {
    color: '#38bdf8',
    fontSize: 12,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace'
  },
  modalButtons: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 10,
    marginTop: 8
  },
  modalButton: {
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 8
  },
  modalButtonText: {
    color: '#ffffff',
    fontWeight: 'bold',
    fontSize: 12
  },
  denyButton: {
    backgroundColor: '#dc2626'
  },
  approveButton: {
    backgroundColor: '#16a34a'
  },
  memoryResultCard: {
    backgroundColor: '#0f172a',
    borderRadius: 8,
    padding: 10,
    marginBottom: 8,
    borderLeftWidth: 3,
    borderLeftColor: '#38bdf8'
  },
  memoryResultTitle: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#f8fafc',
    flex: 1
  },
  memoryResultScore: {
    fontSize: 10,
    color: '#34d399'
  },
  memoryResultPreview: {
    fontSize: 11,
    color: '#94a3b8',
    marginTop: 4,
    lineHeight: 16
  },
  liveEventItem: {
    paddingVertical: 6,
    paddingHorizontal: 8,
    backgroundColor: '#0f172a',
    borderRadius: 6,
    marginBottom: 6,
    borderLeftWidth: 2,
    borderLeftColor: '#38bdf8'
  },
  categoryBadge: {
    paddingHorizontal: 5,
    paddingVertical: 2,
    borderRadius: 4
  },
  categoryBadgeText: {
    fontSize: 9,
    color: '#f8fafc',
    fontWeight: 'bold'
  },
  liveEventSource: {
    fontSize: 10,
    color: '#cbd5e1',
    fontWeight: '600'
  },
  liveEventTime: {
    fontSize: 9,
    color: '#64748b'
  },
  liveEventMessage: {
    fontSize: 11,
    color: '#e2e8f0',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    lineHeight: 16
  },
  agentCard: {
    backgroundColor: '#0f172a',
    borderRadius: 8,
    padding: 10,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#334155'
  },
  agentCollapsibleHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start'
  },
  agentName: {
    fontSize: 13,
    fontWeight: 'bold',
    color: '#f8fafc'
  },
  agentRole: {
    fontSize: 10,
    color: '#94a3b8',
    marginTop: 2
  },
  agentStatusBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4
  },
  agentStatusText: {
    fontSize: 9,
    fontWeight: 'bold'
  },
  agentMission: {
    fontSize: 11,
    color: '#cbd5e1',
    lineHeight: 15,
    marginTop: 4
  },
  agentDetailSection: {
    marginTop: 8,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: '#1e293b'
  },
  agentDetailLabel: {
    fontSize: 10,
    color: '#94a3b8',
    fontWeight: 'bold',
    letterSpacing: 0.5
  },
  agentDetailValue: {
    fontSize: 11,
    color: '#cbd5e1',
    marginTop: 2,
    lineHeight: 16
  }
});
