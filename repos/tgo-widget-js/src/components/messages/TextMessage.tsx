import MarkdownContent from '../MarkdownContent'

export interface TextMessageProps {
  content: string
  onSendMessage?: (message: string) => void
}

export default function TextMessage({ content, onSendMessage }: TextMessageProps){
  if (!content) return null
  return <MarkdownContent content={content} onSendMessage={onSendMessage} />
}

