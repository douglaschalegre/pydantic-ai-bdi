import type { AgentConfigInput, CreateAgentResponse, AgentState, AgentEvent, ChatMessage, DesireState, IntentionState } from '../types';

// Simple in-memory store for a single agent (MVP scope)
const agents: Record<string, AgentState> = {};
const listeners: Record<string, Set<(e: AgentEvent) => void>> = {};

function randomId() { return Math.random().toString(36).slice(2, 10); }

export async function mockCreateAgent(input: AgentConfigInput): Promise<CreateAgentResponse> {
  await delay(300); // simulate network
  const agentId = randomId();
  const desires: DesireState[] = [
    { id: randomId(), text: input.brief.slice(0, 80) + ' (core goal)', status: 'in_progress' },
    { id: randomId(), text: 'Produce summarized presentation outline', status: 'pending' }
  ];
  const intentions: IntentionState[] = [
    { id: randomId(), text: 'Collect recent commit data', active: true },
    { id: randomId(), text: 'Cluster themes', active: false },
    { id: randomId(), text: 'Draft summary slides', active: false }
  ];
  const state: AgentState = {
    agentId,
    createdAt: new Date().toISOString(),
    status: 'running',
    cycleCount: 0,
    desires,
    intentions,
    activeIntentionId: intentions[0].id
  };
  agents[agentId] = state;
  listeners[agentId] = new Set();
  startSimulationLoop(agentId);
  const initialMessages: ChatMessage[] = [
    { id: randomId(), at: new Date().toISOString(), sender: 'system', content: 'Agent created and running.' }
  ];
  return { state, initialMessages };
}

export function mockSubscribe(agentId: string, cb: (evt: AgentEvent) => void): () => void {
  listeners[agentId]?.add(cb);
  return () => listeners[agentId]?.delete(cb);
}

function emit(agentId: string, evt: AgentEvent) {
  listeners[agentId]?.forEach(l => l(evt));
}

async function startSimulationLoop(agentId: string) {
  while (agents[agentId] && agents[agentId].status === 'running') {
    const a = agents[agentId];
    const nextCycle = a.cycleCount + 1;
    emit(agentId, { type: 'cycle.started', at: new Date().toISOString(), cycle: nextCycle });
    // Simulate some work
    await delay(600 + Math.random() * 600);
    // Randomly mark a pending desire as in_progress or satisfied
    maybeAdvanceDesires(a, agentId);
    emit(agentId, { type: 'cycle.completed', at: new Date().toISOString(), cycle: nextCycle });
    a.cycleCount = nextCycle;
  }
}

function maybeAdvanceDesires(a: AgentState, agentId: string) {
  const pending = a.desires.find(d => d.status === 'pending');
  if (pending && Math.random() < 0.4) {
    pending.status = 'in_progress';
    emit(agentId, { type: 'desire.updated', at: new Date().toISOString(), desire: { ...pending } });
  }
  const inProgress = a.desires.find(d => d.status === 'in_progress');
  if (inProgress && Math.random() < 0.3) {
    inProgress.status = 'satisfied';
    emit(agentId, { type: 'desire.updated', at: new Date().toISOString(), desire: { ...inProgress } });
  }
  // Intention switching
  const currentIdx = a.intentions.findIndex(i => i.active);
  if (Math.random() < 0.35) {
    a.intentions.forEach(i => i.active = false);
    const next = a.intentions[(currentIdx + 1) % a.intentions.length];
    next.active = true;
    a.activeIntentionId = next.id;
    emit(agentId, { type: 'intention.updated', at: new Date().toISOString(), intention: { ...next } });
  }
}

function delay(ms: number) { return new Promise(res => setTimeout(res, ms)); }
