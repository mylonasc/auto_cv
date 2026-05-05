"""
Event generator for Server-Sent Events (SSE) to provide real-time job updates.
"""
import json
from typing import AsyncGenerator


async def job_status_stream(job_id: str, job_manager) -> AsyncGenerator[str, None]:
    """
    Generate SSE events for job status updates.
    
    Yields events whenever the job status changes.
    """
    last_status = None
    last_progress = None
    
    while True:
        job = job_manager.get_job(job_id)
        if not job:
            yield f"event: error\ndata: {json.dumps({'error': 'Job not found'})}\n\n"
            break
        
        current_status = job.status
        current_progress = job.progress
        
        # Send event if status or progress changed
        if current_status != last_status or current_progress != last_progress:
            data = {
                "job_id": job.id,
                "status": current_status,
                "progress": job.progress,
                "message": job.message,
                "updated_at": job.updated_at.isoformat() if job.updated_at else None
            }
            yield f"event: job_update\ndata: {json.dumps(data)}\n\n"
            
            last_status = current_status
            last_progress = current_progress
        
        # If job is complete (succeeded, failed, cancelled), send final event and break
        if current_status in ["succeeded", "failed", "cancelled"]:
            result_data = None
            if job.result:
                if hasattr(job.result, 'model_dump'):
                    result_data = job.result.model_dump()
                elif isinstance(job.result, dict):
                    result_data = job.result
                else:
                    result_data = str(job.result)

            final_data = {
                "job_id": job.id,
                "status": current_status,
                "progress": job.progress,
                "message": job.message,
                "result": result_data,
                "error": job.error,
                "updated_at": job.updated_at.isoformat() if job.updated_at else None
            }
            yield f"event: job_complete\ndata: {json.dumps(final_data)}\n\n"
            break
        
        # Wait before checking again
        import asyncio
        await asyncio.sleep(1)
