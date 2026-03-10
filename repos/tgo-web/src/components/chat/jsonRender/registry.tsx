import { useBoundProp, type ComponentRegistry, type ComponentRenderProps } from '@json-render/react';

type JsonRenderProps = Record<string, unknown>;

function toStringValue(value: unknown, fallback = ''): string {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return fallback;
}

function toNumberValue(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string') {
    const parsed = Number(value.replace(/[^0-9.+-]/g, ''));
    if (Number.isFinite(parsed)) return parsed;
  }
  return undefined;
}

function toBool(value: unknown): boolean {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'string') return value === 'true';
  return false;
}

function pickFirstString(props: JsonRenderProps, keys: string[], fallback = ''): string {
  for (const key of keys) {
    const value = toStringValue(props[key]);
    if (value) return value;
  }
  return fallback;
}

function splitLabelValue(rawText: string): { label: string; value: string } | null {
  const text = rawText.trim();
  if (!text) return null;
  const matched = text.match(/^([^:：]{1,24})[:：]\s*(.+)$/);
  if (!matched) return null;
  const label = matched[1].trim();
  const value = matched[2].trim();
  if (!label || !value) return null;
  return { label, value };
}

function isSectionTitle(text: string): boolean {
  return /^(商品详情|支付信息|收货信息|订单信息|物流信息|商品明细|支付详情|配送信息|订单详情|items|payment|shipping|order)$/i.test(text.trim());
}

function isSkuLine(text: string): boolean {
  return /^sku[:：]/i.test(text.trim());
}

function isHeadlineKey(label: string): boolean {
  return /(实付金额|应付金额|支付金额|合计|总额|payable|grand total|total)/i.test(label);
}

function isDiscountKey(label: string): boolean {
  return /(优惠|折扣|减免|discount|coupon)/i.test(label);
}

function isMetaKey(label: string): boolean {
  return /(订单号|sku|数量|qty|电话|联系人|收货地址|地址|物流单号|tracking)/i.test(label);
}

const Text = ({ element }: ComponentRenderProps<JsonRenderProps>) => {
  const props = element.props;
  const text = pickFirstString(props, ['text', 'label', 'value', 'content']);
  const variant = toStringValue(props.variant).toLowerCase();

  if (!text) return null;

  const pair = splitLabelValue(text);
  const renderedAsSection = variant === 'section-title' || isSectionTitle(text);
  if (renderedAsSection) {
    return <div className="pt-2 text-sm font-semibold text-gray-900 dark:text-gray-100">{text}</div>;
  }

  if (pair && variant !== 'plain') {
    const headline = variant === 'headline' || isHeadlineKey(pair.label);
    const discount = variant === 'discount' || isDiscountKey(pair.label);
    const meta = variant === 'meta' || isMetaKey(pair.label);

    return (
      <div className={`flex items-baseline justify-between gap-3 ${headline ? 'pt-1 border-t border-gray-200/80 dark:border-gray-700/80 mt-1' : ''}`}>
        <span className={`text-sm ${meta ? 'text-gray-500 dark:text-gray-400' : 'text-gray-600 dark:text-gray-300'}`}>{pair.label}</span>
        <span
          className={`text-right ${
            headline
              ? 'text-base font-semibold text-red-600 dark:text-red-400'
              : discount
                ? 'text-sm font-medium text-emerald-600 dark:text-emerald-400'
                : 'text-sm font-medium text-gray-900 dark:text-gray-100'
          }`}
        >
          {pair.value}
        </span>
      </div>
    );
  }

  if (variant === 'caption' || variant === 'muted' || isSkuLine(text)) {
    return <div className="text-xs text-gray-500 dark:text-gray-400">{text}</div>;
  }

  if (variant === 'title') {
    return <div className="text-base font-semibold text-gray-900 dark:text-gray-100">{text}</div>;
  }

  return <div className="text-sm text-gray-900 dark:text-gray-100 leading-6">{text}</div>;
};

const Button = ({ element, children, emit, loading }: ComponentRenderProps<JsonRenderProps>) => {
  const props = element.props;
  const label = pickFirstString(props, ['label', 'text'], 'Submit');
  const variant = toStringValue(props.variant).toLowerCase();
  const primary = toBool(props.primary) || variant === 'primary';
  const danger = variant === 'danger';
  const link = variant === 'link';
  const isDisabled = toBool(props.disabled) || loading;

  return (
    <button
      type="button"
      onClick={() => {
        if (!isDisabled) emit('press');
      }}
      disabled={isDisabled}
      className={`mt-1 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
        isDisabled
          ? 'cursor-not-allowed opacity-60'
          : link
            ? 'text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 underline'
            : primary
              ? 'cursor-pointer bg-blue-600 text-white hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600'
              : danger
                ? 'cursor-pointer bg-red-500 text-white hover:bg-red-600 dark:bg-red-600 dark:hover:bg-red-700'
                : 'cursor-pointer border border-gray-200 text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700'
      }`}
    >
      {loading ? 'Loading...' : (children ?? label)}
    </button>
  );
};

const ButtonGroup = ({ children }: ComponentRenderProps<JsonRenderProps>) => {
  return <div className="mt-2 flex flex-wrap items-center gap-2">{children}</div>;
};

const Card = ({ element, children }: ComponentRenderProps<JsonRenderProps>) => {
  const props = element.props;
  const variant = toStringValue(props.variant).toLowerCase();
  const orderLike = variant === 'order' || variant === 'invoice';

  return (
    <div
      className={`rounded-2xl border p-4 shadow-sm ${
        orderLike
          ? 'border-blue-100 bg-gradient-to-b from-white to-blue-50/40 dark:border-blue-900/30 dark:from-gray-900 dark:to-blue-950/20'
          : 'border-gray-200 bg-white/90 dark:border-gray-700 dark:bg-gray-900/60'
      }`}
    >
      {children}
    </div>
  );
};

const Image = ({ element }: ComponentRenderProps<JsonRenderProps>) => {
  const props = element.props;
  const src = pickFirstString(props, ['url', 'src']);
  if (!src) return null;
  const alt = pickFirstString(props, ['alt'], 'image');
  return <img src={src} alt={alt} className="max-w-full rounded-md" />;
};

const Row = ({ element, children }: ComponentRenderProps<JsonRenderProps>) => {
  const props = element.props;
  const justify = toStringValue(props.justify).toLowerCase();
  const align = toStringValue(props.align).toLowerCase();
  const gap = toStringValue(props.gap).toLowerCase();
  const wrap = toBool(props.wrap);

  const justifyClass =
    justify === 'between' ? 'justify-between' : justify === 'center' ? 'justify-center' : justify === 'end' ? 'justify-end' : 'justify-start';
  const alignClass = align === 'center' ? 'items-center' : align === 'end' ? 'items-end' : 'items-start';
  const gapClass = gap === 'lg' ? 'gap-4' : gap === 'sm' ? 'gap-1.5' : 'gap-2.5';

  return <div className={`flex flex-row ${justifyClass} ${alignClass} ${gapClass} ${wrap ? 'flex-wrap' : ''}`}>{children}</div>;
};

const Column = ({ element, children }: ComponentRenderProps<JsonRenderProps>) => {
  const gap = toStringValue(element.props.gap).toLowerCase();
  const gapClass = gap === 'lg' ? 'gap-4' : gap === 'sm' ? 'gap-1.5' : 'gap-2.5';
  return <div className={`flex flex-col ${gapClass}`}>{children}</div>;
};

const Divider = () => <hr className="border-gray-200 dark:border-gray-700 my-1" />;

const Badge = ({ element, children }: ComponentRenderProps<JsonRenderProps>) => {
  const props = element.props;
  const tone = toStringValue(props.tone).toLowerCase();
  const label = children ?? pickFirstString(props, ['label', 'text', 'value'], '');
  if (!label) return null;

  const toneClass =
    tone === 'success'
      ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300'
      : tone === 'warning'
        ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300'
        : tone === 'danger'
          ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
          : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300';

  return <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${toneClass}`}>{label}</span>;
};

const Section = ({ element, children }: ComponentRenderProps<JsonRenderProps>) => {
  const title = pickFirstString(element.props, ['title', 'label', 'text']);
  return (
    <section className="rounded-xl border border-gray-100 bg-gray-50/70 p-3 dark:border-gray-700/70 dark:bg-gray-800/50">
      {title ? <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">{title}</div> : null}
      <div className={title ? 'mt-2 space-y-2' : 'space-y-2'}>{children}</div>
    </section>
  );
};

const KV = ({ element }: ComponentRenderProps<JsonRenderProps>) => {
  const props = element.props;
  const label = pickFirstString(props, ['label', 'key', 'name']);
  const value = pickFirstString(props, ['value', 'text', 'amount']);
  const highlight = toBool(props.highlight) || isHeadlineKey(label);
  if (!label && !value) return null;
  return (
    <div className={`flex items-baseline justify-between gap-3 ${highlight ? 'pt-1 border-t border-gray-200/80 dark:border-gray-700/80' : ''}`}>
      <span className={`text-sm ${highlight ? 'font-medium text-gray-900 dark:text-gray-100' : 'text-gray-600 dark:text-gray-300'}`}>{label}</span>
      <span className={`text-right ${highlight ? 'text-base font-semibold text-red-600 dark:text-red-400' : 'text-sm font-medium text-gray-900 dark:text-gray-100'}`}>
        {value}
      </span>
    </div>
  );
};

const PriceRow = ({ element }: ComponentRenderProps<JsonRenderProps>) => {
  const props = element.props;
  const label = pickFirstString(props, ['label', 'title', 'name']);
  const rawValue = props.amount ?? props.value ?? props.text;
  const valueText = toStringValue(rawValue);
  const numeric = toNumberValue(rawValue);
  const currency = pickFirstString(props, ['currency'], '¥');
  const emphasis = toBool(props.emphasis) || isHeadlineKey(label);
  const discount = toBool(props.discount) || isDiscountKey(label) || (numeric !== undefined && numeric < 0);

  const shownValue =
    valueText ||
    (numeric !== undefined ? `${currency}${Math.abs(numeric).toFixed(2)}` : '');
  if (!label && !shownValue) return null;

  return (
    <div className={`flex items-baseline justify-between gap-3 ${emphasis ? 'pt-1 border-t border-gray-200/80 dark:border-gray-700/80 mt-1' : ''}`}>
      <span className={`text-sm ${emphasis ? 'font-medium text-gray-900 dark:text-gray-100' : 'text-gray-600 dark:text-gray-300'}`}>{label}</span>
      <span
        className={`text-right ${
          emphasis
            ? 'text-lg font-semibold text-red-600 dark:text-red-400'
            : discount
              ? 'text-sm font-medium text-emerald-600 dark:text-emerald-400'
              : 'text-sm font-medium text-gray-900 dark:text-gray-100'
        }`}
      >
        {discount && numeric !== undefined && numeric > 0 ? `-${currency}${numeric.toFixed(2)}` : shownValue}
      </span>
    </div>
  );
};

const OrderItem = ({ element }: ComponentRenderProps<JsonRenderProps>) => {
  const props = element.props;
  const name = pickFirstString(props, ['name', 'title', 'label']);
  const sku = pickFirstString(props, ['sku']);
  const quantity = pickFirstString(props, ['quantity', 'qty'], '1');
  const price = pickFirstString(props, ['subtotal', 'price', 'amount']);

  if (!name && !price) return null;

  return (
    <div className="flex items-start justify-between gap-3 rounded-lg border border-gray-100 bg-white/70 p-2.5 dark:border-gray-700 dark:bg-gray-900/50">
      <div className="min-w-0">
        <div className="truncate text-sm font-medium text-gray-900 dark:text-gray-100">{name}</div>
        {sku ? <div className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">SKU: {sku}</div> : null}
      </div>
      <div className="shrink-0 text-right">
        <div className="text-xs text-gray-500 dark:text-gray-400">x{quantity}</div>
        <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">{price}</div>
      </div>
    </div>
  );
};

const Input = ({ element, bindings }: ComponentRenderProps<JsonRenderProps>) => {
  const props = element.props;
  const [value, setValue] = useBoundProp<string | undefined>(toStringValue(props.value), bindings?.value);
  const label = toStringValue(props.label);
  const placeholder = toStringValue(props.placeholder);

  return (
    <label className="flex flex-col gap-1 text-sm text-gray-700 dark:text-gray-300">
      {label ? <span>{label}</span> : null}
      <input
        className="rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2"
        value={value ?? ''}
        placeholder={placeholder}
        onChange={(e) => setValue(e.target.value)}
      />
    </label>
  );
};

const Checkbox = ({ element, bindings }: ComponentRenderProps<Record<string, unknown>>) => {
  const props = element.props;
  // Accept value, checked, or selected as the bound prop
  const rawValue = props.value ?? props.checked ?? props.selected;
  const bindingPath = bindings?.value ?? bindings?.checked ?? bindings?.selected;
  const [value, setValue] = useBoundProp<boolean | undefined>(toBool(rawValue), bindingPath);
  const label = toStringValue(props.label) || toStringValue(props.text);

  return (
    <label className="inline-flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
      <input
        type="checkbox"
        checked={Boolean(value)}
        onChange={(e) => setValue(e.target.checked)}
      />
      <span>{label}</span>
    </label>
  );
};

const DateTimeInput = ({ element, bindings }: ComponentRenderProps<Record<string, unknown>>) => {
  const props = element.props;
  // Accept value, date, or selectedDate as the bound prop
  const rawValue = props.value ?? props.date ?? props.selectedDate;
  const bindingPath = bindings?.value ?? bindings?.date ?? bindings?.selectedDate;
  const [value, setValue] = useBoundProp<string | undefined>(toStringValue(rawValue), bindingPath);
  const label = toStringValue(props.label);

  // Respect mode prop (date/time/datetime) as well as enableDate/enableTime
  const mode = toStringValue(props.mode).toLowerCase() || toStringValue(props.type).toLowerCase();
  const enableDate = mode ? mode !== 'time' : props.enableDate !== false;
  const enableTime = mode ? (mode === 'time' || mode === 'datetime' || mode === 'datetime-local') : props.enableTime !== false;
  const type = enableDate && enableTime ? 'datetime-local' : enableDate ? 'date' : 'time';

  return (
    <label className="flex flex-col gap-1 text-sm text-gray-700 dark:text-gray-300">
      {label ? <span>{label}</span> : null}
      <input
        type={type}
        className="rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2"
        value={value ?? ''}
        onChange={(e) => setValue(e.target.value)}
      />
    </label>
  );
};

const MultipleChoice = ({ element, bindings }: ComponentRenderProps<Record<string, unknown>>) => {
  const props = element.props;
  const rawOptions = Array.isArray(props.options) ? props.options : [];
  const options = rawOptions
    .map((item: unknown) => {
      // Handle string shorthand: "身份证" → { label: "身份证", value: "身份证" }
      if (typeof item === 'string') {
        return item ? { label: item, value: item } : null;
      }
      if (typeof item !== 'object' || item === null) return null;
      const obj = item as Record<string, unknown>;
      return {
        label: toStringValue(obj.label),
        value: toStringValue(obj.value),
      };
    })
    .filter((item: { label: string; value: string } | null): item is { label: string; value: string } => item !== null && item.value.length > 0);

  // Accept value, selectedValue, or selectedValues as the bound prop
  const rawValue = props.value ?? props.selectedValue ?? props.selectedValues;
  const initialValue = Array.isArray(rawValue) ? toStringValue(rawValue[0]) : toStringValue(rawValue);
  const bindingPath = bindings?.value ?? bindings?.selectedValue ?? bindings?.selectedValues;
  const [value, setValue] = useBoundProp<string | undefined>(initialValue, bindingPath);
  const label = toStringValue(props.label);

  return (
    <label className="flex flex-col gap-1 text-sm text-gray-700 dark:text-gray-300">
      {label ? <span>{label}</span> : null}
      <select
        className="rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2"
        value={value ?? ''}
        onChange={(e) => setValue(e.target.value)}
      >
        <option value="">Select</option>
        {options.map((opt: { label: string; value: string }) => (
          <option key={opt.value} value={opt.value}>
            {opt.label || opt.value}
          </option>
        ))}
      </select>
    </label>
  );
};

const List = ({ children }: ComponentRenderProps<Record<string, unknown>>) => {
  return <div className="flex flex-col gap-2">{children}</div>;
};

const Unknown = ({ element, children }: ComponentRenderProps<JsonRenderProps>) => {
  return (
    <div className="rounded-md border border-amber-300 bg-amber-50/80 dark:bg-amber-900/20 px-3 py-2">
      <div className="text-xs text-amber-700 dark:text-amber-300">Unsupported component: {element.type}</div>
      {children}
    </div>
  );
};

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
};

export const jsonRenderFallback = Unknown;
