import { Command } from 'commander';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { TgoClient } from '../client.js';

// Use vi.hoisted so the mock is available during vi.mock hoisting
const { mockWkimSend, mockEnsure } = vi.hoisted(() => {
  const mockWkimSend = vi.fn();
  const mockEnsure = vi.fn();
  return { mockWkimSend, mockEnsure };
});

// Mock the wukongim module — chatSend now uses WebSocket
vi.mock('../wukongim.js', () => ({
  ensureWuKongIMConnected: mockEnsure,
  getSharedWuKongIMClient: vi.fn(),
  WuKongIMClient: vi.fn(),
}));

function mockClient() {
  return {
    get: vi.fn().mockResolvedValue({}),
    post: vi.fn().mockResolvedValue({}),
    delete: vi.fn().mockResolvedValue({}),
    token: 'test-token',
    serverUrl: 'http://localhost:8000',
  } as unknown as TgoClient & {
    post: ReturnType<typeof vi.fn>;
    delete: ReturnType<typeof vi.fn>;
  };
}

describe('chat commands', () => {
  beforeEach(() => {
    mockWkimSend.mockReset().mockResolvedValue({
      messageId: 'msg-123',
      messageSeq: 1,
      reasonCode: 1,
    });
    mockEnsure.mockReset().mockResolvedValue({
      isConnected: true,
      uid: 'test-user-staff',
      send: mockWkimSend,
    });
  });

  describe('chatSend', () => {
    it('should send message via WuKongIM WebSocket', async () => {
      const { chatSend } = await import('./chat.js');
      const client = mockClient();
      const result = await chatSend(client, {
        channel_id: 'ch-1',
        channel_type: 1,
        message: 'Hello!',
      });
      expect(result).toHaveProperty('messageId', 'msg-123');
      expect(result).toHaveProperty('messageSeq', 1);
      expect(result).toHaveProperty('clientMsgNo');
      expect(result).toHaveProperty('status', 'sent');
    });

    it('should pass correct payload to WuKongIM send', async () => {
      const { chatSend } = await import('./chat.js');
      const client = mockClient();
      await chatSend(client, {
        channel_id: 'ch-1',
        channel_type: 2,
        message: 'Test message',
      });
      expect(mockEnsure).toHaveBeenCalledWith(client);
      expect(mockWkimSend).toHaveBeenCalledWith(
        'ch-1',
        2,
        { content: 'Test message', type: 1 },
        expect.any(String),
      );
    });
  });

  describe('chatSendPlatform', () => {
    it('should POST message via HTTP API to /v1/chat/messages/send', async () => {
      const { chatSendPlatform } = await import('./chat.js');
      const client = mockClient();
      await chatSendPlatform(client, {
        channel_id: 'ch-1',
        channel_type: 251,
        message: 'Hello!',
      });
      expect(client.post).toHaveBeenCalledWith('/v1/chat/messages/send', {
        channel_id: 'ch-1',
        channel_type: 251,
        payload: { content: 'Hello!', type: 1 },
        client_msg_no: undefined,
      });
    });
  });

  describe('registerChatCommands', () => {
    it('should register only the chat agent command', async () => {
      const { registerChatCommands } = await import('./chat.js');
      const client = mockClient();

      const program = new Command();
      program.option('--server <url>').option('--token <token>');
      const root = program.command('root');

      registerChatCommands(root);

      const chat = root.commands.find((cmd) => cmd.name() === 'chat');
      expect(chat?.commands.some((cmd) => cmd.name() === 'agent')).toBe(true);
      expect(chat?.commands.some((cmd) => cmd.name() === 'team')).toBe(false);
      expect(client.post).not.toHaveBeenCalled();
    });
  });

  describe('chatAgent', () => {
    it('should POST to /v1/chat/agent with agent_id', async () => {
      const { chatAgent } = await import('./chat.js');
      const client = mockClient();
      await chatAgent(client, { message: 'Hi', agent_id: 'agent-1' });
      expect(client.post).toHaveBeenCalledWith('/v1/chat/agent', {
        message: 'Hi',
        agent_id: 'agent-1',
      });
    });
  });

  describe('chatClearMemory', () => {
    it('should DELETE /v1/chat/memory with query params', async () => {
      const { chatClearMemory } = await import('./chat.js');
      const client = mockClient();
      await chatClearMemory(client, { channel_id: 'ch-1', channel_type: 251 });
      expect(client.delete).toHaveBeenCalledWith('/v1/chat/memory?channel_id=ch-1&channel_type=251');
    });
  });
});
