import React from 'react';
import { useTranslation } from 'react-i18next';

interface TableColumn {
  key: string;
  label: string;
  width?: string | number;
  align?: 'left' | 'center' | 'right';
}

interface TableTemplateProps {
  title?: string;
  columns: TableColumn[];
  rows: Record<string, any>[];
}

const TableTemplate: React.FC<TableTemplateProps> = ({ title, columns, rows }) => {
  const { t } = useTranslation();

  const renderCell = (row: Record<string, any>, col: TableColumn) => {
    const value = row[col.key];
    
    // Support basic color/badge if value is an object
    if (value && typeof value === 'object' && value.text) {
      return (
        <span
          className="px-2 py-0.5 rounded-full text-[10px] font-medium"
          style={{
            backgroundColor: value.color ? `${value.color}20` : '#f3f4f6',
            color: value.color || '#374151',
          }}
        >
          {value.text}
        </span>
      );
    }

    return <span>{value}</span>;
  };

  return (
    <div className="space-y-3">
      {title && (
        <h5 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
          {title}
        </h5>
      )}
      <div className="overflow-x-auto rounded-lg border border-gray-100 dark:border-gray-700 bg-white dark:bg-gray-800">
        <table className="min-w-full divide-y divide-gray-100 dark:divide-gray-700 text-xs">
          <thead>
            <tr className="bg-gray-50 dark:bg-gray-900/50">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`px-3 py-2 text-left font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider`}
                  style={{ width: col.width }}
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
            {rows.map((row, idx) => (
              <tr key={idx} className="hover:bg-gray-50/50 dark:hover:bg-gray-900/20 transition-colors">
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={`px-3 py-2 whitespace-nowrap text-gray-700 dark:text-gray-300`}
                  >
                    {renderCell(row, col)}
                  </td>
                ))}
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="px-3 py-8 text-center text-gray-400 italic">
                  {t('common.noData', '暂无数据')}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default TableTemplate;

