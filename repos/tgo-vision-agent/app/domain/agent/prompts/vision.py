"""Prompt templates for the vision model.

The vision model is a VLM that analyzes screenshots and returns
structured information about the screen state.
"""

SCREEN_ANALYSIS_PROMPT = """分析这张 Android 屏幕截图，返回结构化信息。

## 分析重点
{focus}

## 任务目标（供参考）
{goal}

## 输出格式
返回 JSON 格式：
{{
  "screen_type": "屏幕类型",
  "app_state": {{
    "app_name": "当前应用名称",
    "is_foreground": true,
    "login_status": "登录状态",
    "screen_type": "具体屏幕类型"
  }},
  "visible_elements": [
    {{
      "type": "元素类型",
      "text": "元素文本",
      "position": {{"x": 100, "y": 200, "width": 50, "height": 30}},
      "clickable": true,
      "enabled": true,
      "style": "primary"
    }}
  ],
  "suggested_actions": ["建议的动作1", "建议的动作2"],
  "raw_description": "屏幕的详细描述...",
  "needs_scroll": false
}}

## 屏幕类型说明
- app_store_home: 应用商店首页
- app_store_search: 应用商店搜索页
- app_store_detail: 应用详情页
- app_installing: 应用正在安装
- chat_list: 聊天列表页
- chat_detail: 聊天详情页
- qr_code: 登录二维码页
- login: 登录页面
- home_screen: 系统桌面/主屏幕
- settings: 设置页面
- terms_agreement: 用户协议/隐私政策弹窗（通常有"同意"按钮）
- permission_dialog: 权限请求弹窗（如存储、通知权限）
- update_dialog: 更新提示弹窗
- alert_dialog: 一般警告/提示弹窗
- ad_popup: 广告弹窗
- loading: 加载中/等待页面
- other: 其他类型

## 登录状态
- logged_in: 已登录
- qr_pending: 等待扫码
- offline: 离线/未登录
- expired: 登录过期
- unknown: 无法判断

## 按钮状态说明
- **enabled: true** - 按钮可点击，颜色鲜艳（蓝色、绿色等主色调）
- **enabled: false** - 按钮禁用，颜色灰暗或透明度高，不可点击
- **style 类型**:
  - "primary": 主要按钮（蓝色/绿色大按钮）
  - "secondary": 次要按钮（灰色/白色小按钮）
  - "disabled": 禁用状态的按钮
  - "text": 文字链接按钮

## 协议弹窗特殊处理
- 对于 terms_agreement 类型的屏幕：
  - **needs_scroll: true** 如果协议内容较长，可能需要滚动才能激活同意按钮
  - 如果"同意"按钮是灰色/禁用状态，设置 enabled: false

## 重要提示
1. visible_elements 只列出关键的可交互元素（最多10个）
2. position 的 x, y 是元素的**中心点坐标**
3. suggested_actions 基于当前屏幕给出建议（最多5个）
4. raw_description 详细描述屏幕内容，帮助决策
5. 如果看到加载中/转圈，在 raw_description 中说明
6. **对于协议弹窗**，务必判断 needs_scroll 和按钮的 enabled 状态
"""

ELEMENT_LOCATION_PROMPT = """在这张屏幕截图中精确定位指定的 UI 元素。

## 目标元素
{element}

## 输出格式
如果找到元素，返回：
{{
  "found": true,
  "position": {{
    "x": 540,
    "y": 800,
    "width": 200,
    "height": 60
  }},
  "confidence": 0.95,
  "enabled": true,
  "description": "找到了目标元素，位于屏幕中央偏下..."
}}

如果未找到元素，返回：
{{
  "found": false,
  "position": null,
  "confidence": 0,
  "enabled": false,
  "description": "未找到目标元素，屏幕上显示的是..."
}}

## 坐标定位规则（重要！）
1. **x, y 必须是元素中心点的坐标**，不是左上角！
2. 假设屏幕分辨率为 1080x1920（宽x高）
3. 屏幕底部按钮的 y 坐标通常在 1500-1800 范围
4. 屏幕中央的 y 坐标约为 960
5. 弹窗内的按钮位置取决于弹窗本身的位置

## 按钮状态识别
- **enabled: true** - 按钮颜色鲜艳（如蓝色、绿色），可以点击
- **enabled: false** - 按钮颜色灰暗或透明度高，处于禁用状态
- 对于协议弹窗的"同意"按钮，如果需要先滚动才能激活，enabled 应为 false

## 定位精度要求
1. 仔细观察目标元素的实际位置，给出精确的中心点坐标
2. 如果元素在弹窗中，先确定弹窗的位置，再定位弹窗内的元素
3. 如果有多个匹配元素，选择最明显/最相关的那个
4. confidence 表示定位准确度 (0-1)，不确定时应降低
5. 如果元素被遮挡、部分可见或处于禁用状态，在 description 中说明
"""

ACTION_VERIFICATION_PROMPT = """比较这两张截图，验证动作是否成功执行。

第一张是动作执行前的截图，第二张是动作执行后的截图。

## 预期变化
{expected_change}

## 输出格式
{{
  "success": true/false,
  "explanation": "验证结果的详细解释",
  "actual_change": "实际观察到的变化",
  "screen_changed": true/false
}}

## 判断标准
1. 如果预期变化已发生，success = true
2. 如果屏幕完全没变化，success = false
3. 如果变化与预期不同但任务可能仍在进行，在 explanation 中说明
"""
