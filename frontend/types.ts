// Minimal data contracts for single-screen MVP
// These mirror conceptual backend objects; may evolve.

export interface AgentConfigInput {
  brief: string; // Natural language description of goals
}

export type DesireStatus = 'pending' | 'in_progress' | 'satisfied';
export interface DesireState {
  id: string;
  text: string;
  status: DesireStatus;
}

export interface IntentionState {
  id: string;
  text: string;
  active: boolean;
  paused?: boolean;
}

export interface AgentState {
  agentId: string;
  createdAt: string;
  status: 'initializing' | 'running' | 'stopped' | 'error';
  cycleCount: number;
  lastProgressAt?: string;
  desires: DesireState[];
  intentions: IntentionState[];
  activeIntentionId?: string;
}

export type ChatSender = 'user' | 'agent' | 'system' | 'tool' | 'error';
export interface ChatMessage {
  id: string;
  at: string; // ISO timestamp
  sender: ChatSender;
  content: string;
  meta?: Record<string, unknown>;
}

// Real-time events to update UI
export type EventType =
  | 'cycle.started'
  | 'cycle.completed'
  | 'desire.updated'
  | 'intention.updated'
  | 'chat.message'
  | 'agent.status'
  | 'error';

export interface BaseEvent<T extends EventType = EventType> {
  type: T;
  at: string;
}

export interface CycleStartedEvent extends BaseEvent<'cycle.started'> {
  cycle: number;
}
export interface CycleCompletedEvent extends BaseEvent<'cycle.completed'> {
  cycle: number;
}
export interface DesireUpdatedEvent extends BaseEvent<'desire.updated'> {
  desire: DesireState;
}
export interface IntentionUpdatedEvent extends BaseEvent<'intention.updated'> {
  intention: IntentionState;
}
export interface ChatMessageEvent extends BaseEvent<'chat.message'> {
  message: ChatMessage;
}
export interface AgentStatusEvent extends BaseEvent<'agent.status'> {
  state: Pick<AgentState, 'status' | 'cycleCount' | 'lastProgressAt' | 'activeIntentionId'>;
}
export interface ErrorEvent extends BaseEvent<'error'> {
  error: string;
}

export type AgentEvent =
  | CycleStartedEvent
  | CycleCompletedEvent
  | DesireUpdatedEvent
  | IntentionUpdatedEvent
  | ChatMessageEvent
  | AgentStatusEvent
  | ErrorEvent;

// Mock API responses
export interface CreateAgentResponse {
  state: AgentState;
  initialMessages?: ChatMessage[];
}
