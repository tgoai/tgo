import React from 'react';
import EditableField from '../ui/EditableField';
import CustomAttributeManager from '../ui/CustomAttributeManager';
import CollapsibleSection from '../ui/CollapsibleSection';
import type { VisitorBasicInfo } from '@/data/mockVisitor';
import { useTranslation } from 'react-i18next';

interface BasicInfoSectionProps {
  basicInfo: VisitorBasicInfo;
  onUpdateBasicInfo: (
    field: 'name' | 'nickname' | 'email' | 'phone' | 'note',
    value: string
  ) => void;
  onAddCustomAttribute: (key: string, value: string) => void;
  onUpdateCustomAttribute: (id: string, key: string, value: string) => void;
  onDeleteCustomAttribute: (id: string) => void;
  className?: string;
  draggable?: boolean;
  expanded?: boolean;
  onToggle?: (expanded: boolean) => void;
  onDragStart?: (e: React.DragEvent) => void;
  onDragEnd?: (e: React.DragEvent) => void;
  onDragOver?: (e: React.DragEvent) => void;
  onDrop?: (e: React.DragEvent) => void;
}



/**
 * 基本信息模块组件
 */
const BasicInfoSection: React.FC<BasicInfoSectionProps> = ({
  basicInfo,
  onUpdateBasicInfo,
  onAddCustomAttribute,
  onUpdateCustomAttribute,
  onDeleteCustomAttribute,
  className = '',
  draggable,
  expanded,
  onToggle,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDrop,
}) => {
  const { t } = useTranslation();
  const validateEmail = (email: string): string | null => {
    if (!email.trim()) return null;
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email) ? null : t('visitor.validation.invalidEmail', '\u8bf7\u8f93\u5165\u6709\u6548\u7684\u90ae\u7bb1\u5730\u5740');
  };
  const validatePhone = (phone: string): string | null => {
    if (!phone.trim()) return null;
    const phoneRegex = /^[\d\s\-\+\(\)]{7,}$/;
    return phoneRegex.test(phone) ? null : t('visitor.validation.invalidPhone', '\u8bf7\u8f93\u5165\u6709\u6548\u7684\u7535\u8bdd\u53f7\u7801');
  };
  return (
    <CollapsibleSection
      title={t('visitor.sections.basicInfo', '基本信息')}
      className={className}
      defaultExpanded={true}
      expanded={expanded}
      onToggle={onToggle}
      draggable={draggable}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      <div className="space-y-1.5 text-[13px] leading-5">
        <EditableField
          label={t('visitor.fields.name', '姓名')}
          value={basicInfo.name}
          onSave={(value) => onUpdateBasicInfo('name', value)}
          placeholder="-"
        />
        <EditableField
          label={t('visitor.fields.nickname', '昵称')}
          value={basicInfo.nickname || ''}
          onSave={(value) => onUpdateBasicInfo('nickname', value)}
          placeholder="-"
        />
        <EditableField
          label={t('visitor.fields.email', '邮箱')}
          value={basicInfo.email}
          onSave={(value) => onUpdateBasicInfo('email', value)}
          placeholder="-"
          type="email"
          validate={validateEmail}
        />
        <EditableField
          label={t('visitor.fields.phone', '电话')}
          value={basicInfo.phone}
          onSave={(value) => onUpdateBasicInfo('phone', value)}
          placeholder="-"
          type="tel"
          validate={validatePhone}
        />
        <EditableField
          label={t('visitor.fields.note', '备注')}
          value={basicInfo.note || ''}
          onSave={(value) => onUpdateBasicInfo('note', value)}
          placeholder="-"
        />

        {/* 自定义属性 */}
        <CustomAttributeManager
          attributes={basicInfo.customAttributes || []}
          onAdd={onAddCustomAttribute}
          onUpdate={onUpdateCustomAttribute}
          onDelete={onDeleteCustomAttribute}
          className="pt-2 space-y-1.5"
        />
      </div>
    </CollapsibleSection>
  );
};

export default BasicInfoSection;
