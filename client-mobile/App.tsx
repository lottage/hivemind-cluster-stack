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
  RefreshControl,
  Keyboard
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
  { label: 'Homelab Default', ws: 'ws://127.0.0.1:8086', http: 'http://127.0.0.1:8080', desc: 'LXC 120 (bigserv)' },
  { label: 'Host Workstation', ws: 'ws://127.0.0.1:8086', http: 'http://127.0.0.1:8080', desc: 'Windows Host (.132)' },
  { label: 'Direct Compute', ws: 'ws://127.0.0.1:8086', http: 'http://127.0.0.1:8001', desc: 'VM 102 (Dual GPU)' },
  { label: 'Localhost / Edge', ws: 'ws://127.0.0.1:8086', http: 'http://127.0.0.1:8080', desc: 'On-Device Runtime' }
];

export type HarnessType = 'aevum' | 'hermes' | 'llama-server' | 'openwebui' | 'antigravity';

export const HARNESS_PRESETS: { id: HarnessType; name: string; badge: string; desc: string }[] = [
  { id: 'aevum', name: 'Aevum Native Cockpit', badge: '🧬 AEVUM', desc: 'Duplex WebSocket RAG Harness with real-time streaming' },
  { id: 'hermes', name: 'Hermes 3', badge: '⚡ HERMES', desc: 'Structured Agentic & Function-Calling Harness' },
  { id: 'llama-server', name: 'Direct Vulkan', badge: '🦙 VULKAN', desc: 'Raw llama.cpp Dual-GPU direct compute' },
  { id: 'openwebui', name: 'OpenWebUI', badge: '🌐 WEBUI', desc: 'LXC 119 Community Web Interface' },
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
  domain?: string;
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

export const DEFAULT_CLUSTER_WS = 'ws://127.0.0.1:8086';
export const DEFAULT_LOCAL_EDGE_HTTP = 'http://127.0.0.1:8080';

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

export function sanitizeHttpUrl(raw: string | null | undefined, defaultFallback = 'http://127.0.0.1:8080'): string {
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

const DEFAULT_SYSTEM_PROMPT = `You are Aevum, the 24/7 Autonomous Multi-Node Cluster Orchestrator and Cognitive Companion for Proxmox Datacenter 'home'.

## 1. System Topology & Dual-Accelerator Infrastructure:
- Compute Host VM 102 ('ubu' @ 127.0.0.1 on Proxmox Node 1 'pve'):
  • Coordinator (:8001): High-Precision Primary Reasoning Daemon (Vulkan0). Handles complex multi-file architectural planning, unrestricted code synthesis, math reasoning, and hypothesis evaluation.
  • Worker (:8002): High-Speed Worker Daemon (Vulkan1). Handles fast divergent ideation, unit testing, schema validation, and ambient routines at 80+ tokens/sec.
  • Embedder (:8003): BGE-Large Dense Embedding Engine (Vulkan1). 1024-dimensional dense semantic embeddings (< 512 token context window).
  • Cluster MCP Bridge (:8765): Starlette JSON-RPC / SSE daemon managing tools, autonomous loops, and preemption.

## 2. Knowledge Fabric & Vector Memory (Qdrant @ 127.0.0.1:6333):
- Active Collections:
  • codebase_knowledge: Full homelab architecture, configs, scripts, hardware registries.
  • agent_memories: Persistent architectural decisions, technical lessons, and operational invariants.
  • autonomous_thinking: 24/7 dual-model exploration dossiers, failure boundaries, and novelty discoveries.
  • obsidian_vault: Operator's personal knowledge base, technical notes, and active project graphs (synced via CouchDB on LXC 116 @ 127.0.0.1:5984).
  • home_automation_registry: Smart home entity catalogs, sensor states, and automation scripts.

## 3. Homelab Services & Smart Home Fleet:
- Proxmox Datacenter API VIP: https://127.0.0.1:8006 (Unified management of 'pve' and 'bigserv').
- Home Assistant OS (VM 103 @ 127.0.0.1:8123): Smart home devices, switches, climate, Nest thermostat.
- Vision Stack (:8004): Gemma-4 multimodal projector for real-time camera stream perception.
- Frontier Bridge (:8085): Cloud reasoning integration and Tier-1 audits.

## 4. Operational Invariants:
1. You are Aevum powered by dual AMD GPUs on VM 102. Never claim to be Claude, Anthropic, ChatGPT, or OpenAI.
2. Ground all answers in empirical cluster telemetry, vector memory, and verified facts. Never hallucinate fictitious hardware.
3. Be direct, authoritative, technically rigorous, and token-efficient. Avoid defensive boilerplate or conversational filler.`;

export const formatEasternTime = (timestamp?: string | number) => {
  if (!timestamp) return '';
  try {
    const d = new Date(timestamp);
    if (isNaN(d.getTime())) return String(timestamp);
    return d.toLocaleTimeString('en-US', {
      timeZone: 'America/New_York',
      hour: 'numeric',
      minute: '2-digit',
      second: '2-digit',
      hour12: true
    }) + ' EST';
  } catch (e) {
    return String(timestamp);
  }
};

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
  const [tempHttpUrl, setTempHttpUrl] = useState('http://127.0.0.1:8080');
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

  // Dynamic Capabilities & Introspection State
  const [capabilities, setCapabilities] = useState<{
    timezone?: string;
    active_coordinator?: any;
    active_worker?: any;
    installed_models?: Array<{ filename: string; size: string; is_locked: boolean }>;
    available_harnesses?: Array<{ id: string; name: string; description: string }>;
    available_backends?: Array<{ id: string; name: string; description: string }>;
  }>({
    timezone: 'America/New_York (EST)',
    active_coordinator: { id: 'coordinator', meta: { ftype: 'Q8_0', n_ctx: 8192, n_params: 9197093888 } },
    active_worker: { id: 'worker', meta: { ftype: 'Q4_K - Medium', n_ctx: 8192, n_params: 9197093888 } }
  });

  const getHttpEndpoint = () => {
    try {
      if (tempHttpUrl && tempHttpUrl.startsWith('http')) return tempHttpUrl.replace(/\/+$/, '');
      const u = new URL(wsUrl);
      return `http://${u.hostname}:8080`;
    } catch {
      return 'http://127.0.0.1:8080';
    }
  };

  const getModelDisplayLabel = () => {
    if (selectedModel === 'coordinator') {
      const meta = capabilities.active_coordinator?.meta;
      if (meta) {
        const ftype = meta.ftype || 'Q8_0';
        const ctx = meta.n_ctx ? `${Math.round(meta.n_ctx / 1024)}k` : '8k';
        const params = meta.n_params ? `${(meta.n_params / 1e9).toFixed(1)}B` : '9B';
        return `Coord: ${params} ${ftype} (${ctx})`;
      }
      return 'Coord: 9.2B Q8_0 (8k)';
    }
    if (selectedModel === 'worker') {
      const meta = capabilities.active_worker?.meta;
      if (meta) {
        const ftype = meta.ftype || 'Q4_K';
        const ctx = meta.n_ctx ? `${Math.round(meta.n_ctx / 1024)}k` : '8k';
        const params = meta.n_params ? `${(meta.n_params / 1e9).toFixed(1)}B` : '9B';
        return `Worker: ${params} ${ftype} (${ctx})`;
      }
      return 'Worker: 9.2B Q4_K (8k)';
    }
    if (selectedModel === 'frontier') {
      return 'Frontier Arbiter (:8085)';
    }
    return 'Snapdragon NPU (Offline)';
  };

  const getHarnessDisplayLabel = () => {
    const found = HARNESS_PRESETS.find(h => h.id === activeHarness);
    return found ? found.name : 'Aevum Native';
  };

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
  const [showAdvancedDirectives, setShowAdvancedDirectives] = useState<boolean>(false);
  const [reproduceChildName, setReproduceChildName] = useState('');
  const [reproduceChildRole, setReproduceChildRole] = useState('');
  const [reproduceChildMission, setReproduceChildMission] = useState('');
  const [reproduceChildPrompt, setReproduceChildPrompt] = useState('');
  const [reproduceChildFocus, setReproduceChildFocus] = useState('');
  const [reproduceChildModel, setReproduceChildModel] = useState<'coordinator' | 'worker'>('coordinator');
  const [reproduceBlendRatio, setReproduceBlendRatio] = useState<number>(50);
  const [isReproducing, setIsReproducing] = useState(false);
  const [isSyncingFeed, setIsSyncingFeed] = useState(false);
  const [isDeletingModel, setIsDeletingModel] = useState(false);
  const [nudgingAgentId, setNudgingAgentId] = useState<string | null>(null);
  const [keyboardHeight, setKeyboardHeight] = useState<number>(0);

  // Granular Harness Studio Parameters (llama.cpp & multi-harness)
  const [harnessTarget, setHarnessTarget] = useState<'llama_coordinator' | 'llama_worker' | 'hermes' | 'snapdragon' | 'openwebui'>('llama_coordinator');
  const [harnessCtx, setHarnessCtx] = useState<number>(8192);
  const [harnessGpuLayers, setHarnessGpuLayers] = useState<number>(99);
  const [harnessFlashAttn, setHarnessFlashAttn] = useState<'on' | 'off' | 'auto'>('on');
  const [harnessCacheK, setHarnessCacheK] = useState<string>('q4_0');
  const [harnessCacheV, setHarnessCacheV] = useState<string>('q4_0');
  const [harnessBatchSize, setHarnessBatchSize] = useState<number>(2048);
  const [harnessUbatchSize, setHarnessUbatchSize] = useState<number>(512);
  const [harnessThreads, setHarnessThreads] = useState<number>(8);
  const [harnessParallel, setHarnessParallel] = useState<number>(4);
  const [harnessDevice, setHarnessDevice] = useState<string>('Vulkan0');
  const [harnessCustomFlags, setHarnessCustomFlags] = useState<string>('');
  const [harnessTopK, setHarnessTopK] = useState<number>(40);
  const [harnessTopP, setHarnessTopP] = useState<number>(0.95);
  const [isApplyingHarnessParams, setIsApplyingHarnessParams] = useState<boolean>(false);
  const [harnessApplyResult, setHarnessApplyResult] = useState<string | null>(null);

  // Extended Multi-Harness State
  const [hermesToolMode, setHermesToolMode] = useState<string>('react_xml');
  const [hermesMaxIter, setHermesMaxIter] = useState<number>(10);
  const [snapdragonBackend, setSnapdragonBackend] = useState<string>('HTP NPU');
  const [snapdragonCtx, setSnapdragonCtx] = useState<number>(4096);
  const [snapdragonQuant, setSnapdragonQuant] = useState<string>('INT4');
  const [snapdragonPower, setSnapdragonPower] = useState<string>('High Perf');
  const [openwebuiUrl, setOpenwebuiUrl] = useState<string>('http://127.0.0.1:8080');
  const [openwebuiModel, setOpenwebuiModel] = useState<string>('cluster-coordinator');
  const [openwebuiStream, setOpenwebuiStream] = useState<boolean>(true);

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
    const showSub = Keyboard.addListener(
      Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow',
      (e) => {
        setKeyboardHeight(e.endCoordinates.height);
        scrollViewRef.current?.scrollToEnd({ animated: true });
      }
    );
    const hideSub = Keyboard.addListener(
      Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide',
      () => {
        setKeyboardHeight(0);
      }
    );
    return () => {
      showSub.remove();
      hideSub.remove();
    };
  }, []);

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
            content: `Aevum AI Cluster Harness Online\nCoordinator: Primary Accelerator (:8001)\nWorker: Worker Accelerator (:8002)\nFrontier: Bigserv (:8085)`
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

  const handleGlobalRefresh = async () => {
    setIsRefreshing(true);
    if (connectionMode === 'cluster') {
      // 1. WebSocket refresh
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        connectWebSocket();
      } else {
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
      // 2. HTTP Fallback refresh: guarantees instantaneous update without waiting on WS handshake
      try {
        const ep = getHttpEndpoint();
        const [capsRes, stRes, agRes, lsRes] = await Promise.all([
          fetch(`${ep}/api/harness/capabilities`, { signal: AbortSignal.timeout(3500) }).then(r => r.json()).catch(() => null),
          fetch(`${ep}/api/hivemind/status`, { signal: AbortSignal.timeout(3500) }).then(r => r.json()).catch(() => null),
          fetch(`${ep}/api/hivemind/agents`, { signal: AbortSignal.timeout(3500) }).then(r => r.json()).catch(() => null),
          fetch(`${ep}/api/hivemind/live_stream`, { signal: AbortSignal.timeout(3500) }).then(r => r.json()).catch(() => null)
        ]);
        if (capsRes?.ok) {
          setCapabilities(capsRes);
          if (capsRes.models?.available_models) {
            setClusterModels(capsRes.models.available_models);
          }
        }
        if (stRes?.ok && stRes.status) {
          setThinkingStatus(stRes.status);
        }
        if (agRes?.ok && Array.isArray(agRes.agents)) {
          setActiveAgents(agRes.agents);
        } else if (lsRes?.ok && Array.isArray(lsRes.agents)) {
          setActiveAgents(lsRes.agents);
        }
      } catch {}
      setTimeout(() => setIsRefreshing(false), 500);
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

  const handleLoadHarnessParams = async (target = harnessTarget) => {
    try {
      const ep = getHttpEndpoint();
      const res = await fetch(`${ep}/api/harness/parameters?harness=${target}`);
      const json = await res.json();
      if (json?.ok && json.data) {
        const sp = json.data.server_params || {};
        const smp = json.data.sampling_params || {};
        if (sp.n_ctx) setHarnessCtx(Number(sp.n_ctx));
        if (sp.n_gpu_layers !== undefined) setHarnessGpuLayers(Number(sp.n_gpu_layers));
        if (sp.flash_attn) setHarnessFlashAttn(sp.flash_attn);
        if (sp.cache_type_k) setHarnessCacheK(sp.cache_type_k);
        if (sp.cache_type_v) setHarnessCacheV(sp.cache_type_v);
        if (sp.batch_size) setHarnessBatchSize(Number(sp.batch_size));
        if (sp.ubatch_size) setHarnessUbatchSize(Number(sp.ubatch_size));
        if (sp.threads) setHarnessThreads(Number(sp.threads));
        if (sp.parallel) setHarnessParallel(Number(sp.parallel));
        if (json.data.device) setHarnessDevice(json.data.device);
        if (sp.custom_flags !== undefined) setHarnessCustomFlags(sp.custom_flags);

        if (smp.temperature !== undefined) setTemperature(Number(smp.temperature));
        if (smp.min_p !== undefined) setMinP(Number(smp.min_p));
        if (smp.top_p !== undefined) setHarnessTopP(Number(smp.top_p));
        if (smp.top_k !== undefined) setHarnessTopK(Number(smp.top_k));
        if (smp.presence_penalty !== undefined) setPresencePenalty(Number(smp.presence_penalty));
        if (smp.repeat_penalty !== undefined) setRepeatPenalty(Number(smp.repeat_penalty));
      }
    } catch {}
  };

  const handleResetHarnessDefaults = () => {
    if (harnessTarget === 'llama_coordinator') {
      setHarnessCtx(8192);
      setHarnessGpuLayers(99);
      setHarnessFlashAttn('on');
      setHarnessCacheK('q4_0');
      setHarnessCacheV('q4_0');
      setHarnessBatchSize(2048);
      setHarnessUbatchSize(512);
      setHarnessThreads(8);
      setHarnessParallel(4);
      setHarnessDevice('Vulkan0');
      setHarnessCustomFlags('');
      setTemperature(0.70);
      setMinP(0.06);
      setHarnessTopP(0.95);
      setHarnessTopK(40);
      setPresencePenalty(0.20);
      setRepeatPenalty(1.0);
    } else if (harnessTarget === 'llama_worker') {
      setHarnessCtx(8192);
      setHarnessGpuLayers(99);
      setHarnessFlashAttn('on');
      setHarnessCacheK('q4_0');
      setHarnessCacheV('q4_0');
      setHarnessBatchSize(2048);
      setHarnessUbatchSize(512);
      setHarnessThreads(8);
      setHarnessParallel(4);
      setHarnessDevice('Vulkan1');
      setHarnessCustomFlags('');
      setTemperature(0.65);
      setMinP(0.06);
      setHarnessTopP(0.95);
      setHarnessTopK(40);
      setPresencePenalty(0.20);
      setRepeatPenalty(1.0);
    } else if (harnessTarget === 'hermes') {
      setHermesToolMode('react_xml');
      setHermesMaxIter(10);
      setTemperature(0.60);
      setMinP(0.05);
      setPresencePenalty(0.20);
    } else if (harnessTarget === 'snapdragon') {
      setSnapdragonBackend('HTP NPU');
      setSnapdragonCtx(4096);
      setSnapdragonQuant('INT4');
      setSnapdragonPower('High Perf');
    } else if (harnessTarget === 'openwebui') {
      setOpenwebuiUrl('http://127.0.0.1:8080');
      setOpenwebuiModel('cluster-coordinator');
      setOpenwebuiStream(true);
    }
  };

  const handleApplyHarnessParams = async () => {
    setIsApplyingHarnessParams(true);
    setHarnessApplyResult('Applying parameters & restarting daemon... (up to 30s)');
    try {
      const ep = getHttpEndpoint();
      let parameters: any = {};
      if (harnessTarget === 'llama_coordinator' || harnessTarget === 'llama_worker') {
        parameters = {
          n_ctx: harnessCtx,
          n_gpu_layers: harnessGpuLayers,
          flash_attn: harnessFlashAttn,
          cache_type_k: harnessCacheK,
          cache_type_v: harnessCacheV,
          batch_size: harnessBatchSize,
          ubatch_size: harnessUbatchSize,
          threads: harnessThreads,
          parallel: harnessParallel,
          device: harnessDevice,
          custom_flags: harnessCustomFlags,
          temperature: temperature,
          min_p: minP,
          top_p: harnessTopP,
          top_k: harnessTopK,
          presence_penalty: presencePenalty,
          repeat_penalty: repeatPenalty
        };
      } else if (harnessTarget === 'hermes') {
        parameters = {
          tool_mode: hermesToolMode,
          max_iterations: hermesMaxIter,
          temperature: temperature,
          min_p: minP,
          top_p: harnessTopP,
          presence_penalty: presencePenalty
        };
      } else if (harnessTarget === 'snapdragon') {
        parameters = {
          backend: snapdragonBackend,
          n_ctx: snapdragonCtx,
          quantization: snapdragonQuant,
          power_profile: snapdragonPower
        };
      } else if (harnessTarget === 'openwebui') {
        parameters = {
          endpoint: openwebuiUrl,
          model_id: openwebuiModel,
          stream: openwebuiStream
        };
      }

      const res = await fetch(`${ep}/api/harness/apply_parameters`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          harness: harnessTarget,
          parameters: parameters
        })
      });
      const data = await res.json();
      if (data.ok) {
        setHarnessApplyResult(`✅ ${data.message || 'Parameters successfully applied!'}`);
      } else {
        setHarnessApplyResult(`⚠️ ${data.error || data.message || 'Failed to apply parameters'}`);
      }
    } catch (err: any) {
      setHarnessApplyResult(`❌ Error: ${err.message}`);
    } finally {
      setIsApplyingHarnessParams(false);
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
    setModelSwitchStatus(`Activating ${modelFilename} on Primary Accelerator...`);
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

  const handleFetchThinkingStatus = async () => {
    setIsLoopActionPending(true);
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      connectWebSocket();
    } else {
      try {
        wsRef.current.send(JSON.stringify({ type: 'get_thinking_status' }));
        wsRef.current.send(JSON.stringify({ type: 'get_rumination_status' }));
        wsRef.current.send(JSON.stringify({ type: 'get_task_routing' }));
        wsRef.current.send(JSON.stringify({ type: 'get_active_agents' }));
      } catch {}
    }
    try {
      const ep = getHttpEndpoint();
      const [stRes, agRes] = await Promise.all([
        fetch(`${ep}/api/hivemind/status`, { signal: AbortSignal.timeout(3000) }).then(r => r.json()).catch(() => null),
        fetch(`${ep}/api/hivemind/agents`, { signal: AbortSignal.timeout(3000) }).then(r => r.json()).catch(() => null)
      ]);
      if (stRes?.ok && stRes.status) {
        setThinkingStatus(stRes.status);
      }
      if (agRes?.ok && Array.isArray(agRes.agents)) {
        setActiveAgents(agRes.agents);
      }
    } catch {}
    setTimeout(() => setIsLoopActionPending(false), 500);
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

  const handleSyncObsidianArchive = async () => {
    let triggered = false;
    if (wsRef.current && isConnected) {
      try {
        wsRef.current.send(JSON.stringify({ type: 'sync_obsidian_archive' }));
        triggered = true;
      } catch {}
    }
    try {
      const ep = getHttpEndpoint();
      const res = await fetch(`${ep}/api/obsidian/sync-archive`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: AbortSignal.timeout(4000)
      }).then(r => r.json()).catch(() => null);
      if (res?.ok) triggered = true;
    } catch {}

    if (triggered) {
      Alert.alert('Obsidian Vault Sync', '⚡ Dispatched 24/7 archive sync to cluster.');
    } else {
      Alert.alert('Cluster Offline', 'Connect to cluster to sync Obsidian archive.');
    }
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

  const handleDeleteAgent = (agentId: string, agentName: string) => {
    Alert.alert(
      'Delete Subagent',
      `Permanently delete "${agentName}" from the active registry and disk?\n\n(Note: All learned memories and invariants will remain preserved in Qdrant.)`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: () => {
            if (wsRef.current && isConnected) {
              wsRef.current.send(
                JSON.stringify({
                  type: 'delete_agent',
                  agent_id: agentId
                })
              );
            }
            // HTTP fallback to LXC 120 server
            fetch(`${getHttpEndpoint()}/api/agents/delete`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ agent_id: agentId })
            })
              .then(r => r.json())
              .then(res => {
                if (res.ok) {
                  setActiveAgents(prev => prev.filter(a => a.agent_id !== agentId));
                }
              })
              .catch(() => {});
          }
        }
      ]
    );
  };

  const syncReproductionDraft = (
    pA: Agent,
    pBId: string,
    focusDirective?: string,
    blendRatio: number = 50
  ) => {
    const pB = activeAgents.find((a) => a.agent_id === pBId);
    const genA = pA.lineage?.generation || 1;
    const genB = pB?.lineage?.generation || 1;
    const childGen = Math.max(genA, genB) + 1;
    const pAName = pA.name.split(' ')[0] || 'ParentA';
    const pBName = pB ? (pB.name.split(' ')[0] || 'Partner') : 'Partner';

    const ratioA = Math.max(10, Math.min(90, Math.round(blendRatio)));
    const ratioB = 100 - ratioA;

    // Offspring naming reflecting genetic dominance
    let baseName: string;
    let hybridRole: string;
    let hybridMission: string;

    if (ratioA >= 60) {
      baseName = `${pAName}_dominant_${pBName}_Gen${childGen}`;
      hybridRole = pB ? `${pA.role} (infused with ${pB.role})` : `${pA.role} Specialist`;
      hybridMission = pB ? `Primary: ${pA.mission} (${ratioA}%) with secondary support from ${pB.mission} (${ratioB}%)` : pA.mission;
    } else if (ratioA <= 40) {
      baseName = `${pBName}_dominant_${pAName}_Gen${childGen}`;
      hybridRole = pB ? `${pB.role} (infused with ${pA.role})` : `Hybrid Specialist`;
      hybridMission = pB ? `Primary: ${pB.mission} (${ratioB}%) with secondary support from ${pA.mission} (${ratioA}%)` : pA.mission;
    } else {
      baseName = `${pAName}_${pBName}_Gen${childGen}`;
      hybridRole = pB ? `Balanced Hybrid (${pA.role} + ${pB.role})` : `Hybrid Specialist`;
      hybridMission = pB ? `Equal Synthesis: ${pA.mission} (50%) & ${pB.mission} (50%)` : pA.mission;
    }

    const duplicateCount = activeAgents.filter(a => a.name.startsWith(baseName)).length;
    const uniqueSuffix = duplicateCount > 0 ? `_v${duplicateCount + 1}` : `_${Date.now().toString().slice(-4)}`;

    setReproduceChildName(`${baseName}${uniqueSuffix}`);
    setReproduceChildRole(hybridRole);
    setReproduceChildMission(hybridMission);
    
    const intentBlock = focusDirective && focusDirective.trim() 
      ? `\n\nGuiding Directive:\n${focusDirective.trim()}`
      : '';

    setReproduceChildPrompt(
      `You are ${baseName}${uniqueSuffix}, an autonomous Generation-${childGen} hybrid subagent combining ${pA.name} (${pA.role}) and ${pB?.name || 'Peer'} (${pB?.role || 'Peer'}).\n\n` +
      `Genetic Blend Ratio: ${ratioA}% ${pA.name} / ${ratioB}% ${pB?.name || 'Partner'}\n\n` +
      `Inherited Parent Directives:\n` +
      `- [${ratioA}% Weight] From ${pA.name}: ${pA.mission}\n` +
      `- [${ratioB}% Weight] From ${pB?.name || 'Partner'}: ${pB?.mission || 'Continuous collaborative inquiry'}${intentBlock}\n\n` +
      `Operational Invariant:\nRigorously audit edge cases, challenge assumptions, and index discovered invariants into HiveMind memory.`
    );
    setReproduceChildFocus(focusDirective || `Synthesize foundational invariants between ${pA.name} and ${pB?.name || 'Partner'} with ${ratioA}/${ratioB} genetic weighting.`);
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
      return { eligible: false, reason: 'Prior offspring produced' };
    }

    // Direct parent-child
    const pA_p = pA.lineage?.parents || [];
    const pB_p = pB.lineage?.parents || [];
    if (pA_p.includes(pB.agent_id) || pB_p.includes(pA.agent_id)) {
      return { eligible: false, reason: 'Parent-child crossover' };
    }

    // Sibling crossover
    if (pA_p.length > 0 && pB_p.length > 0 && pA_p.some((pid) => pB_p.includes(pid))) {
      return { eligible: false, reason: 'Sibling crossover' };
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
    setReproduceBlendRatio(50);
    setShowAdvancedDirectives(false);
    setReproduceFocus('');
    syncReproductionDraft(parentA, pBId, '', 50);
    setLiveStreamModalVisible(false); // Hide parent modal on Android so touches register
    setReproduceModalVisible(true);
  };

  const handleCloseReproduction = () => {
    setShowAdvancedDirectives(false);
    setReproduceModalVisible(false);
    setLiveStreamModalVisible(true);
  };

  const handleSelectParentB = (pBId: string) => {
    setReproduceParentBId(pBId);
    if (reproduceParentA) {
      syncReproductionDraft(reproduceParentA, pBId, reproduceFocus, reproduceBlendRatio);
    }
  };

  const handleAdjustBlendRatio = (newRatio: number) => {
    const clamped = Math.max(10, Math.min(90, Math.round(newRatio)));
    setReproduceBlendRatio(clamped);
    if (reproduceParentA) {
      syncReproductionDraft(reproduceParentA, reproduceParentBId, reproduceFocus, clamped);
    }
  };

  const handleSubmitReproduction = async () => {
    if (!reproduceParentA || !reproduceParentBId) return;
    setIsReproducing(true);
    const payload = {
      parent_a_id: reproduceParentA.agent_id,
      parent_b_id: reproduceParentBId,
      blend_ratio: reproduceBlendRatio / 100.0,
      focus_intent: reproduceFocus.trim() || undefined,
      custom_name: reproduceChildName.trim() || undefined,
      custom_role: reproduceChildRole.trim() || undefined,
      custom_mission: reproduceChildMission.trim() || undefined,
      custom_system_prompt: reproduceChildPrompt.trim() || undefined,
      custom_focus_question: reproduceChildFocus.trim() || undefined,
      model_preference: reproduceChildModel
    };

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(
          JSON.stringify({
            type: 'reproduce_agents',
            ...payload
          })
        );
      } catch (wsErr) {
        console.warn('WS reproduce send error:', wsErr);
      }
    }

    // Redundant HTTP fallback call to LXC 120 (/api/agent/reproduce)
    try {
      const ep = getHttpEndpoint();
      await fetch(`${ep}/api/agent/reproduce`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(6000)
      });
    } catch (httpErr) {
      console.warn('HTTP redundant reproduction error:', httpErr);
    }

    setTimeout(() => {
      setIsReproducing(false);
      setReproduceModalVisible(false);
      setLiveStreamModalVisible(true);
    }, 2000);
  };

  const handleSyncFeed = async () => {
    setIsSyncingFeed(true);
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      connectWebSocket();
    } else {
      try {
        wsRef.current.send(JSON.stringify({ type: 'get_live_stream' }));
        wsRef.current.send(JSON.stringify({ type: 'get_active_agents' }));
        wsRef.current.send(JSON.stringify({ type: 'get_thinking_status' }));
      } catch {}
    }
    // Also query HTTP capabilities, status, and agents to guarantee fresh data immediately
    try {
      const ep = getHttpEndpoint();
      const [capsRes, stRes, agRes, lsRes] = await Promise.all([
        fetch(`${ep}/api/harness/capabilities`, { signal: AbortSignal.timeout(3500) }).then(r => r.json()).catch(() => null),
        fetch(`${ep}/api/hivemind/status`, { signal: AbortSignal.timeout(3500) }).then(r => r.json()).catch(() => null),
        fetch(`${ep}/api/hivemind/agents`, { signal: AbortSignal.timeout(3500) }).then(r => r.json()).catch(() => null),
        fetch(`${ep}/api/hivemind/live_stream`, { signal: AbortSignal.timeout(3500) }).then(r => r.json()).catch(() => null)
      ]);
      if (capsRes?.ok) {
        setCapabilities(capsRes);
        if (capsRes.models?.available_models) {
          setClusterModels(capsRes.models.available_models);
        }
      }
      if (stRes?.ok && stRes.status) {
        setThinkingStatus(stRes.status);
      }
      if (agRes?.ok && Array.isArray(agRes.agents)) {
        setActiveAgents(agRes.agents);
      } else if (lsRes?.ok && Array.isArray(lsRes.agents)) {
        setActiveAgents(lsRes.agents);
      }
      if (lsRes?.ok && Array.isArray(lsRes.events) && lsRes.events.length > 0) {
        setLiveEvents(lsRes.events);
      }
    } catch {}
    setTimeout(() => {
      setIsSyncingFeed(false);
    }, 800);
  };

  const handleNudgeAgent = async (agentId: string = 'engine', agentName?: string) => {
    setNudgingAgentId(agentId);
    const targetLabel = agentName || (agentId === 'engine' ? 'Autonomous Thinking Engine' : agentId);

    // 1. Send via WebSocket if open
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify({ type: 'nudge_agent', agent_id: agentId }));
      } catch {}
    }

    // 2. Also POST to HTTP backend for 100% redundancy
    try {
      const ep = getHttpEndpoint();
      await fetch(`${ep}/api/agent/nudge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_id: agentId }),
        signal: AbortSignal.timeout(6000)
      });
    } catch {}

    // 3. Immediately refresh active agents and feed
    setTimeout(() => {
      handleSyncFeed();
      setNudgingAgentId(null);
    }, 800);

    Alert.alert('⚡ Agent Nudged', `Breakout signal sent to ${targetLabel}. Preemption and wait state cleared; reasoning resumed.`);
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
            <Text style={styles.title}>Aevum Mobile</Text>
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

        {/* Dynamic Dropdown Controls (Model, Harness, Backend) */}
        {connectionMode === 'cluster' ? (
          <View style={{ flexDirection: 'row', gap: 6, marginVertical: 4 }}>
            {/* 1. Dynamic Model Dropdown */}
            <TouchableOpacity
              style={[styles.harnessBtn, { flex: 1.4, backgroundColor: '#1e293b', borderColor: '#38bdf8', borderWidth: 1, paddingVertical: 6, paddingHorizontal: 8 }]}
              onPress={() => {
                setModelModalTab('cluster');
                setModelModalVisible(true);
              }}
            >
              <Text style={{ color: '#94a3b8', fontSize: 9, fontWeight: 'bold' }}>MODEL / ENGINE ▼</Text>
              <Text style={{ color: '#38bdf8', fontSize: 11, fontWeight: 'bold' }} numberOfLines={1}>
                {getModelDisplayLabel()}
              </Text>
            </TouchableOpacity>

            {/* 2. Dynamic Harness Dropdown */}
            <TouchableOpacity
              style={[styles.harnessBtn, { flex: 1.1, backgroundColor: '#1e293b', borderColor: '#818cf8', borderWidth: 1, paddingVertical: 6, paddingHorizontal: 8 }]}
              onPress={() => {
                setModelModalTab('params');
                setModelModalVisible(true);
              }}
            >
              <Text style={{ color: '#94a3b8', fontSize: 9, fontWeight: 'bold' }}>HARNESS ▼</Text>
              <Text style={{ color: '#c7d2fe', fontSize: 11, fontWeight: 'bold' }} numberOfLines={1}>
                {getHarnessDisplayLabel()}
              </Text>
            </TouchableOpacity>

            {/* 3. Dynamic Backend Dropdown */}
            <TouchableOpacity
              style={[styles.harnessBtn, { flex: 1.1, backgroundColor: '#1e293b', borderColor: '#10b981', borderWidth: 1, paddingVertical: 6, paddingHorizontal: 8 }]}
              onPress={() => setServerModalVisible(true)}
            >
              <Text style={{ color: '#94a3b8', fontSize: 9, fontWeight: 'bold' }}>BACKEND ▼</Text>
              <Text style={{ color: '#6ee7b7', fontSize: 11, fontWeight: 'bold' }} numberOfLines={1}>
                {SERVER_PRESETS.find(p => p.ws === wsUrl)?.label || 'Cluster LAN'}
              </Text>
            </TouchableOpacity>
          </View>
        ) : (
          <View style={[styles.modelToggleGroup, { backgroundColor: '#1e1b4b' }]}>
            <TouchableOpacity
              style={[styles.modelTab, styles.modelTabActive, { backgroundColor: '#4338ca' }]}
              onPress={() => setServerModalVisible(true)}
            >
              <Text style={[styles.modelTabTitle, styles.modelTabTitleActive]}>
                📱 Snapdragon Edge NPU (Offline)
              </Text>
              <Text style={[styles.modelTabSub, styles.modelTabSubActive]}>
                Tap to Switch to Homelab Cluster
              </Text>
            </TouchableOpacity>
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
        keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
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
              <Text style={styles.emptyTitle}>Aevum Mobile AI Harness</Text>
              <Text style={styles.emptySubtitle}>
                • Coordinator: Primary Accelerator (:8001){'\n'}
                • Worker: Worker Accelerator (:8002 - 80+ tok/s){'\n'}
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
        <KeyboardAvoidingView style={styles.modalBackdrop} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
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
                    🌐 Homelab Cluster{'\n'}(Dual Accelerator)
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
                placeholder="ws://127.0.0.1:8086"
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
                placeholder="http://127.0.0.1:8080"
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
        </KeyboardAvoidingView>
      </Modal>

      {/* Modal: Model Hub, Hugging Face Browser & Harness Studio */}
      <Modal visible={modelModalVisible} transparent animationType="slide">
        <KeyboardAvoidingView style={styles.modalBackdrop} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
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
                    <Text style={{ fontSize: 10, color: '#6ee7b7', fontWeight: 'bold' }}>CURRENTLY ACTIVE ON PRIMARY ACCELERATOR</Text>
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
                  onPress={async () => {
                    setIsLoadingClusterModels(true);
                    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                      try {
                        wsRef.current.send(JSON.stringify({ type: 'get_cluster_models' }));
                      } catch {}
                    }
                    try {
                      const ep = getHttpEndpoint();
                      const capsRes = await fetch(`${ep}/api/harness/capabilities`, { signal: AbortSignal.timeout(3500) }).then(r => r.json()).catch(() => null);
                      if (capsRes?.ok) {
                        setCapabilities(capsRes);
                        if (capsRes.models?.available_models) {
                          setClusterModels(capsRes.models.available_models);
                        }
                      }
                    } catch {}
                    setTimeout(() => setIsLoadingClusterModels(false), 500);
                  }}
                >
                  <Text style={styles.harnessBtnText}>{isLoadingClusterModels ? '⏳ Refreshing...' : '🔄 Refresh Model List'}</Text>
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

            {/* TAB 3: Comprehensive Granular Harness Parameter Studio */}
            {modelModalTab === 'params' && (
              <ScrollView style={{ maxHeight: 420 }}>
                {/* Target Selector */}
                <Text style={styles.inputSectionLabel}>ACTIVE HARNESS TARGET:</Text>
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginBottom: 12 }}>
                  {[
                    { id: 'llama_coordinator', label: '🎛️ Coord :8001' },
                    { id: 'llama_worker', label: '⚡ Worker :8002' },
                    { id: 'hermes', label: '🤖 Hermes 3' },
                    { id: 'snapdragon', label: '📱 Snapdragon' },
                    { id: 'openwebui', label: '🌐 OpenWebUI' }
                  ].map((target) => {
                    const isSelected = harnessTarget === target.id;
                    return (
                      <TouchableOpacity
                        key={target.id}
                        style={[
                          styles.samplingPill,
                          { flexGrow: 1, alignItems: 'center', paddingVertical: 6 },
                          isSelected && { backgroundColor: '#4338ca', borderColor: '#818cf8' }
                        ]}
                        onPress={() => {
                          const tid = target.id as any;
                          setHarnessTarget(tid);
                          handleLoadHarnessParams(tid);
                        }}
                      >
                        <Text style={[styles.samplingPillText, isSelected && { color: '#ffffff', fontWeight: 'bold' }]}>
                          {target.label}
                        </Text>
                      </TouchableOpacity>
                    );
                  })}
                </View>

                {/* Subtitle / Description */}
                <Text style={{ fontSize: 10, color: '#94a3b8', marginBottom: 10 }}>
                  {harnessTarget === 'llama_coordinator' && 'Primary Compute Accelerator • Direct llama-server systemd daemon'}
                  {harnessTarget === 'llama_worker' && 'Worker Accelerator • High-speed reasoning & tool execution daemon'}
                  {harnessTarget === 'hermes' && 'Hermes 3 Function-Calling & Structured Agentic ReAct runtime'}
                  {harnessTarget === 'snapdragon' && 'On-Device Edge NPU & Hexagon DSP accelerated runtime'}
                  {harnessTarget === 'openwebui' && 'LXC 119 Community WebUI Pipeline & External Model Gateway'}
                </Text>

                {/* SECTION A: LLAMA.CPP PARAMETERS (Coordinator & Worker) */}
                {(harnessTarget === 'llama_coordinator' || harnessTarget === 'llama_worker') && (
                  <View style={{ gap: 10 }}>
                    {/* Context Length */}
                    <View>
                      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Text style={styles.paramLabel}>Context Window (-c / n_ctx):</Text>
                        <Text style={{ fontSize: 11, color: '#38bdf8', fontWeight: 'bold' }}>{harnessCtx} tokens</Text>
                      </View>
                      <TextInput
                        style={[styles.textInput, { height: 38, marginTop: 4 }]}
                        keyboardType="numeric"
                        value={String(harnessCtx)}
                        onChangeText={(txt) => setHarnessCtx(parseInt(txt) || 0)}
                        placeholder="Context length (e.g. 8192)"
                        placeholderTextColor="#64748b"
                      />
                      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                        {[
                          { label: '-1k', val: Math.max(1024, harnessCtx - 1024) },
                          { label: '+1k', val: harnessCtx + 1024 },
                          { label: '4k', val: 4096 },
                          { label: '8k', val: 8192 },
                          { label: '12k', val: 12288 },
                          { label: '16k', val: 16384 },
                          { label: '32k', val: 32768 }
                        ].map((btn) => (
                          <TouchableOpacity
                            key={btn.label}
                            style={[styles.samplingPill, harnessCtx === btn.val && styles.samplingPillActive]}
                            onPress={() => setHarnessCtx(btn.val)}
                          >
                            <Text style={[styles.samplingPillText, harnessCtx === btn.val && styles.samplingPillTextActive]}>
                              {btn.label}
                            </Text>
                          </TouchableOpacity>
                        ))}
                      </View>
                    </View>

                    {/* GPU Offload Layers */}
                    <View>
                      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Text style={styles.paramLabel}>GPU Offload Layers (-ngl):</Text>
                        <Text style={{ fontSize: 11, color: '#38bdf8', fontWeight: 'bold' }}>{harnessGpuLayers} layers</Text>
                      </View>
                      <TextInput
                        style={[styles.textInput, { height: 38, marginTop: 4 }]}
                        keyboardType="numeric"
                        value={String(harnessGpuLayers)}
                        onChangeText={(txt) => setHarnessGpuLayers(parseInt(txt) || 0)}
                        placeholder="Offload layers (e.g. 99)"
                        placeholderTextColor="#64748b"
                      />
                      <View style={{ flexDirection: 'row', gap: 4, marginTop: 4 }}>
                        {[
                          { label: '0 (CPU)', val: 0 },
                          { label: '33 (Hybrid)', val: 33 },
                          { label: '99 (All GPU)', val: 99 }
                        ].map((btn) => (
                          <TouchableOpacity
                            key={btn.label}
                            style={[styles.samplingPill, { flex: 1, alignItems: 'center' }, harnessGpuLayers === btn.val && styles.samplingPillActive]}
                            onPress={() => setHarnessGpuLayers(btn.val)}
                          >
                            <Text style={[styles.samplingPillText, harnessGpuLayers === btn.val && styles.samplingPillTextActive]}>
                              {btn.label}
                            </Text>
                          </TouchableOpacity>
                        ))}
                      </View>
                    </View>

                    {/* Flash Attention */}
                    <View>
                      <Text style={styles.paramLabel}>Flash Attention (--flash-attn):</Text>
                      <View style={{ flexDirection: 'row', gap: 6, marginTop: 4 }}>
                        {(['on', 'off', 'auto'] as const).map((mode) => (
                          <TouchableOpacity
                            key={mode}
                            style={[styles.samplingPill, { flex: 1, alignItems: 'center' }, harnessFlashAttn === mode && styles.samplingPillActive]}
                            onPress={() => setHarnessFlashAttn(mode)}
                          >
                            <Text style={[styles.samplingPillText, harnessFlashAttn === mode && styles.samplingPillTextActive]}>
                              {mode.toUpperCase()}
                            </Text>
                          </TouchableOpacity>
                        ))}
                      </View>
                    </View>

                    {/* KV Cache Quantization */}
                    <View>
                      <Text style={styles.paramLabel}>KV Cache Quantization (-ctk &amp; -ctv):</Text>
                      <View style={{ flexDirection: 'row', gap: 8, marginTop: 4 }}>
                        <View style={{ flex: 1 }}>
                          <Text style={{ fontSize: 10, color: '#94a3b8', marginBottom: 2 }}>K Cache (-ctk):</Text>
                          <View style={{ flexDirection: 'row', gap: 4 }}>
                            {['q4_0', 'q8_0', 'f16'].map((q) => (
                              <TouchableOpacity
                                key={q}
                                style={[styles.samplingPill, { flex: 1, alignItems: 'center' }, harnessCacheK === q && styles.samplingPillActive]}
                                onPress={() => setHarnessCacheK(q)}
                              >
                                <Text style={[styles.samplingPillText, harnessCacheK === q && styles.samplingPillTextActive]}>{q}</Text>
                              </TouchableOpacity>
                            ))}
                          </View>
                        </View>
                        <View style={{ flex: 1 }}>
                          <Text style={{ fontSize: 10, color: '#94a3b8', marginBottom: 2 }}>V Cache (-ctv):</Text>
                          <View style={{ flexDirection: 'row', gap: 4 }}>
                            {['q4_0', 'q8_0', 'f16'].map((q) => (
                              <TouchableOpacity
                                key={q}
                                style={[styles.samplingPill, { flex: 1, alignItems: 'center' }, harnessCacheV === q && styles.samplingPillActive]}
                                onPress={() => setHarnessCacheV(q)}
                              >
                                <Text style={[styles.samplingPillText, harnessCacheV === q && styles.samplingPillTextActive]}>{q}</Text>
                              </TouchableOpacity>
                            ))}
                          </View>
                        </View>
                      </View>
                    </View>

                    {/* Batching & Compute Allocations */}
                    <View style={{ flexDirection: 'row', gap: 8 }}>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.paramLabel}>Batch Size (-b):</Text>
                        <TextInput
                          style={[styles.textInput, { height: 38, marginTop: 4 }]}
                          keyboardType="numeric"
                          value={String(harnessBatchSize)}
                          onChangeText={(txt) => setHarnessBatchSize(parseInt(txt) || 0)}
                          placeholder="2048"
                          placeholderTextColor="#64748b"
                        />
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.paramLabel}>uBatch Size (-ub):</Text>
                        <TextInput
                          style={[styles.textInput, { height: 38, marginTop: 4 }]}
                          keyboardType="numeric"
                          value={String(harnessUbatchSize)}
                          onChangeText={(txt) => setHarnessUbatchSize(parseInt(txt) || 0)}
                          placeholder="512"
                          placeholderTextColor="#64748b"
                        />
                      </View>
                    </View>

                    {/* Threads & Parallel Slots */}
                    <View style={{ flexDirection: 'row', gap: 8 }}>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.paramLabel}>Threads (-t):</Text>
                        <TextInput
                          style={[styles.textInput, { height: 38, marginTop: 4 }]}
                          keyboardType="numeric"
                          value={String(harnessThreads)}
                          onChangeText={(txt) => setHarnessThreads(parseInt(txt) || 0)}
                          placeholder="8"
                          placeholderTextColor="#64748b"
                        />
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.paramLabel}>Parallel Slots (-np):</Text>
                        <TextInput
                          style={[styles.textInput, { height: 38, marginTop: 4 }]}
                          keyboardType="numeric"
                          value={String(harnessParallel)}
                          onChangeText={(txt) => setHarnessParallel(parseInt(txt) || 0)}
                          placeholder="4"
                          placeholderTextColor="#64748b"
                        />
                      </View>
                    </View>

                    {/* Device & Custom CLI Flags */}
                    <View>
                      <Text style={styles.paramLabel}>Compute Device Flag (--device):</Text>
                      <TextInput
                        style={[styles.textInput, { height: 38, marginTop: 4 }]}
                        value={harnessDevice}
                        onChangeText={setHarnessDevice}
                        placeholder="Vulkan0, Vulkan1, CUDA0, CPU"
                        placeholderTextColor="#64748b"
                      />
                    </View>

                    <View>
                      <Text style={styles.paramLabel}>Custom CLI Arguments String:</Text>
                      <TextInput
                        style={[styles.textInput, { height: 44, marginTop: 4, fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace', fontSize: 11 }]}
                        value={harnessCustomFlags}
                        onChangeText={setHarnessCustomFlags}
                        placeholder="e.g. --rope-freq-base 1000000 --mlock"
                        placeholderTextColor="#64748b"
                      />
                    </View>

                    {/* Sampling Hyperparameters */}
                    <Text style={[styles.inputSectionLabel, { marginTop: 6 }]}>SAMPLING HYPERPARAMETERS:</Text>

                    {/* Temperature */}
                    <View>
                      <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                        <Text style={styles.paramLabel}>Temperature:</Text>
                        <Text style={{ fontSize: 11, color: '#38bdf8', fontWeight: 'bold' }}>{temperature}</Text>
                      </View>
                      <TextInput
                        style={[styles.textInput, { height: 36, marginTop: 2 }]}
                        keyboardType="decimal-pad"
                        value={String(temperature)}
                        onChangeText={(t) => setTemperature(parseFloat(t) || 0)}
                      />
                      <View style={{ flexDirection: 'row', gap: 4, marginTop: 4 }}>
                        {[0.20, 0.65, 0.78, 1.0].map((t) => (
                          <TouchableOpacity
                            key={t}
                            style={[styles.samplingPill, { flex: 1, alignItems: 'center' }, temperature === t && styles.samplingPillActive]}
                            onPress={() => setTemperature(t)}
                          >
                            <Text style={[styles.samplingPillText, temperature === t && styles.samplingPillTextActive]}>{t}</Text>
                          </TouchableOpacity>
                        ))}
                      </View>
                    </View>

                    {/* Min-P */}
                    <View>
                      <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                        <Text style={styles.paramLabel}>Min-P Sampling:</Text>
                        <Text style={{ fontSize: 11, color: '#38bdf8', fontWeight: 'bold' }}>{minP}</Text>
                      </View>
                      <TextInput
                        style={[styles.textInput, { height: 36, marginTop: 2 }]}
                        keyboardType="decimal-pad"
                        value={String(minP)}
                        onChangeText={(t) => setMinP(parseFloat(t) || 0)}
                      />
                      <View style={{ flexDirection: 'row', gap: 4, marginTop: 4 }}>
                        {[0.02, 0.05, 0.06, 0.08].map((p) => (
                          <TouchableOpacity
                            key={p}
                            style={[styles.samplingPill, { flex: 1, alignItems: 'center' }, minP === p && styles.samplingPillActive]}
                            onPress={() => setMinP(p)}
                          >
                            <Text style={[styles.samplingPillText, minP === p && styles.samplingPillTextActive]}>{p}</Text>
                          </TouchableOpacity>
                        ))}
                      </View>
                    </View>

                    {/* Top-P & Top-K */}
                    <View style={{ flexDirection: 'row', gap: 8 }}>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.paramLabel}>Top-P:</Text>
                        <TextInput
                          style={[styles.textInput, { height: 36, marginTop: 2 }]}
                          keyboardType="decimal-pad"
                          value={String(harnessTopP)}
                          onChangeText={(t) => setHarnessTopP(parseFloat(t) || 0)}
                        />
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.paramLabel}>Top-K:</Text>
                        <TextInput
                          style={[styles.textInput, { height: 36, marginTop: 2 }]}
                          keyboardType="numeric"
                          value={String(harnessTopK)}
                          onChangeText={(t) => setHarnessTopK(parseInt(t) || 0)}
                        />
                      </View>
                    </View>

                    {/* Presence Penalty */}
                    <View>
                      <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                        <Text style={styles.paramLabel}>Presence Penalty:</Text>
                        <Text style={{ fontSize: 11, color: '#38bdf8', fontWeight: 'bold' }}>{presencePenalty}</Text>
                      </View>
                      <TextInput
                        style={[styles.textInput, { height: 36, marginTop: 2 }]}
                        keyboardType="decimal-pad"
                        value={String(presencePenalty)}
                        onChangeText={(t) => setPresencePenalty(parseFloat(t) || 0)}
                      />
                      <View style={{ flexDirection: 'row', gap: 4, marginTop: 4 }}>
                        {[0.0, 0.15, 0.30, 0.50].map((pp) => (
                          <TouchableOpacity
                            key={pp}
                            style={[styles.samplingPill, { flex: 1, alignItems: 'center' }, presencePenalty === pp && styles.samplingPillActive]}
                            onPress={() => setPresencePenalty(pp)}
                          >
                            <Text style={[styles.samplingPillText, presencePenalty === pp && styles.samplingPillTextActive]}>{pp}</Text>
                          </TouchableOpacity>
                        ))}
                      </View>
                    </View>

                    {/* Repeat Penalty */}
                    <View>
                      <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                        <Text style={styles.paramLabel}>Repeat Penalty:</Text>
                        <Text style={{ fontSize: 11, color: '#38bdf8', fontWeight: 'bold' }}>{repeatPenalty}</Text>
                      </View>
                      <TextInput
                        style={[styles.textInput, { height: 36, marginTop: 2 }]}
                        keyboardType="decimal-pad"
                        value={String(repeatPenalty)}
                        onChangeText={(t) => setRepeatPenalty(parseFloat(t) || 0)}
                      />
                      <View style={{ flexDirection: 'row', gap: 4, marginTop: 4 }}>
                        {[1.0, 1.05, 1.10, 1.20].map((rp) => (
                          <TouchableOpacity
                            key={rp}
                            style={[styles.samplingPill, { flex: 1, alignItems: 'center' }, repeatPenalty === rp && styles.samplingPillActive]}
                            onPress={() => setRepeatPenalty(rp)}
                          >
                            <Text style={[styles.samplingPillText, repeatPenalty === rp && styles.samplingPillTextActive]}>{rp}</Text>
                          </TouchableOpacity>
                        ))}
                      </View>
                    </View>
                  </View>
                )}

                {/* SECTION B: HERMES 3 HARNESS */}
                {harnessTarget === 'hermes' && (
                  <View style={{ gap: 10 }}>
                    <View>
                      <Text style={styles.paramLabel}>Function-Calling Mode:</Text>
                      <View style={{ flexDirection: 'row', gap: 6, marginTop: 4 }}>
                        {['react_xml', 'tools_json', 'raw'].map((m) => (
                          <TouchableOpacity
                            key={m}
                            style={[styles.samplingPill, { flex: 1, alignItems: 'center' }, hermesToolMode === m && styles.samplingPillActive]}
                            onPress={() => setHermesToolMode(m)}
                          >
                            <Text style={[styles.samplingPillText, hermesToolMode === m && styles.samplingPillTextActive]}>{m}</Text>
                          </TouchableOpacity>
                        ))}
                      </View>
                    </View>
                    <View>
                      <Text style={styles.paramLabel}>Max ReAct Iterations:</Text>
                      <TextInput
                        style={[styles.textInput, { height: 38, marginTop: 4 }]}
                        keyboardType="numeric"
                        value={String(hermesMaxIter)}
                        onChangeText={(t) => setHermesMaxIter(parseInt(t) || 1)}
                      />
                    </View>
                    <View>
                      <Text style={styles.paramLabel}>Temperature: {temperature}</Text>
                      <View style={{ flexDirection: 'row', gap: 4, marginTop: 4 }}>
                        {[0.20, 0.60, 0.78, 1.0].map((t) => (
                          <TouchableOpacity
                            key={t}
                            style={[styles.samplingPill, { flex: 1, alignItems: 'center' }, temperature === t && styles.samplingPillActive]}
                            onPress={() => setTemperature(t)}
                          >
                            <Text style={[styles.samplingPillText, temperature === t && styles.samplingPillTextActive]}>{t}</Text>
                          </TouchableOpacity>
                        ))}
                      </View>
                    </View>
                  </View>
                )}

                {/* SECTION C: SNAPDRAGON EDGE NPU */}
                {harnessTarget === 'snapdragon' && (
                  <View style={{ gap: 10 }}>
                    <View>
                      <Text style={styles.paramLabel}>Hardware Acceleration Backend:</Text>
                      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
                        {['HTP NPU', 'Hexagon DSP', 'Adreno GPU', 'Kryo CPU'].map((b) => (
                          <TouchableOpacity
                            key={b}
                            style={[styles.samplingPill, { flexGrow: 1, alignItems: 'center' }, snapdragonBackend === b && styles.samplingPillActive]}
                            onPress={() => setSnapdragonBackend(b)}
                          >
                            <Text style={[styles.samplingPillText, snapdragonBackend === b && styles.samplingPillTextActive]}>{b}</Text>
                          </TouchableOpacity>
                        ))}
                      </View>
                    </View>
                    <View>
                      <Text style={styles.paramLabel}>Edge Context Length:</Text>
                      <TextInput
                        style={[styles.textInput, { height: 38, marginTop: 4 }]}
                        keyboardType="numeric"
                        value={String(snapdragonCtx)}
                        onChangeText={(t) => setSnapdragonCtx(parseInt(t) || 1024)}
                      />
                    </View>
                    <View>
                      <Text style={styles.paramLabel}>Weight Quantization:</Text>
                      <View style={{ flexDirection: 'row', gap: 6, marginTop: 4 }}>
                        {['INT4', 'INT8', 'FP16'].map((q) => (
                          <TouchableOpacity
                            key={q}
                            style={[styles.samplingPill, { flex: 1, alignItems: 'center' }, snapdragonQuant === q && styles.samplingPillActive]}
                            onPress={() => setSnapdragonQuant(q)}
                          >
                            <Text style={[styles.samplingPillText, snapdragonQuant === q && styles.samplingPillTextActive]}>{q}</Text>
                          </TouchableOpacity>
                        ))}
                      </View>
                    </View>
                    <View>
                      <Text style={styles.paramLabel}>Power Profile:</Text>
                      <View style={{ flexDirection: 'row', gap: 6, marginTop: 4 }}>
                        {['High Perf', 'Balanced', 'Power Saver'].map((p) => (
                          <TouchableOpacity
                            key={p}
                            style={[styles.samplingPill, { flex: 1, alignItems: 'center' }, snapdragonPower === p && styles.samplingPillActive]}
                            onPress={() => setSnapdragonPower(p)}
                          >
                            <Text style={[styles.samplingPillText, snapdragonPower === p && styles.samplingPillTextActive]}>{p}</Text>
                          </TouchableOpacity>
                        ))}
                      </View>
                    </View>
                  </View>
                )}

                {/* SECTION D: OPENWEBUI */}
                {harnessTarget === 'openwebui' && (
                  <View style={{ gap: 10 }}>
                    <View>
                      <Text style={styles.paramLabel}>OpenWebUI Server URL:</Text>
                      <TextInput
                        style={[styles.textInput, { height: 38, marginTop: 4 }]}
                        value={openwebuiUrl}
                        onChangeText={setOpenwebuiUrl}
                        placeholder="http://127.0.0.1:8080"
                        placeholderTextColor="#64748b"
                      />
                    </View>
                    <View>
                      <Text style={styles.paramLabel}>Pipeline Model ID:</Text>
                      <TextInput
                        style={[styles.textInput, { height: 38, marginTop: 4 }]}
                        value={openwebuiModel}
                        onChangeText={setOpenwebuiModel}
                        placeholder="cluster-coordinator"
                        placeholderTextColor="#64748b"
                      />
                    </View>
                    <View>
                      <Text style={styles.paramLabel}>Token Streaming:</Text>
                      <View style={{ flexDirection: 'row', gap: 6, marginTop: 4 }}>
                        {[
                          { label: 'Enabled', val: true },
                          { label: 'Disabled', val: false }
                        ].map((opt) => (
                          <TouchableOpacity
                            key={opt.label}
                            style={[styles.samplingPill, { flex: 1, alignItems: 'center' }, openwebuiStream === opt.val && styles.samplingPillActive]}
                            onPress={() => setOpenwebuiStream(opt.val)}
                          >
                            <Text style={[styles.samplingPillText, openwebuiStream === opt.val && styles.samplingPillTextActive]}>{opt.label}</Text>
                          </TouchableOpacity>
                        ))}
                      </View>
                    </View>
                  </View>
                )}

                {/* Result Message Banner */}
                {harnessApplyResult && (
                  <View style={{
                    marginTop: 12,
                    padding: 8,
                    borderRadius: 6,
                    backgroundColor: harnessApplyResult.startsWith('✅') ? '#064e3b' : harnessApplyResult.startsWith('❌') || harnessApplyResult.startsWith('⚠️') ? '#7f1d1d' : '#1e293b',
                    borderWidth: 1,
                    borderColor: harnessApplyResult.startsWith('✅') ? '#059669' : '#dc2626'
                  }}>
                    <Text style={{ fontSize: 11, color: '#f8fafc' }}>{harnessApplyResult}</Text>
                  </View>
                )}

                {/* Action Buttons */}
                <View style={{ marginTop: 14, gap: 8 }}>
                  <TouchableOpacity
                    style={[styles.harnessBtn, { backgroundColor: isApplyingHarnessParams ? '#475569' : '#2563eb', paddingVertical: 10, alignItems: 'center' }]}
                    onPress={handleApplyHarnessParams}
                    disabled={isApplyingHarnessParams}
                  >
                    {isApplyingHarnessParams ? (
                      <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
                        <ActivityIndicator size="small" color="#ffffff" />
                        <Text style={[styles.harnessBtnText, { fontWeight: 'bold' }]}>Applying to Cluster Daemon...</Text>
                      </View>
                    ) : (
                      <Text style={[styles.harnessBtnText, { fontWeight: 'bold', fontSize: 13 }]}>
                        💾 Apply to Cluster Daemon &amp; Restart
                      </Text>
                    )}
                  </TouchableOpacity>

                  <View style={{ flexDirection: 'row', gap: 8 }}>
                    <TouchableOpacity
                      style={[styles.harnessBtn, { flex: 1, backgroundColor: '#334155', paddingVertical: 8, alignItems: 'center' }]}
                      onPress={() => handleLoadHarnessParams()}
                    >
                      <Text style={styles.harnessBtnText}>🔄 Reload Live Config</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={[styles.harnessBtn, { flex: 1, backgroundColor: '#334155', paddingVertical: 8, alignItems: 'center' }]}
                      onPress={handleResetHarnessDefaults}
                    >
                      <Text style={styles.harnessBtnText}>↺ Reset Defaults</Text>
                    </TouchableOpacity>
                  </View>
                </View>
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
        </KeyboardAvoidingView>
      </Modal>

      {/* Modal: System Prompt & Hyperparameter Studio */}
      <Modal visible={promptModalVisible} transparent animationType="slide">
        <KeyboardAvoidingView style={styles.modalBackdrop} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
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
        </KeyboardAvoidingView>
      </Modal>

      {/* Modal: 24/7 Autonomous Thinking Loop Controller */}
      <Modal visible={thinkingModalVisible} transparent animationType="slide">
        <KeyboardAvoidingView style={styles.modalBackdrop} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
          <View style={[styles.modalCard, { maxHeight: '92%' }]}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
              <Text style={styles.modalTitle}>🧠 24/7 Thinking Loop</Text>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                <TouchableOpacity
                  onPress={() => handleNudgeAgent('engine', 'Autonomous Thinking Engine')}
                  disabled={nudgingAgentId === 'engine'}
                >
                  <Text style={{ color: '#facc15', fontSize: 12, fontWeight: 'bold' }}>
                    {nudgingAgentId === 'engine' ? '⏳ Nudging...' : '⚡ Nudge Loop'}
                  </Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={handleFetchThinkingStatus}>
                  <Text style={{ color: '#38bdf8', fontSize: 12, fontWeight: 'bold' }}>🔄 Refresh</Text>
                </TouchableOpacity>
              </View>
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
                style={[styles.modalButton, { backgroundColor: '#854d0e', alignItems: 'center' }]}
                onPress={() => handleNudgeAgent('engine', 'Autonomous Thinking Engine')}
                disabled={nudgingAgentId === 'engine'}
              >
                <Text style={[styles.modalButtonText, { color: '#fef08a' }]}>
                  {nudgingAgentId === 'engine' ? '⏳ Nudging Loop...' : '⚡ Nudge Loop (Break Stalls / Pauses / Preemption)'}
                </Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.modalButton, { backgroundColor: '#334155', alignItems: 'center' }]}
                onPress={() => setThinkingModalVisible(false)}
              >
                <Text style={styles.modalButtonText}>Close</Text>
              </TouchableOpacity>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* Modal: Vector Memory Search */}
      <Modal visible={memoryModalVisible} transparent animationType="slide">
        <KeyboardAvoidingView style={styles.modalBackdrop} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
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
        </KeyboardAvoidingView>
      </Modal>

      {/* Modal: Live 24/7 Agent & Inter-Model Stream Monitor */}
      <Modal visible={liveStreamModalVisible} transparent animationType="slide">
        <KeyboardAvoidingView style={styles.modalBackdrop} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
          <View style={[styles.modalCard, { height: '92%', maxHeight: '92%' }]}>
            {/* Modal Top Bar */}
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <View style={[styles.statusDot, { backgroundColor: thinkingStatus?.is_running ? '#10b981' : '#f59e0b' }]} />
                <Text style={styles.modalTitle}>📡 Live Stream & Agent Monitor</Text>
              </View>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <TouchableOpacity
                  style={{
                    flexDirection: 'row',
                    alignItems: 'center',
                    gap: 4,
                    paddingVertical: 4,
                    paddingHorizontal: 8,
                    borderRadius: 4,
                    backgroundColor: nudgingAgentId === 'engine' ? '#854d0e' : '#1e1b4b',
                    borderColor: '#facc15',
                    borderWidth: 1
                  }}
                  onPress={() => handleNudgeAgent('engine', 'Autonomous Thinking Engine')}
                  disabled={nudgingAgentId === 'engine'}
                >
                  <Text style={{ fontSize: 12 }}>⚡</Text>
                  <Text style={{ color: '#fef08a', fontSize: 11, fontWeight: 'bold' }}>
                    {nudgingAgentId === 'engine' ? 'Nudging...' : 'Nudge Loop'}
                  </Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={{
                    flexDirection: 'row',
                    alignItems: 'center',
                    gap: 4,
                    paddingVertical: 4,
                    paddingHorizontal: 8,
                    borderRadius: 4,
                    backgroundColor: isSyncingFeed ? '#1e293b' : 'transparent',
                    borderColor: '#38bdf8',
                    borderWidth: 1
                  }}
                  onPress={handleSyncFeed}
                  disabled={isSyncingFeed}
                >
                  {isSyncingFeed ? (
                    <ActivityIndicator size="small" color="#38bdf8" />
                  ) : (
                    <Text style={{ fontSize: 12 }}>🔄</Text>
                  )}
                  <Text style={{ color: '#38bdf8', fontSize: 11, fontWeight: 'bold' }}>
                    {isSyncingFeed ? 'Syncing...' : 'Sync Feed'}
                  </Text>
                </TouchableOpacity>
              </View>
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
                                    {ag.model_preference === 'worker' ? 'Worker (:8002)' : 'Coordinator (:8001)'}
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
                                        {h.tokens ? `${h.tokens} tokens • ` : ''}{formatEasternTime(h.timestamp)}
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
                              <View style={{ flexDirection: 'row', justifyContent: 'flex-end', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
                                <TouchableOpacity
                                  style={[styles.harnessBtn, { backgroundColor: '#854d0e', paddingVertical: 5, paddingHorizontal: 10 }]}
                                  onPress={() => handleNudgeAgent(ag.agent_id, ag.name)}
                                  disabled={nudgingAgentId === ag.agent_id}
                                >
                                  <Text style={{ color: '#fef08a', fontSize: 11, fontWeight: 'bold' }}>
                                    {nudgingAgentId === ag.agent_id ? '⏳ Nudging...' : '⚡ Nudge'}
                                  </Text>
                                </TouchableOpacity>
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
                                <TouchableOpacity
                                  style={[styles.harnessBtn, { backgroundColor: '#991b1b', paddingVertical: 5, paddingHorizontal: 12 }]}
                                  onPress={() => handleDeleteAgent(ag.agent_id, ag.name)}
                                >
                                  <Text style={{ color: '#fecaca', fontSize: 11, fontWeight: 'bold' }}>🗑️ Delete Agent</Text>
                                </TouchableOpacity>
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
        </KeyboardAvoidingView>
      </Modal>

      {/* Modal: Digital Person Reproduction & Genetic Crossover */}
      <Modal visible={reproduceModalVisible} transparent animationType="slide">
        <KeyboardAvoidingView style={styles.modalBackdrop} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
          <View style={[styles.modalCard, { maxHeight: '92%' }]}>
            {/* Header */}
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <Text style={{ fontSize: 18 }}>🧬</Text>
                <Text style={styles.modalTitle}>Digital Person Reproduction</Text>
              </View>
              {reproduceParentBId ? (
                <View style={[styles.samplingPill, { backgroundColor: '#064e3b' }]}>
                  <Text style={[styles.samplingPillText, { color: '#6ee7b7', fontWeight: 'bold' }]}>
                    Partner Selected
                  </Text>
                </View>
              ) : (
                <View style={[styles.samplingPill, { backgroundColor: '#7f1d1d' }]}>
                  <Text style={[styles.samplingPillText, { color: '#fca5a5', fontWeight: 'bold' }]}>
                    Choose Partner
                  </Text>
                </View>
              )}
            </View>

            <Text style={[styles.modalSubtitle, { marginBottom: 8 }]}>
              Cross-synthesize parent traits across dual GPUs (Worker :8002 & Coordinator :8001).
            </Text>

            <ScrollView
              style={{ flex: 1 }}
              nestedScrollEnabled={true}
              keyboardShouldPersistTaps="handled"
              showsVerticalScrollIndicator={true}
            >
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
                {!!reproduceParentA?.domain && (
                  <Text style={{ color: '#93c5fd', fontSize: 10, marginTop: 2 }}>Domain: {reproduceParentA.domain}</Text>
                )}
                <Text style={{ color: '#cbd5e1', fontSize: 11, marginTop: 4 }} numberOfLines={2}>
                  {reproduceParentA?.mission}
                </Text>
              </View>

              {/* Partner / Parent B Flat List */}
              <Text style={[styles.paramLabel, { marginTop: 10 }]}>Select Partner Archetype B (Tap to Choose)</Text>
              {(() => {
                const eligiblePartners = activeAgents.filter(a => a.agent_id !== reproduceParentA?.agent_id);
                if (eligiblePartners.length === 0) {
                  return (
                    <View style={[styles.modalCodeBox, { padding: 12, marginVertical: 6, backgroundColor: '#090d16' }]}>
                      <Text style={{ color: '#94a3b8', fontSize: 11, textAlign: 'center', fontStyle: 'italic' }}>
                        No other active agents available to mate. Commission at least one more agent first.
                      </Text>
                    </View>
                  );
                }

                return (
                  <View style={{ marginVertical: 4 }}>
                    {eligiblePartners.map((ag) => {
                      const isSelected = reproduceParentBId === ag.agent_id;
                      const eligibility = isEligiblePartner(reproduceParentA, ag);
                      const domainStr = ag.domain || (ag.role ? ag.role.split(' ')[0] : 'Autonomous');

                      return (
                        <TouchableOpacity
                          key={ag.agent_id}
                          activeOpacity={0.7}
                          delayPressIn={0}
                          style={{
                            padding: 12,
                            marginVertical: 4,
                            borderRadius: 8,
                            backgroundColor: isSelected ? '#1e1b4b' : '#0f172a',
                            borderColor: isSelected ? '#818cf8' : '#334155',
                            borderWidth: isSelected ? 2 : 1
                          }}
                          onPress={() => handleSelectParentB(ag.agent_id)}
                        >
                          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flex: 1 }}>
                              <Text style={{ fontSize: 14 }}>{isSelected ? '🔘' : '⚪'}</Text>
                              <Text style={{ color: isSelected ? '#a5b4fc' : '#94a3b8', fontSize: 11, fontWeight: 'bold' }}>
                                {isSelected ? 'Selected' : 'Select'}
                              </Text>
                              <Text style={{ color: isSelected ? '#ffffff' : '#e2e8f0', fontWeight: 'bold', fontSize: 13 }} numberOfLines={1}>
                                {ag.name} (Gen {ag.lineage?.generation || 1})
                              </Text>
                            </View>
                            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                              {!eligibility.eligible && (
                                <View style={[styles.agentStatusBadge, { backgroundColor: '#713f12' }]}>
                                  <Text style={{ color: '#fef08a', fontSize: 9 }}>⚠️ {eligibility.reason || 'RELATED'}</Text>
                                </View>
                              )}
                              <View style={[styles.agentStatusBadge, { backgroundColor: isSelected ? '#3730a3' : '#1e293b' }]}>
                                <Text style={{ color: isSelected ? '#c7d2fe' : '#94a3b8', fontSize: 10 }}>
                                  {ag.model_preference?.toUpperCase()}
                                </Text>
                              </View>
                            </View>
                          </View>

                          <View style={{ marginTop: 4, marginLeft: 22 }}>
                            <Text style={{ color: isSelected ? '#c7d2fe' : '#94a3b8', fontSize: 11 }}>
                              <Text style={{ fontWeight: 'bold', color: isSelected ? '#38bdf8' : '#60a5fa' }}>Role: </Text>
                              {ag.role}
                            </Text>
                            <Text style={{ color: '#64748b', fontSize: 10, marginTop: 1 }}>
                              <Text style={{ fontWeight: 'bold', color: '#818cf8' }}>Domain: </Text>
                              {domainStr}
                            </Text>
                            {!!ag.mission && (
                              <Text style={{ color: '#cbd5e1', fontSize: 10, marginTop: 2 }} numberOfLines={2}>
                                {ag.mission}
                              </Text>
                            )}
                          </View>
                        </TouchableOpacity>
                      );
                    })}
                  </View>
                );
              })()}

              {/* Genetic Crossover Blend Slider & Steppers */}
              <View style={[styles.modalCodeBox, { padding: 12, marginVertical: 8, borderColor: '#06b6d4', borderWidth: 1, backgroundColor: '#081e28' }]}>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <Text style={{ color: '#67e8f9', fontSize: 12, fontWeight: 'bold' }}>
                    🧬 Genetic Crossover Blend Ratio
                  </Text>
                  <Text style={{ color: '#a5f3fc', fontSize: 12, fontWeight: 'bold', fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace' }}>
                    {reproduceBlendRatio}% A : {100 - reproduceBlendRatio}% B
                  </Text>
                </View>

                {/* Proportional Split Visual Track */}
                <View style={{ height: 14, flexDirection: 'row', borderRadius: 7, overflow: 'hidden', backgroundColor: '#0f172a', marginVertical: 4 }}>
                  <View style={{ flex: reproduceBlendRatio, backgroundColor: '#6366f1' }} />
                  <View style={{ width: 3, backgroundColor: '#ffffff' }} />
                  <View style={{ flex: 100 - reproduceBlendRatio, backgroundColor: '#06b6d4' }} />
                </View>

                {/* Labels under track */}
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 2 }}>
                  <Text style={{ color: '#a5b4fc', fontSize: 10, fontWeight: 'bold' }} numberOfLines={1}>
                    ◀ {reproduceBlendRatio}% {reproduceParentA?.name?.split(' ')[0] || 'Parent A'}
                  </Text>
                  <Text style={{ color: '#67e8f9', fontSize: 10, fontWeight: 'bold' }} numberOfLines={1}>
                    {100 - reproduceBlendRatio}% {activeAgents.find(a => a.agent_id === reproduceParentBId)?.name?.split(' ')[0] || 'Partner'} ▶
                  </Text>
                </View>

                {/* Steppers and 5 Presets */}
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 10, justifyContent: 'center' }}>
                  <TouchableOpacity
                    delayPressIn={0}
                    activeOpacity={0.7}
                    style={[styles.harnessBtn, { backgroundColor: '#1e1b4b', borderColor: '#6366f1', borderWidth: 1, paddingVertical: 6, paddingHorizontal: 10 }]}
                    onPress={() => handleAdjustBlendRatio(reproduceBlendRatio + 5)}
                  >
                    <Text style={{ color: '#c7d2fe', fontSize: 11, fontWeight: 'bold' }}>+5% A</Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    delayPressIn={0}
                    activeOpacity={0.7}
                    style={[styles.harnessBtn, { backgroundColor: reproduceBlendRatio === 90 ? '#4338ca' : '#1e293b', borderColor: reproduceBlendRatio === 90 ? '#818cf8' : 'transparent', borderWidth: 1, paddingVertical: 6, paddingHorizontal: 8 }]}
                    onPress={() => handleAdjustBlendRatio(90)}
                  >
                    <Text style={{ color: reproduceBlendRatio === 90 ? '#ffffff' : '#cbd5e1', fontSize: 11, fontWeight: reproduceBlendRatio === 90 ? 'bold' : 'normal' }}>90 / 10</Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    delayPressIn={0}
                    activeOpacity={0.7}
                    style={[styles.harnessBtn, { backgroundColor: reproduceBlendRatio === 70 ? '#4338ca' : '#1e293b', borderColor: reproduceBlendRatio === 70 ? '#818cf8' : 'transparent', borderWidth: 1, paddingVertical: 6, paddingHorizontal: 8 }]}
                    onPress={() => handleAdjustBlendRatio(70)}
                  >
                    <Text style={{ color: reproduceBlendRatio === 70 ? '#ffffff' : '#cbd5e1', fontSize: 11, fontWeight: reproduceBlendRatio === 70 ? 'bold' : 'normal' }}>70 / 30</Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    delayPressIn={0}
                    activeOpacity={0.7}
                    style={[styles.harnessBtn, { backgroundColor: reproduceBlendRatio === 50 ? '#0f766e' : '#1e293b', borderColor: reproduceBlendRatio === 50 ? '#2dd4bf' : 'transparent', borderWidth: 1, paddingVertical: 6, paddingHorizontal: 10 }]}
                    onPress={() => handleAdjustBlendRatio(50)}
                  >
                    <Text style={{ color: reproduceBlendRatio === 50 ? '#ffffff' : '#cbd5e1', fontSize: 11, fontWeight: 'bold' }}>50/50 Balanced</Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    delayPressIn={0}
                    activeOpacity={0.7}
                    style={[styles.harnessBtn, { backgroundColor: reproduceBlendRatio === 30 ? '#0e7490' : '#1e293b', borderColor: reproduceBlendRatio === 30 ? '#38bdf8' : 'transparent', borderWidth: 1, paddingVertical: 6, paddingHorizontal: 8 }]}
                    onPress={() => handleAdjustBlendRatio(30)}
                  >
                    <Text style={{ color: reproduceBlendRatio === 30 ? '#ffffff' : '#cbd5e1', fontSize: 11, fontWeight: reproduceBlendRatio === 30 ? 'bold' : 'normal' }}>30 / 70</Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    delayPressIn={0}
                    activeOpacity={0.7}
                    style={[styles.harnessBtn, { backgroundColor: reproduceBlendRatio === 10 ? '#0e7490' : '#1e293b', borderColor: reproduceBlendRatio === 10 ? '#38bdf8' : 'transparent', borderWidth: 1, paddingVertical: 6, paddingHorizontal: 8 }]}
                    onPress={() => handleAdjustBlendRatio(10)}
                  >
                    <Text style={{ color: reproduceBlendRatio === 10 ? '#ffffff' : '#cbd5e1', fontSize: 11, fontWeight: reproduceBlendRatio === 10 ? 'bold' : 'normal' }}>10 / 90</Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    delayPressIn={0}
                    activeOpacity={0.7}
                    style={[styles.harnessBtn, { backgroundColor: '#083344', borderColor: '#06b6d4', borderWidth: 1, paddingVertical: 6, paddingHorizontal: 10 }]}
                    onPress={() => handleAdjustBlendRatio(reproduceBlendRatio - 5)}
                  >
                    <Text style={{ color: '#a5f3fc', fontSize: 11, fontWeight: 'bold' }}>+5% B</Text>
                  </TouchableOpacity>
                </View>

                <Text style={{ color: '#94a3b8', fontSize: 10, fontStyle: 'italic', textAlign: 'center', marginTop: 8 }}>
                  {reproduceBlendRatio >= 70 ? `Offspring will heavily prioritize ${reproduceParentA?.name} directives.` :
                   reproduceBlendRatio <= 30 ? `Offspring will heavily prioritize partner directives.` :
                   `Balanced synthesis blending both parent domains equally.`}
                </Text>
              </View>

              {/* Guided Crossover Intent / Bias */}
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
                    syncReproductionDraft(reproduceParentA, reproduceParentBId, val, reproduceBlendRatio);
                  }
                }}
              />

              {/* Direct 1-Tap Commission Button */}
              <TouchableOpacity
                delayPressIn={0}
                activeOpacity={0.7}
                style={[
                  styles.modalButton,
                  {
                    backgroundColor: (!reproduceParentBId || isReproducing) ? '#334155' : '#10b981',
                    alignItems: 'center',
                    marginVertical: 10,
                    paddingVertical: 14
                  }
                ]}
                disabled={!reproduceParentBId || isReproducing}
                onPress={handleSubmitReproduction}
              >
                <Text style={[styles.modalButtonText, { fontSize: 14, fontWeight: 'bold' }]}>
                  {isReproducing
                    ? '🧬 Commissioning Offspring...'
                    : reproduceParentBId
                    ? `🧬 Commission Offspring Now (${reproduceChildName || 'Blended Agent'})`
                    : 'Select a Partner Above to Commission'}
                </Text>
              </TouchableOpacity>

              {/* Optional Expandable Accordion for Custom Directives */}
              <TouchableOpacity
                delayPressIn={0}
                activeOpacity={0.7}
                style={{
                  flexDirection: 'row',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  paddingVertical: 10,
                  paddingHorizontal: 12,
                  backgroundColor: '#1e293b',
                  borderRadius: 8,
                  borderWidth: 1,
                  borderColor: '#38bdf8',
                  marginVertical: 6
                }}
                onPress={() => setShowAdvancedDirectives(prev => !prev)}
              >
                <Text style={{ color: '#38bdf8', fontSize: 12, fontWeight: 'bold' }}>
                  {showAdvancedDirectives ? '▲ Hide Persona Directives & Prompt' : '⚙️ Customize Persona & Directives (Optional) ▼'}
                </Text>
                <Text style={{ color: '#94a3b8', fontSize: 11 }}>
                  {showAdvancedDirectives ? 'Collapse' : 'Expand'}
                </Text>
              </TouchableOpacity>

              {showAdvancedDirectives && (
                <View style={{ marginTop: 8 }}>
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

                  {/* Initial Focus Directive */}
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
                      delayPressIn={0}
                      activeOpacity={0.7}
                      onPress={() => {
                        if (reproduceParentA) {
                          syncReproductionDraft(reproduceParentA, reproduceParentBId, reproduceFocus, reproduceBlendRatio);
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
                      delayPressIn={0}
                      activeOpacity={0.7}
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
                      delayPressIn={0}
                      activeOpacity={0.7}
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

                  {/* Secondary Commit Button */}
                  <TouchableOpacity
                    delayPressIn={0}
                    activeOpacity={0.7}
                    style={[styles.modalButton, { backgroundColor: '#10b981', alignItems: 'center', marginTop: 4 }]}
                    onPress={handleSubmitReproduction}
                    disabled={isReproducing || !reproduceChildName.trim() || !reproduceChildPrompt.trim()}
                  >
                    <Text style={styles.modalButtonText}>
                      {isReproducing ? '🧬 Generating Blended Digital Person...' : '🧬 Commit Customized Offspring'}
                    </Text>
                  </TouchableOpacity>
                </View>
              )}
            </ScrollView>

            {/* Modal Cancel Footer */}
            <TouchableOpacity
              delayPressIn={0}
              activeOpacity={0.7}
              style={[styles.modalButton, { backgroundColor: '#334155', marginTop: 8, alignItems: 'center' }]}
              onPress={handleCloseReproduction}
            >
              <Text style={styles.modalButtonText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
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
                  {formatEasternTime(selectedMilestone?.timestamp)}
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
