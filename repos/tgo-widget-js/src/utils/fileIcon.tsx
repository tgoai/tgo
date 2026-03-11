import React from 'react'
import {
  FaFile,
  FaFilePdf,
  FaFileWord,
  FaFileExcel,
  FaFilePowerpoint,
  FaFileAlt,
  FaFileArchive,
  FaFileCode,
  FaFileVideo,
  FaFileAudio,
  FaFileImage,
} from 'react-icons/fa'

/**
 * Get the appropriate file icon component based on file extension
 * @param fileName - The name of the file (with extension)
 * @param className - Optional CSS classes to apply to the icon
 * @param size - Icon size in pixels (default: 20)
 * @returns React icon component
 */
export const getFileIcon = (
  fileName: string,
  className?: string,
  size: number = 20
): React.ReactElement => {
  const extension = (fileName || '').toLowerCase().split('.').pop() || ''

  const iconProps = {
    size,
    className: className || 'flex-shrink-0',
  }

  // PDF files
  if (extension === 'pdf') {
    return <FaFilePdf {...iconProps} style={{ color: '#E53E3E' }} />
  }

  // Word documents
  if (['doc', 'docx'].includes(extension)) {
    return <FaFileWord {...iconProps} style={{ color: '#2B6CB0' }} />
  }

  // Excel files
  if (['xls', 'xlsx', 'csv'].includes(extension)) {
    return <FaFileExcel {...iconProps} style={{ color: '#38A169' }} />
  }

  // PowerPoint files
  if (['ppt', 'pptx'].includes(extension)) {
    return <FaFilePowerpoint {...iconProps} style={{ color: '#DD6B20' }} />
  }

  // Text files
  if (['txt', 'md', 'rtf'].includes(extension)) {
    return <FaFileAlt {...iconProps} style={{ color: '#718096' }} />
  }

  // Image files
  if (['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp'].includes(extension)) {
    return <FaFileImage {...iconProps} style={{ color: '#805AD5' }} />
  }

  // Archive files
  if (['zip', 'rar', '7z', 'tar', 'gz'].includes(extension)) {
    return <FaFileArchive {...iconProps} style={{ color: '#805AD5' }} />
  }

  // Code files
  if (
    [
      'js', 'ts', 'tsx', 'jsx', 'py', 'java', 'cpp', 'c',
      'html', 'css', 'json', 'xml', 'php', 'rb', 'go', 'rs',
      'swift', 'kt', 'sh', 'yml', 'yaml'
    ].includes(extension)
  ) {
    return <FaFileCode {...iconProps} style={{ color: '#3182CE' }} />
  }

  // Video files
  if (['mp4', 'avi', 'mov', 'mkv', 'flv', 'wmv', 'webm'].includes(extension)) {
    return <FaFileVideo {...iconProps} style={{ color: '#D53F8C' }} />
  }

  // Audio files
  if (['mp3', 'wav', 'flac', 'aac', 'ogg', 'm4a', 'wma'].includes(extension)) {
    return <FaFileAudio {...iconProps} style={{ color: '#38B2AC' }} />
  }

  // Default/Unknown
  return <FaFile {...iconProps} style={{ color: '#718096' }} />
}

