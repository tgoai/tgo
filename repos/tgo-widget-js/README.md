# TGO Widget App (Vite + React + Emotion)

一个类似 Intercom 的客服小窗口 Widget 示例：React 18 + Vite 5 + Emotion（@emotion/react + @emotion/styled）。

## 功能
- 顶部导航栏：标题 + 关闭按钮
- 消息列表：滚动区域、左右两侧气泡
- 输入区域：圆角输入框 + 发送按钮（支持回车）
- Emotion 样式注入：可在 DevTools 中看到 `<style data-emotion="tgo">` 与 `<style data-emotion="tgo-global">`
- 生产构建时 Emotion 默认通过 CSSOM insertRule 注入规则（style 标签内容看似为空，但在 `sheet.cssRules` 中存在）
- 响应式：小屏幕下全屏显示

## 运行
```bash
cd tgo-widget-js
npm install
npm run dev          # http://localhost:5173
# 生产预览
npm run build
npm run preview      # http://localhost:5174
```

## 结构
```
./tgo-widget-js
  ├─ index.html
  ├─ package.json
  ├─ tsconfig.json
  ├─ tsconfig.node.json
  ├─ vite.config.ts
  └─ src/
     ├─ main.tsx
     ├─ App.tsx
     ├─ styles/
     │  └─ emotionCache.ts   # key = "tgo" → <style data-emotion="tgo">
     └─ components/
        ├─ Header.tsx
        ├─ MessageList.tsx
        └─ MessageInput.tsx
```

## 验证 Emotion 的 insertRule 注入
在生产预览页面的控制台执行：
```js
[...document.querySelectorAll('style[data-emotion]')].map(s => ({
  key: s.getAttribute('data-emotion'),
  rules: s.sheet?.cssRules.length
}))
```
如果 `rules > 0` 即表示规则已通过 CSSOM 注入（即使 `<style>` 标签没有文本）。

