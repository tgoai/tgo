import { formatSystemMessageContent, type SystemMessageExtra } from '../../types/chat'
import { SystemMessageWrapper, SystemMessageInner } from './messageStyles'
import { useTranslation } from 'react-i18next'

export type SystemMessageProps = {
  type: number
  content: string
  extra?: SystemMessageExtra[]
}

export default function SystemMessage({ type, content, extra }: SystemMessageProps) {
  const { t } = useTranslation()

  const getFormattedContent = () => {
    const params: Record<string, string> = {}
    if (extra && Array.isArray(extra)) {
      extra.forEach((item, index) => {
        params[`name${index}`] = item?.name || item?.uid || ''
      })
    }

    switch (type) {
      case 1000: // SYSTEM_STAFF_ASSIGNED
        return t('system.staffAssigned', { ...params, defaultValue: formatSystemMessageContent(content, extra) })
      case 1001: // SYSTEM_SESSION_CLOSED
        if (!extra || extra.length === 0) {
          return t('system.sessionClosedNoAgent', { defaultValue: 'Session ended.' })
        }
        return t('system.sessionClosed', { ...params, defaultValue: formatSystemMessageContent(content, extra) })
      case 1002: // SESSION_TRANSFERRED
        return t('system.sessionTransferred', { ...params, defaultValue: formatSystemMessageContent(content, extra) })
      default:
        return formatSystemMessageContent(content, extra)
    }
  }

  const formattedContent = getFormattedContent()
  
  return (
    <SystemMessageWrapper>
      <SystemMessageInner>
        {formattedContent}
      </SystemMessageInner>
    </SystemMessageWrapper>
  )
}

