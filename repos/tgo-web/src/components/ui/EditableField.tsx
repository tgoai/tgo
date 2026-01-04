import React, { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';

import { Check, X, Edit3 } from 'lucide-react';

interface EditableFieldProps {
  label: string;
  value: string;
  onSave: (newValue: string) => Promise<void> | void;
  onCancel?: () => void;
  placeholder?: string;
  type?: 'text' | 'email' | 'tel';
  validate?: (value: string) => string | null;
  className?: string;
  disabled?: boolean;
}

/**
 * Inline editable field component
 */
const EditableField: React.FC<EditableFieldProps> = ({
  label,
  value,
  onSave,
  onCancel,
  placeholder,
  type = 'text',
  validate,
  className = '',
  disabled = false
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(value);
  const { t } = useTranslation();

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  useEffect(() => {
    setEditValue(value);
  }, [value]);

  const handleEdit = () => {
    if (disabled) return;
    setIsEditing(true);
    setError(null);
  };

  const handleSave = async () => {
    if (validate) {
      const validationError = validate(editValue);
      if (validationError) {
        setError(validationError);
        return;
      }
    }

    setIsLoading(true);
    setError(null);

    try {
      await onSave(editValue);
      setIsEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.saveFailed', '保存失败'));
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = () => {
    setEditValue(value);
    setError(null);
    setIsEditing(false);
    onCancel?.();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSave();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      handleCancel();
    }
  };

  const handleBlur = () => {
    // Auto-save on blur if value changed
    if (editValue !== value && !error) {
      handleSave();
    } else {
      handleCancel();
    }
  };

  if (isEditing) {
    return (
      <div className={`flex justify-between items-start py-0.5 ${className}`}>
        <span className="text-gray-400 dark:text-gray-500 flex-shrink-0 text-[12px] leading-6 pt-0.5">{label}</span>
        <div className="flex-1 ml-3 min-w-0">
          <div className="flex items-center space-x-1">
            <input
              ref={inputRef}
              type={type}
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onKeyDown={handleKeyDown}
              onBlur={handleBlur}
              placeholder={placeholder}
              disabled={isLoading}
              className={`flex-1 min-w-0 max-w-[150px] px-2 py-1 text-[12px] leading-5 text-gray-800 dark:text-gray-100 bg-white dark:bg-gray-800 border rounded transition-all focus:outline-none focus:ring-1 focus:ring-blue-500/50 focus:border-blue-500/50 ${
                error ? 'border-red-400 dark:border-red-500' : 'border-gray-200 dark:border-gray-700'
              } ${isLoading ? 'opacity-50' : ''}`}
            />
            <button
              onClick={handleSave}
              disabled={isLoading}
              className="p-1 text-green-600 dark:text-green-500 hover:bg-green-50 dark:hover:bg-green-900/20 rounded transition-colors disabled:opacity-50 flex-shrink-0"
            >
              <Check className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleCancel}
              disabled={isLoading}
              className="p-1 text-gray-400 dark:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors disabled:opacity-50 flex-shrink-0"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          {error && (
            <div className="mt-1 text-[10px] text-red-500 dark:text-red-400 font-medium px-1">{error}</div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={`flex justify-between items-start group py-0.5 ${className}`}>
      <span className="text-gray-400 dark:text-gray-500 text-[12px] leading-6 flex-shrink-0">{label}</span>
      <div className="flex items-center space-x-1.5 flex-1 min-w-0 ml-3 justify-end">
        <span
          className={`text-gray-700 dark:text-gray-200 font-medium text-[12px] leading-6 truncate max-w-full ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer hover:text-blue-600 dark:hover:text-blue-400 transition-colors'} text-right`}
          onClick={handleEdit}
          title={value || placeholder || '-'}
        >
          {value || placeholder || '-'}
        </span>
        {!disabled && (
          <Edit3 className="w-2.5 h-2.5 text-gray-300 dark:text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 cursor-pointer" onClick={handleEdit} />
        )}
      </div>
    </div>
  );
};

export default EditableField;
