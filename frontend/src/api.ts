import type { AgentConfigInput, CreateAgentResponse, AgentEvent, AgentState, ChatMessage, DesireState, IntentionState } from '../types';

const API_BASE = import.meta.env?.VITE_API_BASE || 'http://localhost:8000';
const USE_REAL_API = import.meta.env?.VITE_USE_REAL_API === 'true';

export const apiMode = USE_REAL_API ? 'real' : 'mock';

async function jsonFetch<T>(url: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(url, { ...opts, headers: { 'Content-Type': 'application/json', ...(opts?.headers || {}) } });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status} ${res.statusText}: ${text}`);
  }
  return res.json() as Promise<T>;
}

interface RawAgentState {
  agent_id: string;
  status: string;
  cycle_count: number;
  last_progress_at?: string;
  desires: { id: string; text: string; status: string }[];
  intentions: { id: string; text: string; active: boolean; paused?: boolean }[];
  active_intention_id?: string;
  created_at?: string;
}
interface RawCreateAgentResponse { state: RawAgentState; initial_messages: ChatMessage[] }
interface RawAgentListItem { agent_id: string; status: string; cycle_count: number; created_at: string; brief: string }

export async function createAgentReal(input: AgentConfigInput): Promise<CreateAgentResponse> {
  const body = JSON.stringify({ brief: input.brief });
  const data = await jsonFetch<RawCreateAgentResponse>(`${API_BASE}/agents`, { method: 'POST', body });
  return { state: normalizeState(data.state), initialMessages: data.initial_messages ?? [] };
}

export async function stopAgentReal(agentId: string): Promise<void> {
  await fetch(`${API_BASE}/agents/${agentId}/stop`, { method: 'POST' });
}

export async function listAgentsReal(): Promise<RawAgentListItem[]> {
  return jsonFetch<RawAgentListItem[]>(`${API_BASE}/agents`);
}

export async function loadAgentState(agentId: string): Promise<AgentState> {
  const raw = await jsonFetch<RawAgentState>(`${API_BASE}/agents/${agentId}`);
  return normalizeState(raw);
}

export function openEventStream(agentId: string, onEvent: (evt: AgentEvent) => void): () => void {
  const url = `${API_BASE}/agents/${agentId}/events`;
  const es = new EventSource(url);

  const handler = (ev: MessageEvent) => {
    if (!ev.data) return;
    try {
      console.debug('SSE event', ev.type, ev.data);
      const parsed = JSON.parse(ev.data);
      onEvent(normalizeEvent(parsed));
    } catch (e) {
      console.warn('Failed to parse SSE event', ev.type, e);
    }
  };

  // Server sends explicit 'event: <type>' so default onmessage won't fire; register each expected event name.
  const eventTypes = [
    'cycle.started',
    'cycle.completed',
    'desire.updated',
    'intention.updated',
    'chat.message',
    'agent.status',
    'error'
  ];
  eventTypes.forEach(t => es.addEventListener(t, handler as EventListener));

  // Fallback for unexpected events (if server ever omits 'event:' line)
  es.onmessage = handler;

  es.onerror = (e) => {
    console.warn('EventSource error / reconnect', e);
  };
  return () => {
    eventTypes.forEach(t => es.removeEventListener(t, handler as EventListener));
    es.close();
  };
}

const allowedStatuses = ['initializing','running','stopped','error'] as const;
type AllowedStatus = typeof allowedStatuses[number];

function isAllowedStatus(s: string): s is AllowedStatus {
  return (allowedStatuses as readonly string[]).includes(s);
}

function normalizeState(raw: RawAgentState): AgentState {
  return {
    agentId: raw.agent_id,
    status: isAllowedStatus(raw.status) ? raw.status : 'initializing',
    cycleCount: raw.cycle_count,
    lastProgressAt: raw.last_progress_at,
    desires: (raw.desires || []).map((d): DesireState => ({ id: d.id, text: d.text, status: d.status as DesireState['status'] })),
    intentions: (raw.intentions || []).map((i): IntentionState => ({ id: i.id, text: i.text, active: !!i.active, paused: !!i.paused })),
    activeIntentionId: raw.active_intention_id,
    createdAt: raw.created_at || new Date().toISOString()
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function normalizeEvent(raw: any): AgentEvent {
  switch (raw.type) {
    case 'cycle.started':
    case 'cycle.completed':
      return { type: raw.type, at: raw.at, cycle: raw.cycle } as AgentEvent;
    case 'desire.updated':
      return { type: raw.type, at: raw.at, desire: raw.desire } as AgentEvent;
    case 'intention.updated':
      return { type: raw.type, at: raw.at, intention: raw.intention } as AgentEvent;
    case 'chat.message':
      return { type: raw.type, at: raw.at, message: raw.message } as AgentEvent;
    case 'agent.status':
      return { type: raw.type, at: raw.at, state: raw.state } as AgentEvent;
    case 'error':
      return { type: raw.type, at: raw.at, error: raw.error } as AgentEvent;
    default:
      return raw as AgentEvent;
  }
}

// Fallback exports (the App will choose based on apiMode)
export const realApi = { createAgentReal, openEventStream, stopAgentReal, listAgentsReal, loadAgentState };
