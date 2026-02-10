import type { Socket } from 'socket.io-client';
import { registerSessionHandlers } from './sessionHandlers';
import { registerJudgmentHandlers } from './judgmentHandlers';
import { registerNarrativeHandlers } from './narrativeHandlers';
import { registerActHandlers } from './actHandlers';

/**
 * Register all socket event handlers on the given socket instance.
 * Each handler module manages a specific domain of events.
 */
export function registerAllSocketHandlers(socket: Socket) {
  registerSessionHandlers(socket);
  registerJudgmentHandlers(socket);
  registerNarrativeHandlers(socket);
  registerActHandlers(socket);
}
