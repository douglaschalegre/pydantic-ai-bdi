import type { AgentConfigInput, CreateAgentResponse, AgentState, AgentEvent, ChatMessage, DesireState, IntentionState } from '../types';

// Simple in-memory store for a single agent (MVP scope)
const agents: Record<string, AgentState> = {};
const listeners: Record<string, Set<(e: AgentEvent) => void>> = {};
// Track per-agent ephemeral execution details (like current step index for active intention)
interface IntentionRuntime {
  stepIndex: number;
  steps: string[];
}
const intentionRuntime: Record<string, Record<string, IntentionRuntime>> = {};

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
  // Initialize runtime step lists for each intention
  intentionRuntime[agentId] = Object.fromEntries(intentions.map(i => [i.id, {
    stepIndex: 0,
    steps: [
      'Analyze inputs',
      'Synthesize findings',
      'Draft output variant',
      'Refine & finalize'
    ]
  }]));
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
    emit(agentId, { type: 'cycle.started', at: isoNow(), cycle: nextCycle });
    // Simulate some work
    await delay(600 + Math.random() * 600);
    // Advance desires & intentions + produce chat events
    maybeAdvanceDesires(a, agentId);
    maybeAdvanceIntention(a, agentId);
    heartbeatChat(a, agentId, nextCycle);
    emit(agentId, { type: 'cycle.completed', at: isoNow(), cycle: nextCycle });
    a.cycleCount = nextCycle;
  }
}

export function mockStopAgent(agentId: string) {
  const a = agents[agentId];
  if (!a) return;
  a.status = 'stopped';
  emit(agentId, { type: 'agent.status', at: new Date().toISOString(), state: { status: 'stopped', cycleCount: a.cycleCount, lastProgressAt: new Date().toISOString(), activeIntentionId: undefined } });
  emit(agentId, { type: 'chat.message', at: new Date().toISOString(), message: { id: randomId(), at: new Date().toISOString(), sender: 'system', content: 'Agent stopped (mock).' } });
}

export function mockListAgents() {
  return Object.values(agents).map(a => ({
    agent_id: a.agentId,
    status: a.status,
    cycle_count: a.cycleCount,
    created_at: a.createdAt,
    brief: a.desires[0]?.text || ''
  }));
}

export async function mockLoadAgentState(agentId: string): Promise<AgentState | undefined> {
  await delay(150);
  return agents[agentId];
}

function maybeAdvanceDesires(a: AgentState, agentId: string) {
  const pending = a.desires.find(d => d.status === 'pending');
  if (pending && Math.random() < 0.4) {
    pending.status = 'in_progress';
    emit(agentId, { type: 'desire.updated', at: isoNow(), desire: { ...pending } });
    emit(agentId, { type: 'chat.message', at: isoNow(), message: makeSystemMsg(`Desire now in progress: ${truncate(pending.text)}`) });
  }
  const inProgress = a.desires.find(d => d.status === 'in_progress');
  if (inProgress && Math.random() < 0.25) {
    inProgress.status = 'satisfied';
    emit(agentId, { type: 'desire.updated', at: isoNow(), desire: { ...inProgress } });
    emit(agentId, { type: 'chat.message', at: isoNow(), message: makeAgentMsg(`Desire satisfied: ${truncate(inProgress.text)}`) });
  }
}

function maybeAdvanceIntention(a: AgentState, agentId: string) {
  const active = a.intentions.find(i => i.active);
  if (!active) return;
  const run = intentionRuntime[agentId]?.[active.id];
  if (!run) return;
  // Randomly decide to progress step
  if (Math.random() < 0.55) {
    run.stepIndex++;
    if (run.stepIndex < run.steps.length) {
      emit(agentId, { type: 'chat.message', at: isoNow(), message: makeAgentMsg(`Step progressed: ${run.steps[run.stepIndex]}`) });
    } else {
      // Completed intention; rotate to next intention
      emit(agentId, { type: 'chat.message', at: isoNow(), message: makeAgentMsg(`Intention completed: ${truncate(active.text)}`) });
      // Switch active intention
      const currentIdx = a.intentions.findIndex(i => i.active);
      const next = a.intentions[(currentIdx + 1) % a.intentions.length];
      a.intentions.forEach(i => i.active = false);
      next.active = true;
      a.activeIntentionId = next.id;
      emit(agentId, { type: 'intention.updated', at: isoNow(), intention: { ...next } });
      // Reset runtime for new active
      const newRun = intentionRuntime[agentId]?.[next.id];
      if (newRun) newRun.stepIndex = 0;
    }
  }
}

function heartbeatChat(a: AgentState, agentId: string, cycle: number) {
  if (Math.random() < 0.35) {
    emit(agentId, { type: 'chat.message', at: isoNow(), message: makeSystemMsg(`Heartbeat after cycle ${cycle}`) });
  }
}

function makeSystemMsg(content: string): ChatMessage {
  return { id: randomId(), at: isoNow(), sender: 'system', content };
}
function makeAgentMsg(content: string): ChatMessage {
  return { id: randomId(), at: isoNow(), sender: 'agent', content };
}
function truncate(text: string, max = 60) { return text.length <= max ? text : text.slice(0, max - 1) + '…'; }
function isoNow() { return new Date().toISOString(); }

function delay(ms: number) { return new Promise(res => setTimeout(res, ms)); }
