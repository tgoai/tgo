import MarkdownContent from '../MarkdownContent'

export interface MixedMessageProps {
  content: string
  onSendMessage?: (message: string) => void
}

export default function MixedMessage({ content, onSendMessage }: MixedMessageProps){
  if (!content) return null
  return <MarkdownContent content={content} onSendMessage={onSendMessage} />
}

