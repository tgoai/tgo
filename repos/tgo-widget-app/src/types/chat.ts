import type { ReasonCode } from 'easyjssdk'

// Status is now used for transient states like uploading and sending.
export type MessageStatus = 'uploading' | 'sending'


// Message payload types (discriminated union)
export type TextMessagePayload = {
  type: 1
  content: string
}

export type ImageMessagePayload = {
  type: 2
  url: string
  width: number
  height: number
}

export type FileMessagePayload = {
  type: 3
  content: string
  url: string
  name: string
  size: number
}


export type MixedMessagePayload = {
  type: 12
  content: string
  images: Array<{
    url: string
    width: number
    height: number
  }>
  file?: {
    url: string
    name: string
    size: number
  }
}


export type CommandMessagePayload = {
  type: 99
  cmd: string
  param: Record<string, any>
}

// AI Loading indicator (shown while AI is thinking/preparing response)
export type AILoadingMessagePayload = {
  type: 100
}

// System message (type 1000-2000), e.g. "您已接入人工客服，客服{0} 将为您服务"
export type SystemMessageExtra = {
  uid?: string
  name?: string
  [key: string]: any
}

export type SystemMessagePayload = {
  type: number // 1000-2000
  content: string
  extra?: SystemMessageExtra[]
}

// Helper to check if a payload type is a system message
export function isSystemMessageType(type: number): boolean {
  return type >= 1000 && type <= 2000
}

// Format system message content by replacing {0}, {1}, etc. with extra data
export function formatSystemMessageContent(content: string, extra?: SystemMessageExtra[]): string {
  if (!extra || !Array.isArray(extra)) return content
  let result = content
  extra.forEach((item, index) => {
    const name = item?.name || item?.uid || ''
    result = result.replace(new RegExp(`\\{${index}\\}`, 'g'), name)
  })
  return result
}

// Regular message payloads (non-system)
export type RegularMessagePayload = TextMessagePayload | ImageMessagePayload | FileMessagePayload | MixedMessagePayload | CommandMessagePayload | AILoadingMessagePayload

// All message payloads including system messages
export type MessagePayload = RegularMessagePayload | SystemMessagePayload

export type ChatMessage = {
  id: string
  role: 'agent' | 'user'
  payload: MessagePayload
  time: Date
  // Align with RecvMessage
  messageSeq?: number
  clientMsgNo?: string
  fromUid?: string
  channelId?: string
  channelType?: number
  // Incremental streaming data (if present, prefer displaying this)
  streamData?: string
  // Transient state while uploading/sending
  status?: MessageStatus
  // Upload progress & error (for attachments)
  uploadProgress?: number
  uploadError?: string
  // Final send result detail from SDK; Success/Failure codes
  reasonCode?: ReasonCode
  // AI 处理错误信息（来自 ___TextMessageEnd 事件的 data 字段或离线消息的 error 字段）
  errorMessage?: string
}
