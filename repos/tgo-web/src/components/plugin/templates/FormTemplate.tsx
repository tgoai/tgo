import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2 } from 'lucide-react';

interface FormField {
  name: string;
  label: string;
  type: 'text' | 'number' | 'select' | 'textarea' | 'checkbox';
  required?: boolean;
  placeholder?: string;
  options?: { label: string; value: any }[];
  default?: any;
}

interface FormTemplateProps {
  title?: string;
  fields: FormField[];
  submit_text?: string;
  cancel_text?: string;
  onSubmit: (data: Record<string, any>) => Promise<void>;
  onCancel?: () => void;
}

const FormTemplate: React.FC<FormTemplateProps> = ({
  title,
  fields,
  submit_text,
  cancel_text,
  onSubmit,
  onCancel,
}) => {
  const { t } = useTranslation();
  const [formData, setFormData] = useState<Record<string, any>>(() => {
    const initial: Record<string, any> = {};
    fields.forEach((f) => {
      if (f.default !== undefined) initial[f.name] = f.default;
    });
    return initial;
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await onSubmit(formData);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (name: string, value: any) => {
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {title && (
        <h5 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
          {title}
        </h5>
      )}
      <div className="space-y-3">
        {fields.map((field) => (
          <div key={field.name} className="space-y-1">
            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
              {field.label}
              {field.required && <span className="text-red-500 ml-0.5">*</span>}
            </label>
            
            {field.type === 'textarea' ? (
              <textarea
                className="w-full text-sm px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-md focus:ring-1 focus:ring-blue-500 bg-white dark:bg-gray-900 dark:text-gray-100"
                placeholder={field.placeholder}
                value={formData[field.name] || ''}
                onChange={(e) => handleChange(field.name, e.target.value)}
                required={field.required}
                rows={3}
              />
            ) : field.type === 'select' ? (
              <select
                className="w-full text-sm px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-md focus:ring-1 focus:ring-blue-500 bg-white dark:bg-gray-900 dark:text-gray-100"
                value={formData[field.name] || ''}
                onChange={(e) => handleChange(field.name, e.target.value)}
                required={field.required}
              >
                <option value="">{field.placeholder || t('common.select', '请选择')}</option>
                {field.options?.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type={field.type}
                className="w-full text-sm px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-md focus:ring-1 focus:ring-blue-500 bg-white dark:bg-gray-900 dark:text-gray-100"
                placeholder={field.placeholder}
                value={formData[field.name] || ''}
                onChange={(e) => handleChange(field.name, e.target.value)}
                required={field.required}
              />
            )}
          </div>
        ))}
      </div>

      <div className="flex items-center justify-end space-x-2 pt-2 border-t border-gray-100 dark:border-gray-700">
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md transition-colors"
          >
            {cancel_text || t('common.cancel', '取消')}
          </button>
        )}
        <button
          type="submit"
          disabled={isSubmitting}
          className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors flex items-center"
        >
          {isSubmitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
          {submit_text || t('common.submit', '提交')}
        </button>
      </div>
    </form>
  );
};

export default FormTemplate;

