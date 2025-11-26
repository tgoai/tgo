"""
File management endpoints.
"""

import os
import mimetypes
from pathlib import Path
from typing import List, Optional, Union
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse as FastAPIFileResponse
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_db_session_dependency
from ..logging_config import get_logger
from ..models import Collection, File as FileModel
from ..schemas.common import PaginationMetadata
from ..schemas.files import (
    FileListResponse,
    FileResponse,
    FileUploadResponse,
    BatchFileUploadResponse,
    FileUploadError,
    BatchUploadSummary
)
from ..schemas.common import ErrorResponse

router = APIRouter()
logger = get_logger(__name__)


@router.get(
    "",
    response_model=FileListResponse,
    responses={
        422: {"model": ErrorResponse, "description": "Validation error - invalid query parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def list_files(
    collection_id: Optional[UUID] = Query(None, description="Filter by collection ID"),
    status: Optional[str] = Query(None, description="Filter by processing status"),
    content_type: Optional[str] = Query(None, description="Filter by MIME type"),
    uploaded_by: Optional[str] = Query(None, description="Filter by uploader"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated list)"),
    limit: int = Query(20, ge=1, le=100, description="Number of files to return"),
    offset: int = Query(0, ge=0, description="Number of files to skip"),
    project_id: UUID = Query(..., description="Project ID", example="11111111-1111-1111-1111-111111111111"),
    db: AsyncSession = Depends(get_db_session_dependency),
):
    """
    Retrieve all files for the specified project (via project_id) with filtering and pagination.

    Files represent uploaded documents that are processed for RAG operations.
    All results are scoped to the specified project.
    """
    # Build query with project filtering for multi-tenant isolation
    query = select(FileModel).where(
        and_(
            FileModel.deleted_at.is_(None),
            FileModel.project_id == project_id
        )
    )
    
    # Apply filters
    if collection_id:
        query = query.where(FileModel.collection_id == collection_id)
    if status:
        query = query.where(FileModel.status == status)
    if content_type:
        query = query.where(FileModel.content_type == content_type)
    if uploaded_by:
        query = query.where(FileModel.uploaded_by == uploaded_by)
    if tags:
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        if tag_list:
            # Use PostgreSQL array overlap operator to check if any of the provided tags exist
            from sqlalchemy import text
            query = query.where(text("tags && :tag_list")).params(tag_list=tag_list)
    
    # Get total count for pagination
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination and ordering
    query = query.offset(offset).limit(limit).order_by(FileModel.created_at.desc())
    
    # Execute query
    result = await db.execute(query)
    files = result.scalars().all()
    
    # Convert to response models
    file_responses = [FileResponse.model_validate(file) for file in files]
    
    # Create pagination metadata
    pagination = PaginationMetadata(
        total=total,
        limit=limit,
        offset=offset,
        has_next=offset + limit < total,
        has_previous=offset > 0,
    )
    
    return FileListResponse(
        data=file_responses,
        pagination=pagination
    )


@router.post(
    "",
    response_model=FileUploadResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request - invalid file or missing filename"},
        404: {"model": ErrorResponse, "description": "Collection not found or not accessible"},
        413: {"model": ErrorResponse, "description": "File too large - exceeds maximum allowed size"},
        415: {"model": ErrorResponse, "description": "Unsupported media type - file type not allowed"},
        422: {"model": ErrorResponse, "description": "Validation error - request data validation failed"},
        500: {"model": ErrorResponse, "description": "Internal server error - file processing failed"}
    }
)
async def upload_file(
    file: UploadFile = File(..., description="File to upload for RAG processing"),
    collection_id: Optional[UUID] = Form(None, description="Collection ID to associate with the file"),
    description: Optional[str] = Form(None, description="Optional file description"),
    language: Optional[str] = Form(None, description="Document language (ISO 639-1 code)"),
    tags: Optional[str] = Form(None, description="Comma-separated list of tags"),
    project_id: UUID = Form(..., description="Project ID", example="11111111-1111-1111-1111-111111111111"),
    db: AsyncSession = Depends(get_db_session_dependency),
):
    """
    Upload a new file for RAG processing within the specified project.

    The file will be stored and queued for document extraction and embedding generation.
    Supported formats: PDF, Word documents, text files, and markdown files.
    All files are scoped to the specified project.
    """
    settings = get_settings()
    
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    # Check file size
    if file.size and file.size > settings.max_file_size:
        raise HTTPException(
            status_code=413,
            detail=f"File size {file.size} exceeds maximum allowed size {settings.max_file_size}"
        )
    
    # Check content type
    if file.content_type not in settings.allowed_file_types:
        raise HTTPException(
            status_code=415,
            detail=f"File type {file.content_type} not supported. Allowed types: {settings.allowed_file_types}"
        )
    
    # Verify collection exists and belongs to the project if provided
    if collection_id:
        collection_query = select(Collection).where(
            and_(
                Collection.id == collection_id,
                Collection.project_id == project_id,
                Collection.deleted_at.is_(None)
            )
        )
        collection_result = await db.execute(collection_query)
        collection = collection_result.scalar_one_or_none()

        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found or not accessible")
    
    # Generate unique filename and save file
    file_id = uuid4()
    file_extension = os.path.splitext(file.filename)[1]
    storage_filename = f"{file_id}{file_extension}"
    storage_path = os.path.join(settings.upload_dir, storage_filename)
    
    # Save file to disk
    try:
        with open(storage_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        file_size = len(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # Parse tags if provided
    tags_list = None
    if tags:
        tags_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
    
    # Create file record with specified project_id
    file_record = FileModel(
        id=file_id,
        project_id=project_id,
        collection_id=collection_id,
        original_filename=file.filename,
        file_size=file_size,
        content_type=file.content_type,
        storage_provider="local",
        storage_path=storage_path,
        storage_metadata={"original_path": storage_path},
        status="pending",
        language=language,
        description=description,
        tags=tags_list,
        # TODO: Get uploaded_by from authentication
        uploaded_by=None,
    )
    
    db.add(file_record)
    await db.commit()
    await db.refresh(file_record)
    
    # Queue file for processing with Celery
    from ..tasks.document_processing import process_file_task

    try:
        task = process_file_task.delay(str(file_record.id), str(collection_id))
        logger.info(f"Queued file {file_record.id} for processing with task {task.id}")
    except Exception as e:
        logger.warning(f"Failed to queue file for processing: {str(e)}")
        # Continue anyway - file is uploaded, processing can be retried

    return FileUploadResponse(
        id=file_record.id,
        original_filename=file_record.original_filename,
        file_size=file_record.file_size,
        content_type=file_record.content_type,
        status=file_record.status,
        message="File uploaded successfully and queued for processing"
    )


@router.get(
    "/{file_id}",
    response_model=FileResponse,
    responses={
        404: {"model": ErrorResponse, "description": "File not found or not accessible"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def get_file(
    file_id: UUID,
    project_id: UUID = Query(..., description="Project ID", example="11111111-1111-1111-1111-111111111111"),
    db: AsyncSession = Depends(get_db_session_dependency),
):
    """
    Retrieve detailed information about a specific file including processing status
    and metadata about generated documents. File must belong to the specified project.
    """
    query = select(FileModel).where(
        and_(
            FileModel.id == file_id,
            FileModel.project_id == project_id,
            FileModel.deleted_at.is_(None)
        )
    )

    result = await db.execute(query)
    file_record = result.scalar_one_or_none()

    if not file_record:
        raise HTTPException(status_code=404, detail="File not found or not accessible")

    return FileResponse.model_validate(file_record)


@router.delete(
    "/{file_id}",
    status_code=204,
    responses={
        404: {"model": ErrorResponse, "description": "File not found or not accessible"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def delete_file(
    file_id: UUID,
    project_id: UUID = Query(..., description="Project ID", example="11111111-1111-1111-1111-111111111111"),
    db: AsyncSession = Depends(get_db_session_dependency),
):
    """
    Delete a specific file by its UUID. This will permanently delete:
    - The file record from the database
    - All associated document chunks (FileDocument records)
    - The physical file from storage
    
    File must belong to the specified project.
    """
    from sqlalchemy import delete
    from ..models import FileDocument
    
    query = select(FileModel).where(
        and_(
            FileModel.id == file_id,
            FileModel.project_id == project_id,
            FileModel.deleted_at.is_(None)
        )
    )
    
    result = await db.execute(query)
    file_record = result.scalar_one_or_none()
    
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Store storage path for later deletion
    storage_path = file_record.storage_path
    
    # Delete associated FileDocument records first (physical delete)
    await db.execute(
        delete(FileDocument).where(FileDocument.file_id == file_id)
    )
    logger.info(f"Deleted FileDocument records for file {file_id}")
    
    # Delete the file record (physical delete)
    await db.delete(file_record)
    logger.info(f"Deleted file record {file_id}")
    
    await db.commit()
    
    # Delete physical file from storage (after successful DB commit)
    if storage_path and os.path.exists(storage_path):
        try:
            os.remove(storage_path)
            logger.info(f"Deleted physical file from storage: {storage_path}")
        except Exception as e:
            # Log error but don't fail the request since DB records are already deleted
            logger.warning(f"Failed to delete physical file {storage_path}: {e}")


@router.get(
    "/{file_id}/documents",
    responses={
        404: {"model": ErrorResponse, "description": "File not found or not accessible"},
        422: {"model": ErrorResponse, "description": "Validation error - invalid query parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def list_file_documents(
    file_id: UUID,
    content_type: Optional[str] = Query(None, description="Filter by content type"),
    chunk_index: Optional[int] = Query(None, description="Filter by chunk index"),
    limit: int = Query(20, ge=1, le=100, description="Number of documents to return"),
    offset: int = Query(0, ge=0, description="Number of documents to skip"),
    project_id: UUID = Query(..., description="Project ID", example="11111111-1111-1111-1111-111111111111"),
    db: AsyncSession = Depends(get_db_session_dependency),
):
    """
    Retrieve all document chunks generated from a specific file with filtering and pagination.
    
    This endpoint provides access to the processed document chunks for RAG operations.
    """
    # Verify file exists
    file_query = select(FileModel).where(
        and_(
            FileModel.id == file_id,
            FileModel.project_id == project_id,
            FileModel.deleted_at.is_(None)
        )
    )
    file_result = await db.execute(file_query)
    file_record = file_result.scalar_one_or_none()
    
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Build documents query
    from ..models import FileDocument
    query = select(FileDocument).where(
        and_(
            FileDocument.file_id == file_id,
            FileDocument.project_id == project_id
        )
    )

    # Apply filters
    if content_type:
        query = query.where(FileDocument.content_type == content_type)
    if chunk_index is not None:
        query = query.where(FileDocument.chunk_index == chunk_index)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination and ordering
    query = query.offset(offset).limit(limit).order_by(FileDocument.chunk_index.asc())
    
    # Execute query
    result = await db.execute(query)
    documents = result.scalars().all()
    
    # Convert to response models
    from ..schemas.documents import DocumentResponse, DocumentListResponse
    document_responses = [DocumentResponse.model_validate(doc) for doc in documents]
    
    # Create pagination metadata
    pagination = PaginationMetadata(
        total=total,
        limit=limit,
        offset=offset,
        has_next=offset + limit < total,
        has_previous=offset > 0,
    )
    
    return DocumentListResponse(
        data=document_responses,
        pagination=pagination
    )


@router.post(
    "/batch",
    response_model=BatchFileUploadResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request - invalid files or missing data"},
        404: {"model": ErrorResponse, "description": "Collection not found or not accessible"},
        413: {"model": ErrorResponse, "description": "File too large - one or more files exceed maximum size"},
        415: {"model": ErrorResponse, "description": "Unsupported media type - one or more file types not allowed"},
        422: {"model": ErrorResponse, "description": "Validation error - request data validation failed"},
        500: {"model": ErrorResponse, "description": "Internal server error - batch processing failed"}
    }
)
async def upload_files_batch(
    files: List[UploadFile] = File(..., description="List of files to upload"),
    collection_id: UUID = Form(..., description="Collection ID to associate files with"),
    language: Optional[str] = Form("auto", description="Document language (auto-detect if not specified)"),
    description: Optional[str] = Form(None, description="Optional description for all files"),
    tags: Optional[str] = Form(None, description="Comma-separated list of tags to apply to all files"),
    project_id: UUID = Form(..., description="Project ID", example="11111111-1111-1111-1111-111111111111"),
    db: AsyncSession = Depends(get_db_session_dependency),
):
    """
    Upload multiple files for processing in a single batch request.

    This endpoint allows uploading multiple files at once, providing better efficiency
    for bulk operations. Each file is processed individually, and the response includes
    both successful uploads and any failures with detailed error information.

    Features:
    - Maintains backward compatibility with single file uploads
    - Provides detailed error reporting for failed uploads
    - Returns comprehensive batch statistics
    - Applies common metadata (tags, description) to all files
    """
    settings = get_settings()

    # Validate collection exists and belongs to project
    collection_query = select(Collection).where(
        and_(
            Collection.id == collection_id,
            Collection.project_id == project_id,
            Collection.deleted_at.is_(None)
        )
    )
    collection_result = await db.execute(collection_query)
    collection = collection_result.scalar_one_or_none()

    if not collection:
        raise HTTPException(
            status_code=404,
            detail="Collection not found or access denied"
        )

    # Parse tags if provided
    tags_list = None
    if tags:
        tags_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

    # Initialize batch tracking
    successful_uploads = []
    failed_uploads = []
    total_size = 0

    # Process each file
    for file in files:
        try:
            # Validate file
            if not file.filename:
                failed_uploads.append(FileUploadError(
                    filename=file.filename or "unknown",
                    error_code="INVALID_FILE",
                    error_message="File has no filename"
                ))
                continue

            # Check file size
            content = await file.read()
            file_size = len(content)
            total_size += file_size

            if file_size > settings.max_file_size:
                failed_uploads.append(FileUploadError(
                    filename=file.filename,
                    error_code="FILE_TOO_LARGE",
                    error_message=f"File size {file_size} bytes exceeds maximum {settings.max_file_size} bytes"
                ))
                continue

            # Check content type
            if file.content_type not in settings.allowed_file_types:
                failed_uploads.append(FileUploadError(
                    filename=file.filename,
                    error_code="UNSUPPORTED_TYPE",
                    error_message=f"Content type {file.content_type} not supported"
                ))
                continue

            # Generate file ID and storage path
            file_id = uuid4()
            storage_path = os.path.join(settings.upload_dir, str(file_id))

            # Save file to storage
            try:
                os.makedirs(os.path.dirname(storage_path), exist_ok=True)
                with open(storage_path, "wb") as f:
                    f.write(content)
            except Exception as e:
                failed_uploads.append(FileUploadError(
                    filename=file.filename,
                    error_code="STORAGE_ERROR",
                    error_message=f"Failed to save file: {str(e)}"
                ))
                continue

            # Create file record
            file_record = FileModel(
                id=file_id,
                project_id=project_id,
                collection_id=collection_id,
                original_filename=file.filename,
                file_size=file_size,
                content_type=file.content_type,
                storage_provider="local",
                storage_path=storage_path,
                storage_metadata={"original_path": storage_path},
                status="pending",
                language=language,
                description=description,
                tags=tags_list,
                uploaded_by=None,  # TODO: Get from authentication
            )

            # Save to database
            try:
                db.add(file_record)
                await db.flush()  # Get the ID without committing

                # Add to successful uploads
                successful_uploads.append(FileUploadResponse(
                    id=file_record.id,
                    original_filename=file_record.original_filename,
                    file_size=file_record.file_size,
                    content_type=file_record.content_type,
                    status=file_record.status,
                    message="File uploaded successfully and queued for processing"
                ))

            except Exception as e:
                # Clean up storage file if database save fails
                try:
                    os.remove(storage_path)
                except:
                    pass

                failed_uploads.append(FileUploadError(
                    filename=file.filename,
                    error_code="DATABASE_ERROR",
                    error_message=f"Failed to save file record: {str(e)}"
                ))
                continue

        except Exception as e:
            failed_uploads.append(FileUploadError(
                filename=getattr(file, 'filename', 'unknown'),
                error_code="PROCESSING_ERROR",
                error_message=f"Unexpected error processing file: {str(e)}"
            ))

    # Commit successful uploads
    if successful_uploads:
        try:
            await db.commit()

            # Queue processing tasks for successful uploads
            for upload in successful_uploads:
                # Import here to avoid circular imports
                from ..tasks.document_processing import process_file_task
                # Get collection_id from the first successful upload (all uploads use the same collection)
                process_file_task.delay(str(upload.id), str(collection_id))

        except Exception as e:
            await db.rollback()
            # Move all successful uploads to failed
            for upload in successful_uploads:
                failed_uploads.append(FileUploadError(
                    filename=upload.original_filename,
                    error_code="COMMIT_ERROR",
                    error_message=f"Failed to commit batch: {str(e)}"
                ))
            successful_uploads = []

    # Create batch summary
    summary = BatchUploadSummary(
        total_files=len(files),
        successful_uploads=len(successful_uploads),
        failed_uploads=len(failed_uploads),
        total_size=total_size
    )

    # Create response message
    if len(successful_uploads) == len(files):
        message = f"Batch upload completed successfully: {len(successful_uploads)} files uploaded"
    elif len(successful_uploads) == 0:
        message = f"Batch upload failed: all {len(files)} files failed to upload"
    else:
        message = f"Batch upload completed with partial success: {len(successful_uploads)} successful, {len(failed_uploads)} failed"

    return BatchFileUploadResponse(
        summary=summary,
        successful_uploads=successful_uploads,
        failed_uploads=failed_uploads,
        message=message
    )


@router.get(
    "/{file_id}/download",
    response_class=FastAPIFileResponse,
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden - access denied"},
        404: {"model": ErrorResponse, "description": "File not found or not accessible"},
        500: {"model": ErrorResponse, "description": "Internal server error - file system error"}
    }
)
async def download_file(
    file_id: UUID,
    project_id: UUID = Query(..., description="Project ID", example="11111111-1111-1111-1111-111111111111"),
    db: AsyncSession = Depends(get_db_session_dependency),
):
    """
    Download a file by its ID.

    Downloads the original file content with appropriate headers for browser download.
    The file must belong to the specified project.

    Security features:
    - Validates file belongs to the specified project
    - Prevents directory traversal attacks
    - Verifies file exists and is not deleted
    - Supports Unicode filenames with proper encoding
    """
    settings = get_settings()

    # Query file with project validation
    query = select(FileModel).where(
        and_(
            FileModel.id == file_id,
            FileModel.project_id == project_id,
            FileModel.deleted_at.is_(None)
        )
    )

    result = await db.execute(query)
    file_record = result.scalar_one_or_none()

    if not file_record:
        raise HTTPException(
            status_code=404,
            detail="File not found or not accessible. Verify the file exists and you have access to it."
        )

    # Validate storage provider (only support local for now)
    if file_record.storage_provider != "local":
        raise HTTPException(
            status_code=500,
            detail=f"Storage provider '{file_record.storage_provider}' not supported for download"
        )

    # Construct and validate file path
    storage_path = file_record.storage_path

    # Security: Ensure the storage path is within the upload directory
    try:
        # Resolve paths to prevent directory traversal
        upload_dir_resolved = Path(settings.upload_dir).resolve()
        file_path_resolved = Path(storage_path).resolve()

        # Check if file path is within upload directory
        if not str(file_path_resolved).startswith(str(upload_dir_resolved)):
            logger.error(f"Security violation: File path {storage_path} is outside upload directory")
            raise HTTPException(status_code=403, detail="Access denied")

    except Exception as e:
        logger.error(f"Path validation error for file {file_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="File path validation failed")

    # Check if file exists on disk
    if not os.path.exists(storage_path):
        logger.error(f"File not found on disk: {storage_path}")
        raise HTTPException(status_code=404, detail="File not found on storage system")

    # Determine MIME type
    content_type = file_record.content_type
    if not content_type:
        # Fallback to guessing from filename
        guessed_type, _ = mimetypes.guess_type(file_record.original_filename)
        content_type = guessed_type or "application/octet-stream"

    # Create safe filename for download with proper Unicode handling
    safe_filename = file_record.original_filename

    # Handle Unicode filenames properly for Content-Disposition header
    try:
        # Try to encode as ASCII first
        safe_filename.encode('ascii')
        content_disposition = f'attachment; filename="{safe_filename}"'
    except UnicodeEncodeError:
        # Use RFC 5987 encoding for Unicode filenames
        import urllib.parse
        encoded_filename = urllib.parse.quote(safe_filename, safe='')
        content_disposition = f"attachment; filename*=UTF-8''{encoded_filename}"

    # Return file as streaming response
    return FastAPIFileResponse(
        path=storage_path,
        media_type=content_type,
        filename=safe_filename,
        headers={
            "Content-Disposition": content_disposition
        }
    )
