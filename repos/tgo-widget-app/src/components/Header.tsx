import React from 'react'
import styled from '@emotion/styled'
import { Maximize2, Minimize2, Sun, Moon } from 'lucide-react'
import { usePlatformStore } from '../store'
import { useTheme } from '../contexts/ThemeContext'
import { useTranslation } from 'react-i18next'

const Bar = styled.header`
  display:flex; align-items:center; gap:8px; height: 56px; padding: 0 16px;
  border-bottom: 1px solid var(--border-secondary, #eef2f4);
  background: var(--bg-primary, #fff);
`
const Title = styled.div`
  flex:1; display:flex; align-items:center; gap:8px; font-weight: 600;
  color: var(--text-primary, #111827); font-size: 15px;
`
const Logo = styled.img`
  width:20px; height:20px; display:block;
`;

const IconBtn = styled.button`
  width: 32px; height: 32px; border-radius: 8px; border: 0; background: transparent;
  color: var(--text-secondary, #6b7280); cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center;
  &:hover { background: var(--bg-hover, #f3f4f6); }
`
const ToggleExpand = styled(IconBtn)``
const ToggleTheme = styled(IconBtn)``

export default function Header({ title, onClose }: { title: string; onClose(): void }){
  const { t } = useTranslation()
  const isExpanded = usePlatformStore(s => s.isExpanded)
  const toggleExpanded = usePlatformStore(s => s.toggleExpanded)
  const cfg = usePlatformStore(s => s.config)
  const { isDark, toggleMode } = useTheme()

  const requestClose = () => {
    // Use postMessage to communicate with SDK in parent window (works cross-origin)
    try {
      window.parent?.postMessage({ type: 'tgo:hide' }, '*');
    } catch {}
    onClose && onClose();
  };

  const themeLabel = isDark ? t('header.switchToLight') : t('header.switchToDark')
  const expandLabel = isExpanded ? t('header.collapse') : t('header.expand')

  return (
    <Bar>
      <Title>
        <Logo src={cfg?.logo_url || '/logo.svg'} alt="TGO logo" width={20} height={20} />
        {title}
      </Title>
      <ToggleTheme
        aria-label={themeLabel}
        title={themeLabel}
        onClick={toggleMode}
      >
        {isDark ? <Sun size={16} /> : <Moon size={16} />}
      </ToggleTheme>
      <ToggleExpand aria-label={expandLabel} title={expandLabel} onClick={toggleExpanded}>
        {isExpanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
      </ToggleExpand>
      <IconBtn aria-label="Close" onClick={requestClose}>✕</IconBtn>
    </Bar>
  )
}

