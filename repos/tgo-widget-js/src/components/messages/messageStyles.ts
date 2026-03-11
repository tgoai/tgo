import styled from '@emotion/styled'

export const Bubble = styled.div<{self:boolean}>`
  display: inline-block;
  max-width: var(--bubble-max-width, 380px);
  width: auto;
  padding: 0px 14px;
  border-radius: 16px;
  line-height: 1.6;
  background: ${p => p.self ? 'var(--primary)' : 'var(--bg-bubble-agent, #f5f6f7)'};
  color: ${p => p.self ? '#fff' : 'var(--text-primary, #111827)'};
  border-top-${p => p.self ? 'right' : 'left'}-radius: 6px;
  word-break: break-word;
  overflow-wrap: anywhere;

  /* Code block styling with dark mode support */
  pre {
    overflow: auto;
    margin: 8px 0;
    padding: 12px;
    border-radius: 8px;
    background: var(--bg-code, #f6f8fa);
  }
  pre code {
    background: transparent;
    padding: 0;
  }
  code {
    font-family: ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;
    font-size: 12px;
    background: var(--bg-code-inline, rgba(0,0,0,0.05));
    padding: 2px 6px;
    border-radius: 4px;
  }

  /* Override highlight.js background for dark mode */
  .hljs {
    background: var(--bg-code, #f6f8fa) !important;
    color: var(--text-primary, #111827);
  }

  a { color: ${p => p.self ? '#fff' : 'var(--link-color, #2563eb)'}; text-decoration: underline; }

  /* Ensure images in markdown don't overflow the bubble */
  img {
    max-width: 100%;
    height: auto;
    display: block;
    border-radius: 8px;
    margin: 8px 0;
  }
`

export const Cursor = styled.span`
  display:inline-block; width:6px; height:1em; margin-left:2px; background: currentColor;
  animation: blink 1s steps(1) infinite;
  @keyframes blink { 0%{opacity:1} 50%{opacity:0} 100%{opacity:1} }
`

// AI Loading indicator (three bouncing dots)
export const AILoadingDots = styled.span`
  display: inline-flex; align-items: center; gap: 4px; padding: 8px 0;
  span {
    display: inline-block; width: 6px; height: 6px; background: var(--text-muted, #9ca3af); border-radius: 50%;
    animation: bounce 1.4s ease-in-out infinite both;
  }
  span:nth-of-type(1) { animation-delay: -0.32s; }
  span:nth-of-type(2) { animation-delay: -0.16s; }
  span:nth-of-type(3) { animation-delay: 0s; }
  @keyframes bounce {
    0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; }
    40% { transform: scale(1); opacity: 1; }
  }
`

export const ImgBox = styled.div`
  display:inline-block; background: var(--bg-tertiary, #f3f4f6); border-radius:12px; overflow:hidden; padding:4px; cursor:pointer;
`;
export const ImgEl = styled.img`
  display:block; width:100%; height:100%; object-fit:contain; background: var(--bg-tertiary, #f3f4f6);
`;

export const Grid = styled.div`
  display: grid; gap: 6px; width: 100%;
`;
export const GridItem = styled.div`
  position: relative; background: var(--bg-tertiary, #f3f4f6); border-radius:8px; overflow:hidden; aspect-ratio:1/1; cursor:pointer;
`;
export const GridImg = styled.img`
  width:100%; height:100%; object-fit:cover; display:block; background: var(--bg-tertiary, #f3f4f6);
`;

// File message UI
export const FileCard = styled.div`
  display:flex; align-items:center; gap:12px; padding:12px; border:1px solid var(--border-primary, #e5e7eb); border-radius:12px;
  background: var(--bg-primary, #fff); color: var(--text-primary, #111827); max-width: var(--bubble-max-width, 380px); cursor:pointer; transition: box-shadow .15s ease, background-color .15s ease;
  &:hover{ box-shadow: 0 6px 20px rgba(0,0,0,.12); background: var(--bg-hover, #f9fafb); }
`;
export const FileIconBox = styled.div`
  width:48px; height:48px; display:grid; place-items:center; border-radius:8px; background: var(--bg-tertiary, #f3f4f6); flex:0 0 auto;
`;
export const FileInfo = styled.div`
  flex:1; min-width:0; display:flex; flex-direction:column; gap:4px;
`;
export const FileName = styled.div`
  font-size:14px; color: var(--text-primary, #111827); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
`;
export const FileSize = styled.div`
  font-size:12px; color: var(--text-secondary, #6b7280);
`;
export const FileAction = styled.a`
  color: var(--text-secondary, #6b7280); flex:0 0 auto; display:grid; place-items:center; padding:4px; border-radius:6px; text-decoration:none;
  &:hover{ background: var(--bg-tertiary, #f3f4f6); }
`;

// System message (WeChat-style centered notification)
export const SystemMessageWrapper = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  padding: 4px 0;
`;

export const SystemMessageInner = styled.span`
  display: inline-block;
  max-width: 80%;
  padding: 4px 12px;
  font-size: 12px;
  color: var(--text-secondary, #6b7280);
  background: var(--bg-system-msg, rgba(0, 0, 0, 0.04));
  border-radius: 4px;
  text-align: center;
  line-height: 1.5;
  word-break: break-word;
`;

