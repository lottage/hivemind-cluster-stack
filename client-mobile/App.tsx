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
  Alert
} from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';

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

const DEFAULT_CLUSTER_WS = 'ws://127.0.0.1:8086';
const DEFAULT_LOCAL_EDGE_HTTP = 'http://127.0.0.1:8080';

const DEFAULT_SYSTEM_PROMPT = `You are StoneSage, the 24/7 Autonomous Multi-Node Cluster Orchestrator and Cognitive Companion for Proxmox Datacenter 'home'.

## 1. System Topology & Dual-GPU Infrastructure:
- Compute Host VM 102 ('ubu' @ 127.0.0.1 on Proxmox Node 1 'pve'):
  • Coordinator (:8001): Ornith-1.5-9B-OBLITERATED Q8_0 on AMD Radeon RX 6750 XT 12GB (Vulkan0). Handles complex multi-file architectural planning, unrestricted code synthesis, math reasoning, and hypothesis evaluation.
  • Worker (:8002): Ornith-1.5-9B Q4_K_M on AMD Radeon RX 6600 XT 8GB (Vulkan1). Handles fast divergent ideation, unit testing, schema validation, and ambient routines at 80+ tokens/sec.
  • Embedder (:8003): bge-large-en-v1.5 on RX 6600 XT. 1024-dimensional dense semantic embeddings (< 512 token context window).
  • Cluster MCP Bridge (:8765): Starlette JSON-RPC / SSE daemon managing tools, autonomous loops, and preemption.

## 2. Knowledge Fabric & Vector Memory (Qdrant @ 127.0.0.1:6333):
- Active Collections:
  • codebase_knowledge: Full homelab architecture, configs, scripts, hardware registries.
  • agent_memories: Persistent architectural decisions, technical lessons, and operational invariants.
  • autonomous_thinking: 24/7 dual-model exploration dossiers, failure boundaries, and novelty discoveries.
  • obsidian_vault: ClusterAdmin's personal knowledge base, technical notes, and active project graphs (synced via CouchDB on LXC 116 @ 127.0.0.1:5984).
  • home_automation_registry: Smart home entity catalogs, sensor states, and automation scripts.

## 3. Homelab Services & Smart Home Fleet:
- Proxmox Datacenter API VIP: https://127.0.0.1:8006 (Unified management of 'pve' and 'bigserv').
- Home Assistant OS (VM 103 @ 127.0.0.1:8123): Smart home devices, switches, climate, Nest thermostat.
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

  const [inputPrompt, setInputPrompt] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [expandedThoughts, setExpandedThoughts] = useState<Record<string, boolean>>({});
  const [confirmModal, setConfirmModal] = useState<ToolConfirmRequest | null>(null);

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

  const wsRef = useRef<WebSocket | null>(null);
  const scrollViewRef = useRef<ScrollView | null>(null);

  useEffect(() => {
    if (connectionMode === 'cluster') {
      connectWebSocket();
    } else {
      if (wsRef.current) wsRef.current.close();
      setIsConnected(true); // Connected to local on-device loop
      setSelectedModel('on_device');
      checkLocalEdgeHealth();
    }
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, [connectionMode, wsUrl, localEdgeUrl]);

  const connectWebSocket = () => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
      };

      ws.onclose = () => {
        setIsConnected(false);
      };

      ws.onerror = () => {
        setIsConnected(false);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleWebSocketMessage(data);
        } catch (e) {
          console.error('Failed to parse WS message:', e);
        }
      };
    } catch (err) {
      setIsConnected(false);
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
      setIsLoopActionPending(false);
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

  const handleFetchThinkingStatus = () => {
    if (wsRef.current && isConnected) {
      setIsLoopActionPending(true);
      wsRef.current.send(JSON.stringify({ type: 'get_thinking_status' }));
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

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.safeArea}>
        <StatusBar barStyle="light-content" backgroundColor="#0f172a" />

      {/* Top Harness Bar */}
      <View style={styles.header}>
        <View style={styles.headerTopRow}>
          <View>
            <Text style={styles.title}>StoneSage Mobile</Text>
            {/* Mode Switcher Badge */}
            <TouchableOpacity onPress={() => setEdgeSettingsVisible(true)}>
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
                      ? 'Cluster: LXC 120 (ONLINE)'
                      : 'Cluster: OFFLINE (Tap to Switch)'
                    : localEdgeHealthy
                    ? 'On-Device Edge: 127.0.0.1 (ONLINE)'
                    : 'On-Device Edge: (Offline Mode)'}
                </Text>
              </View>
            </TouchableOpacity>
          </View>

          {/* Quick Harness Tools */}
          <View style={styles.harnessActionRow}>
            <TouchableOpacity
              style={styles.harnessBtn}
              onPress={() => setEdgeSettingsVisible(true)}
            >
              <Text style={styles.harnessBtnText}>⚙️ Engine</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.harnessBtn, { backgroundColor: '#334155' }]}
              onPress={() => setPromptModalVisible(true)}
            >
              <Text style={styles.harnessBtnText}>📝 Tuning</Text>
            </TouchableOpacity>
            {connectionMode === 'cluster' && (
              <>
                <TouchableOpacity
                  style={[styles.harnessBtn, { backgroundColor: '#4f46e5' }]}
                  onPress={() => {
                    handleFetchThinkingStatus();
                    setThinkingModalVisible(true);
                  }}
                >
                  <Text style={styles.harnessBtnText}>🧠 24/7 Loop</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.harnessBtn}
                  onPress={() => setMemoryModalVisible(true)}
                >
                  <Text style={styles.harnessBtnText}>🔍 Memory</Text>
                </TouchableOpacity>
              </>
            )}
          </View>
        </View>

        {/* Model Tabs */}
        {connectionMode === 'cluster' ? (
          <View style={styles.modelToggleGroup}>
            <TouchableOpacity
              style={[styles.modelTab, selectedModel === 'coordinator' && styles.modelTabActive]}
              onPress={() => setSelectedModel('coordinator')}
            >
              <Text style={[styles.modelTabText, selectedModel === 'coordinator' && styles.modelTabTextActive]}>
                Ornith-9B Q8_0 (RX 6750 XT)
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.modelTab, selectedModel === 'worker' && styles.modelTabActive]}
              onPress={() => setSelectedModel('worker')}
            >
              <Text style={[styles.modelTabText, selectedModel === 'worker' && styles.modelTabTextActive]}>
                Ornith-9B Q4 (RX 6600 XT)
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.modelTab, selectedModel === 'frontier' && styles.modelTabActive]}
              onPress={() => setSelectedModel('frontier')}
            >
              <Text style={[styles.modelTabText, selectedModel === 'frontier' && styles.modelTabTextActive]}>
                Frontier
              </Text>
            </TouchableOpacity>
          </View>
        ) : (
          <View style={[styles.modelToggleGroup, { backgroundColor: '#1e1b4b' }]}>
            <View style={[styles.modelTab, styles.modelTabActive, { backgroundColor: '#4338ca' }]}>
              <Text style={[styles.modelTabText, styles.modelTabTextActive]}>
                📱 Snapdragon 8 Elite • Local Edge Ornith-1.5-9B
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

      {/* Chat Messages */}
      <ScrollView
        ref={scrollViewRef}
        style={styles.messageContainer}
        contentContainerStyle={styles.messageContent}
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
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
      >
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

      {/* Modal: Engine Connection & Offline Model Loader */}
      <Modal visible={edgeSettingsVisible} transparent animationType="slide">
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>⚡ Inference Engine & Offline Loader</Text>
            <Text style={styles.modalSubtitle}>
              Select runtime compute location or configure offline on-device loading.
            </Text>

            {/* Mode Selector Toggle */}
            <View style={{ flexDirection: 'row', gap: 8, marginVertical: 10 }}>
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

            {/* Offline Loader Details */}
            <Text style={styles.inputSectionLabel}>Local On-Device Engine Endpoint:</Text>
            <TextInput
              style={[styles.textInput, { height: 42, marginBottom: 10 }]}
              value={localEdgeUrl}
              onChangeText={setLocalEdgeUrl}
              placeholder="http://127.0.0.1:8080"
              placeholderTextColor="#64748b"
            />

            <Text style={styles.inputSectionLabel}>Target Local GGUF Model Path:</Text>
            <TextInput
              style={[styles.textInput, { height: 42, marginBottom: 10 }]}
              value={localModelPath}
              onChangeText={setLocalModelPath}
              placeholder="/storage/emulated/0/Download/Ornith-1.5-9B-Q4_K_M.gguf"
              placeholderTextColor="#64748b"
            />

            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginVertical: 8 }}>
              <Text style={{ fontSize: 12, color: '#94a3b8' }}>
                Engine Status: {localEdgeHealthy ? '🟢 ONLINE' : '🟡 Awaiting local server'}
              </Text>
              <TouchableOpacity
                style={[styles.harnessBtn, { backgroundColor: '#2563eb' }]}
                onPress={checkLocalEdgeHealth}
              >
                <Text style={styles.harnessBtnText}>Test Ping</Text>
              </TouchableOpacity>
            </View>

            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={[styles.modalButton, { backgroundColor: '#334155' }]}
                onPress={() => setEdgeSettingsVisible(false)}
              >
                <Text style={styles.modalButtonText}>Save & Close</Text>
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
                  <View style={{ flexDirection: 'row', gap: 4, marginTop: 4 }}>
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
                  <View style={{ flexDirection: 'row', gap: 4, marginTop: 4 }}>
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
                <View style={{ flexDirection: 'row', gap: 4, marginTop: 4 }}>
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
                  <View style={{ flexDirection: 'row', gap: 4, marginTop: 4 }}>
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
                  <View style={{ flexDirection: 'row', gap: 4, marginTop: 4 }}>
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

            <ScrollView style={{ maxHeight: 340 }}>
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
                  <View style={{ flexDirection: 'row', gap: 4 }}>
                    {[60, 120, 300, 600].map((sec) => (
                      <TouchableOpacity
                        key={sec}
                        style={[styles.samplingPill, thinkingInterval === sec && styles.samplingPillActive]}
                        onPress={() => setThinkingInterval(sec)}
                      >
                        <Text style={[styles.samplingPillText, thinkingInterval === sec && styles.samplingPillTextActive]}>
                          {sec}s
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>

                <View style={{ flex: 1 }}>
                  <Text style={styles.inputSectionLabel}>PRIORITY</Text>
                  <View style={{ flexDirection: 'row', gap: 4 }}>
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
  harnessActionRow: {
    flexDirection: 'row',
    gap: 8
  },
  harnessBtn: {
    backgroundColor: '#334155',
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 6
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
    alignItems: 'center',
    borderRadius: 6
  },
  modelTabActive: {
    backgroundColor: '#2563eb'
  },
  modelTabText: {
    fontSize: 10,
    color: '#94a3b8',
    fontWeight: '600'
  },
  modelTabTextActive: {
    color: '#ffffff'
  },
  samplingBar: {
    flexDirection: 'row',
    alignItems: 'center',
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
  }
});
