"""
Document loading and parsing module.

This module provides document loading capabilities using a unified parser-based approach.
It supports multiple file formats with specialized parsers for optimal content extraction.

Key Components:
- Unified document loader factory using GenericLoader.from_filesystem
- Specialized parser selection based on content type
- Support for PDF, Text, Markdown, Word, HTML, and other file formats
- Fallback mechanisms for unsupported content types
- Comprehensive error handling for loading failures

Supported File Types:
- PDF: PDFMinerParser for reliable PDF text extraction
- Text/Markdown: TextParser for plain text and markdown files
- Word Documents: MsWordParser for .doc and .docx files
- HTML: BS4HTMLParser for HTML content extraction
- Other: MimeTypeBasedParser with TextParser fallback
"""

import os
from typing import Any, List

from langchain_community.document_loaders.parsers import BS4HTMLParser, PDFMinerParser
from langchain_community.document_loaders.parsers.generic import MimeTypeBasedParser
from langchain_community.document_loaders.parsers.msword import MsWordParser
from langchain_community.document_loaders.parsers.txt import TextParser
from langchain_community.document_loaders.generic import GenericLoader

from ..logging_config import get_logger
from .document_processing_errors import DocumentProcessingError, ProcessingStep
from .document_processing_types import (
    DocumentLoader as DocumentLoaderProtocol,
    ParserInfo,
    SUPPORTED_CONTENT_TYPES,
    PARSER_MAPPING
)

logger = get_logger(__name__)


def get_document_loader(file_path: str, content_type: str, file_id: str) -> GenericLoader:
    """
    Get appropriate document loader based on content type using unified parser approach.

    This function creates a GenericLoader instance with the appropriate parser for the
    given content type. All file types use the same GenericLoader.from_filesystem
    pattern for consistency and reliability.

    Args:
        file_path: Path to the file to be loaded
        content_type: MIME type of the file
        file_id: File ID for error reporting and logging

    Returns:
        GenericLoader instance configured with appropriate parser

    Raises:
        DocumentProcessingError: For unsupported content types or loader creation failures
    """
    try:
        # Get the directory and filename for GenericLoader
        file_dir = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        
        # Select appropriate parser based on content type
        parser = _get_parser_for_content_type(content_type, file_id)
        
        # Create GenericLoader with the selected parser
        loader = GenericLoader.from_filesystem(
            path=file_dir,
            glob=file_name,
            parser=parser,
            show_progress=False
        )
        
        logger.debug(f"Created document loader for {content_type} file: {file_name}")
        return loader
        
    except Exception as e:
        if isinstance(e, DocumentProcessingError):
            raise
        raise DocumentProcessingError(
            f"Error creating document loader for {content_type}: {str(e)}",
            file_id,
            ProcessingStep.EXTRACTING_CONTENT,
            e
        ) from e


def _get_parser_for_content_type(content_type: str, file_id: str) -> Any:
    """
    Get appropriate parser based on content type.
    
    This function selects the most suitable parser for each content type,
    providing specialized parsing capabilities for optimal content extraction.
    
    Args:
        content_type: MIME type of the file
        file_id: File ID for error reporting
        
    Returns:
        Parser instance for the given content type
        
    Raises:
        DocumentProcessingError: For parser creation failures
    """
    try:
        if content_type == "application/pdf":
            # Use PDFMinerParser for PDF files - provides reliable text extraction
            logger.debug(f"Selected PDFMinerParser for PDF file {file_id}")
            return PDFMinerParser()
            
        elif content_type in ["text/plain", "text/markdown"]:
            # Use TextParser for text and markdown files - handles UTF-8 encoding
            logger.debug(f"Selected TextParser for text/markdown file {file_id}")
            return TextParser()
            
        elif content_type in [
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ]:
            # Use MsWordParser for Word documents - handles both .doc and .docx
            logger.debug(f"Selected MsWordParser for Word document {file_id}")
            return MsWordParser()
            
        elif content_type in [
            "text/html",
            "application/xhtml+xml"
        ]:
            # Use BS4HTMLParser for HTML files - extracts text from HTML structure
            logger.debug(f"Selected BS4HTMLParser for HTML file {file_id}")
            return BS4HTMLParser()
            
        else:
            # Use MimeTypeBasedParser as fallback for other file types
            logger.debug(f"Using MimeTypeBasedParser fallback for content type {content_type} (file {file_id})")
            try:
                return MimeTypeBasedParser()
            except Exception as fallback_error:
                # If MimeTypeBasedParser fails, fall back to TextParser
                logger.warning(
                    f"MimeTypeBasedParser failed for {content_type} (file {file_id}), "
                    f"using TextParser as final fallback: {fallback_error}"
                )
                return TextParser()
                
    except Exception as e:
        raise DocumentProcessingError(
            f"Error creating parser for content type {content_type}: {str(e)}",
            file_id,
            ProcessingStep.EXTRACTING_CONTENT,
            e
        ) from e


def get_supported_content_types() -> List[str]:
    """
    Get list of supported content types.

    Returns:
        List of supported MIME types
    """
    return SUPPORTED_CONTENT_TYPES


def is_content_type_supported(content_type: str) -> bool:
    """
    Check if a content type is explicitly supported.
    
    Args:
        content_type: MIME type to check
        
    Returns:
        True if content type is explicitly supported, False otherwise
        
    Note:
        Unsupported content types will still be processed using fallback parsers
    """
    return content_type in get_supported_content_types()


def get_parser_info(content_type: str) -> ParserInfo:
    """
    Get information about the parser that would be used for a content type.

    Args:
        content_type: MIME type to get parser info for

    Returns:
        ParserInfo object with parser information including name and description
    """
    if content_type == "application/pdf":
        return ParserInfo(
            parser="PDFMinerParser",
            description="Specialized PDF text extraction with reliable formatting"
        )
    elif content_type in ["text/plain", "text/markdown"]:
        return ParserInfo(
            parser="TextParser",
            description="Plain text parser with UTF-8 encoding support"
        )
    elif content_type in [
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]:
        return ParserInfo(
            parser="MsWordParser",
            description="Microsoft Word document parser for .doc and .docx files"
        )
    elif content_type in ["text/html", "application/xhtml+xml"]:
        return ParserInfo(
            parser="BS4HTMLParser",
            description="HTML parser using BeautifulSoup for text extraction"
        )
    else:
        return ParserInfo(
            parser="MimeTypeBasedParser (fallback to TextParser)",
            description="Generic parser with text fallback for unsupported types"
        )
