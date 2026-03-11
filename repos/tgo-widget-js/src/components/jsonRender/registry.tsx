import type { CSSProperties } from 'react'
import { useBoundProp, type ComponentRegistry, type ComponentRenderProps } from '@json-render/react'

type JsonRenderProps = Record<string, unknown>

function toStringValue(value: unknown, fallback = ''): string {
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return fallback
}

function toNumberValue(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') {
    const parsed = Number(value.replace(/[^0-9.+-]/g, ''))
    if (Number.isFinite(parsed)) return parsed
  }
  return undefined
}

function toBool(value: unknown): boolean {
  if (typeof value === 'boolean') return value
  if (typeof value === 'string') return value === 'true'
  return false
}

function pickFirstString(props: JsonRenderProps, keys: string[], fallback = ''): string {
  for (const key of keys) {
    const value = toStringValue(props[key])
    if (value) return value
  }
  return fallback
}

function splitLabelValue(rawText: string): { label: string; value: string } | null {
  const text = rawText.trim()
  if (!text) return null
  const matched = text.match(/^([^:：]{1,24})[:：]\s*(.+)$/)
  if (!matched) return null
  const label = matched[1].trim()
  const value = matched[2].trim()
  if (!label || !value) return null
  return { label, value }
}

function isSectionTitle(text: string): boolean {
  return /^(商品详情|支付信息|收货信息|订单信息|物流信息|商品明细|支付详情|配送信息|订单详情|items|payment|shipping|order)$/i.test(text.trim())
}

function isHeadlineKey(label: string): boolean {
  return /(实付金额|应付金额|支付金额|合计|总额|payable|grand total|total)/i.test(label)
}

function isDiscountKey(label: string): boolean {
  return /(优惠|折扣|减免|discount|coupon)/i.test(label)
}

function isMetaKey(label: string): boolean {
  return /(订单号|sku|数量|qty|电话|联系人|收货地址|地址|物流单号|tracking)/i.test(label)
}

const baseTextStyle: CSSProperties = {
  color: 'var(--text-primary, #111827)',
  fontSize: 14,
  lineHeight: 1.6,
}

const mutedTextStyle: CSSProperties = {
  color: 'var(--text-secondary, #6b7280)',
  fontSize: 12,
  lineHeight: 1.5,
}

const Text = ({ element }: ComponentRenderProps<JsonRenderProps>) => {
  const props = element.props
  const text = pickFirstString(props, ['text', 'label', 'value', 'content'])
  const variant = toStringValue(props.variant).toLowerCase()
  if (!text) return null

  const pair = splitLabelValue(text)
  const renderedAsSection = variant === 'section-title' || isSectionTitle(text)
  if (renderedAsSection) {
    return <div style={{ ...baseTextStyle, fontWeight: 700, marginTop: 8 }}>{text}</div>
  }

  if (pair && variant !== 'plain') {
    const headline = variant === 'headline' || isHeadlineKey(pair.label)
    const discount = variant === 'discount' || isDiscountKey(pair.label)
    const meta = variant === 'meta' || isMetaKey(pair.label)

    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          gap: 8,
          paddingTop: headline ? 6 : 0,
          marginTop: headline ? 4 : 0,
          borderTop: headline ? '1px solid var(--border-primary, #e5e7eb)' : 'none',
        }}
      >
        <span style={meta ? mutedTextStyle : { ...baseTextStyle, color: 'var(--text-secondary, #6b7280)' }}>{pair.label}</span>
        <span
          style={{
            fontSize: headline ? 17 : 14,
            fontWeight: headline ? 700 : 600,
            color: headline
              ? '#dc2626'
              : discount
                ? '#059669'
                : 'var(--text-primary, #111827)',
          }}
        >
          {pair.value}
        </span>
      </div>
    )
  }

  if (variant === 'caption' || variant === 'muted') {
    return <div style={mutedTextStyle}>{text}</div>
  }

  if (variant === 'title') {
    return <div style={{ ...baseTextStyle, fontSize: 16, fontWeight: 700 }}>{text}</div>
  }

  return <div style={baseTextStyle}>{text}</div>
}

const Button = ({ element, children, emit, loading }: ComponentRenderProps<JsonRenderProps>) => {
  const props = element.props
  const label = pickFirstString(props, ['label', 'text'], 'Submit')
  const variant = toStringValue(props.variant).toLowerCase()
  const primary = toBool(props.primary) || variant === 'primary'
  const danger = variant === 'danger'
  const link = variant === 'link'
  const isDisabled = toBool(props.disabled) || loading

  const style: CSSProperties = link
    ? {
        border: 'none',
        background: 'transparent',
        color: 'var(--primary, #2f80ed)',
        textDecoration: 'underline',
        padding: 0,
      }
    : primary
      ? {
          border: 'none',
          background: 'var(--primary, #2f80ed)',
          color: '#fff',
          padding: '8px 14px',
          borderRadius: 10,
          fontWeight: 600,
        }
      : danger
        ? {
            border: 'none',
            background: '#ef4444',
            color: '#fff',
            padding: '8px 14px',
            borderRadius: 10,
            fontWeight: 600,
          }
        : {
            border: '1px solid var(--border-primary, #e5e7eb)',
            background: 'var(--bg-primary, #fff)',
            color: 'var(--text-primary, #111827)',
            padding: '8px 14px',
            borderRadius: 10,
            fontWeight: 600,
          }

  return (
    <button
      type="button"
      onClick={() => {
        if (!isDisabled) emit('press')
      }}
      disabled={isDisabled}
      style={{ ...style, cursor: isDisabled ? 'not-allowed' : 'pointer', opacity: isDisabled ? 0.6 : 1 }}
    >
      {loading ? 'Loading...' : (children ?? label)}
    </button>
  )
}

const ButtonGroup = ({ children }: ComponentRenderProps<JsonRenderProps>) => {
  return <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>{children}</div>
}

const Card = ({ element, children }: ComponentRenderProps<JsonRenderProps>) => {
  const variant = toStringValue(element.props.variant).toLowerCase()
  const orderLike = variant === 'order' || variant === 'invoice'
  return (
    <div
      style={{
        border: orderLike ? '1px solid #dbeafe' : '1px solid var(--border-primary, #e5e7eb)',
        background: orderLike ? 'linear-gradient(180deg, #ffffff 0%, #eff6ff 100%)' : 'var(--bg-primary, #fff)',
        borderRadius: 14,
        padding: 12,
        boxShadow: '0 1px 2px rgba(0,0,0,0.06)',
      }}
    >
      {children}
    </div>
  )
}

const Image = ({ element }: ComponentRenderProps<JsonRenderProps>) => {
  const src = pickFirstString(element.props, ['url', 'src'])
  if (!src) return null
  const alt = pickFirstString(element.props, ['alt'], 'image')
  return <img src={src} alt={alt} style={{ maxWidth: '100%', borderRadius: 10, display: 'block' }} />
}

const Row = ({ element, children }: ComponentRenderProps<JsonRenderProps>) => {
  const justify = toStringValue(element.props.justify).toLowerCase()
  const align = toStringValue(element.props.align).toLowerCase()
  const wrap = toBool(element.props.wrap)

  const justifyContent = justify === 'between' ? 'space-between' : justify === 'center' ? 'center' : justify === 'end' ? 'flex-end' : 'flex-start'
  const alignItems = align === 'center' ? 'center' : align === 'end' ? 'flex-end' : 'flex-start'

  return (
    <div style={{ display: 'flex', flexDirection: 'row', justifyContent, alignItems, gap: 8, flexWrap: wrap ? 'wrap' : 'nowrap' }}>
      {children}
    </div>
  )
}

const Column = ({ children }: ComponentRenderProps<JsonRenderProps>) => {
  return <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>{children}</div>
}

const Divider = () => <hr style={{ border: 'none', borderTop: '1px solid var(--border-primary, #e5e7eb)', margin: '4px 0' }} />

const Badge = ({ element, children }: ComponentRenderProps<JsonRenderProps>) => {
  const tone = toStringValue(element.props.tone).toLowerCase()
  const label = children ?? pickFirstString(element.props, ['label', 'text', 'value'], '')
  if (!label) return null

  const toneStyle: CSSProperties =
    tone === 'success'
      ? { background: '#dcfce7', color: '#166534' }
      : tone === 'warning'
        ? { background: '#fef3c7', color: '#92400e' }
        : tone === 'danger'
          ? { background: '#fee2e2', color: '#991b1b' }
          : { background: '#dbeafe', color: '#1d4ed8' }

  return (
    <span style={{ ...toneStyle, display: 'inline-flex', borderRadius: 999, padding: '2px 8px', fontSize: 12, fontWeight: 600 }}>
      {label}
    </span>
  )
}

const Section = ({ element, children }: ComponentRenderProps<JsonRenderProps>) => {
  const title = pickFirstString(element.props, ['title', 'label', 'text'])
  return (
    <section style={{ border: '1px solid var(--border-primary, #e5e7eb)', borderRadius: 12, background: '#f9fafb', padding: 10 }}>
      {title ? <div style={{ ...baseTextStyle, fontWeight: 700 }}>{title}</div> : null}
      <div style={{ marginTop: title ? 8 : 0, display: 'flex', flexDirection: 'column', gap: 6 }}>{children}</div>
    </section>
  )
}

const KV = ({ element }: ComponentRenderProps<JsonRenderProps>) => {
  const label = pickFirstString(element.props, ['label', 'key', 'name'])
  const value = pickFirstString(element.props, ['value', 'text', 'amount'])
  const highlight = toBool(element.props.highlight) || isHeadlineKey(label)
  if (!label && !value) return null

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'baseline',
        justifyContent: 'space-between',
        gap: 8,
        paddingTop: highlight ? 6 : 0,
        borderTop: highlight ? '1px solid var(--border-primary, #e5e7eb)' : 'none',
      }}
    >
      <span style={highlight ? { ...baseTextStyle, fontWeight: 600 } : { ...baseTextStyle, color: 'var(--text-secondary, #6b7280)' }}>{label}</span>
      <span style={highlight ? { ...baseTextStyle, fontSize: 16, fontWeight: 700, color: '#dc2626' } : { ...baseTextStyle, fontWeight: 600 }}>{value}</span>
    </div>
  )
}

const PriceRow = ({ element }: ComponentRenderProps<JsonRenderProps>) => {
  const props = element.props
  const label = pickFirstString(props, ['label', 'title', 'name'])
  const rawValue = props.amount ?? props.value ?? props.text
  const valueText = toStringValue(rawValue)
  const numeric = toNumberValue(rawValue)
  const currency = pickFirstString(props, ['currency'], '¥')
  const emphasis = toBool(props.emphasis) || isHeadlineKey(label)
  const discount = toBool(props.discount) || isDiscountKey(label) || (numeric !== undefined && numeric < 0)

  const shownValue = valueText || (numeric !== undefined ? `${currency}${Math.abs(numeric).toFixed(2)}` : '')
  if (!label && !shownValue) return null

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'baseline',
        justifyContent: 'space-between',
        gap: 8,
        paddingTop: emphasis ? 6 : 0,
        marginTop: emphasis ? 4 : 0,
        borderTop: emphasis ? '1px solid var(--border-primary, #e5e7eb)' : 'none',
      }}
    >
      <span style={emphasis ? { ...baseTextStyle, fontWeight: 600 } : { ...baseTextStyle, color: 'var(--text-secondary, #6b7280)' }}>{label}</span>
      <span
        style={
          emphasis
            ? { ...baseTextStyle, fontSize: 18, fontWeight: 700, color: '#dc2626' }
            : discount
              ? { ...baseTextStyle, fontWeight: 600, color: '#059669' }
              : { ...baseTextStyle, fontWeight: 600 }
        }
      >
        {discount && numeric !== undefined && numeric > 0 ? `-${currency}${numeric.toFixed(2)}` : shownValue}
      </span>
    </div>
  )
}

const OrderItem = ({ element }: ComponentRenderProps<JsonRenderProps>) => {
  const name = pickFirstString(element.props, ['name', 'title', 'label'])
  const sku = pickFirstString(element.props, ['sku'])
  const quantity = pickFirstString(element.props, ['quantity', 'qty'], '1')
  const price = pickFirstString(element.props, ['subtotal', 'price', 'amount'])

  if (!name && !price) return null

  return (
    <div style={{ border: '1px solid var(--border-primary, #e5e7eb)', borderRadius: 10, background: 'var(--bg-primary, #fff)', padding: 10 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ ...baseTextStyle, fontWeight: 600 }}>{name}</div>
          {sku ? <div style={mutedTextStyle}>SKU: {sku}</div> : null}
        </div>
        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          <div style={mutedTextStyle}>x{quantity}</div>
          <div style={{ ...baseTextStyle, fontWeight: 700 }}>{price}</div>
        </div>
      </div>
    </div>
  )
}

const Input = ({ element, bindings }: ComponentRenderProps<JsonRenderProps>) => {
  const props = element.props
  const [value, setValue] = useBoundProp<string | undefined>(toStringValue(props.value), bindings?.value)
  const label = toStringValue(props.label)
  const placeholder = toStringValue(props.placeholder)

  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4, ...baseTextStyle }}>
      {label ? <span>{label}</span> : null}
      <input
        style={{ border: '1px solid var(--border-primary, #e5e7eb)', borderRadius: 8, padding: '8px 10px' }}
        value={value ?? ''}
        placeholder={placeholder}
        onChange={(e) => setValue(e.target.value)}
      />
    </label>
  )
}

const Checkbox = ({ element, bindings }: ComponentRenderProps<Record<string, unknown>>) => {
  const props = element.props
  // Accept value, checked, or selected as the bound prop
  const rawValue = props.value ?? props.checked ?? props.selected
  const bindingPath = bindings?.value ?? bindings?.checked ?? bindings?.selected
  const [value, setValue] = useBoundProp<boolean | undefined>(toBool(rawValue), bindingPath)
  const label = toStringValue(props.label) || toStringValue(props.text)

  return (
    <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, ...baseTextStyle }}>
      <input type="checkbox" checked={Boolean(value)} onChange={(e) => setValue(e.target.checked)} />
      <span>{label}</span>
    </label>
  )
}

const DateTimeInput = ({ element, bindings }: ComponentRenderProps<Record<string, unknown>>) => {
  const props = element.props
  // Accept value, date, or selectedDate as the bound prop
  const rawValue = props.value ?? props.date ?? props.selectedDate
  const bindingPath = bindings?.value ?? bindings?.date ?? bindings?.selectedDate
  const [value, setValue] = useBoundProp<string | undefined>(toStringValue(rawValue), bindingPath)
  const label = toStringValue(props.label)

  // Respect mode prop (date/time/datetime) as well as enableDate/enableTime
  const mode = toStringValue(props.mode).toLowerCase() || toStringValue(props.type).toLowerCase()
  const enableDate = mode ? mode !== 'time' : props.enableDate !== false
  const enableTime = mode ? (mode === 'time' || mode === 'datetime' || mode === 'datetime-local') : props.enableTime !== false
  const type = enableDate && enableTime ? 'datetime-local' : enableDate ? 'date' : 'time'

  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4, ...baseTextStyle }}>
      {label ? <span>{label}</span> : null}
      <input
        type={type}
        style={{ border: '1px solid var(--border-primary, #e5e7eb)', borderRadius: 8, padding: '8px 10px' }}
        value={value ?? ''}
        onChange={(e) => setValue(e.target.value)}
      />
    </label>
  )
}

const MultipleChoice = ({ element, bindings }: ComponentRenderProps<Record<string, unknown>>) => {
  const props = element.props
  const rawOptions = Array.isArray(props.options) ? props.options : []
  const options = rawOptions
    .map((item: unknown) => {
      // Handle string shorthand: "身份证" → { label: "身份证", value: "身份证" }
      if (typeof item === 'string') {
        return item ? { label: item, value: item } : null
      }
      if (typeof item !== 'object' || item === null) return null
      const obj = item as Record<string, unknown>
      return {
        label: toStringValue(obj.label),
        value: toStringValue(obj.value),
      }
    })
    .filter((item: { label: string; value: string } | null): item is { label: string; value: string } => item !== null && item.value.length > 0)

  // Accept value, selectedValue, or selectedValues as the bound prop
  const rawValue = props.value ?? props.selectedValue ?? props.selectedValues
  const initialValue = Array.isArray(rawValue) ? toStringValue(rawValue[0]) : toStringValue(rawValue)
  const bindingPath = bindings?.value ?? bindings?.selectedValue ?? bindings?.selectedValues
  const [value, setValue] = useBoundProp<string | undefined>(initialValue, bindingPath)
  const label = toStringValue(props.label)

  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4, ...baseTextStyle }}>
      {label ? <span>{label}</span> : null}
      <select
        style={{ border: '1px solid var(--border-primary, #e5e7eb)', borderRadius: 8, padding: '8px 10px' }}
        value={value ?? ''}
        onChange={(e) => setValue(e.target.value)}
      >
        <option value="">Select</option>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label || opt.value}
          </option>
        ))}
      </select>
    </label>
  )
}

const List = ({ children }: ComponentRenderProps<JsonRenderProps>) => {
  return <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>{children}</div>
}

const Unknown = ({ element, children }: ComponentRenderProps<JsonRenderProps>) => {
  return (
    <div style={{ border: '1px solid #f59e0b', borderRadius: 8, background: '#fffbeb', padding: 8 }}>
      <div style={{ fontSize: 12, color: '#b45309' }}>Unsupported component: {element.type}</div>
      {children}
    </div>
  )
}

export const jsonRenderRegistry: ComponentRegistry = {
  Text,
  Button,
  ButtonGroup,
  Actions: ButtonGroup,
  Card,
  Section,
  SectionCard: Section,
  KV,
  KeyValue: KV,
  PriceRow,
  AmountRow: PriceRow,
  Badge,
  StatusBadge: Badge,
  OrderItem,
  LineItem: OrderItem,
  Image,
  Row,
  Column,
  List,
  Divider,
  Input,
  TextField: Input,
  Checkbox,
  CheckBox: Checkbox,
  DateTimeInput,
  MultipleChoice,
}

export const jsonRenderFallback = Unknown
